"""The daily after-close routine (docs/03 §3) as one consolidated run.

For every holding in the portfolio:
  - fetch data, build the Snapshot (with live-priced open shorts), run the
    decision state machine
  - tracker alerts per open short (25% buy-back, assignment watch, expiry,
    event proximity) priced from the live chain
  - 15% stop-loss check, CD relative-strength state, earnings countdown
Then run the Chapter-19 scan over the watch list and emit one action report,
most-urgent first.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from .analysis import build_snapshot
from .config import Config, DEFAULT
from .data.provider import DataProvider
from .indicators import assess_cd
from .options.tracker import ShortOption, check_short_option
from .portfolio import Portfolio, Position
from .scanner import ScanParams, ScanReport, run_scan
from .signals import Action, assess
from .signals.states import ShortOptionView


@dataclass
class HoldingReport:
    ticker: str
    price: float
    state: str
    actions: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    alerts: list[str] = field(default_factory=list)      # tracker output, formatted
    cd_state: str = "n/a"
    cd_signals: list[str] = field(default_factory=list)
    stop_breached: bool = False
    days_to_earnings: int | None = None
    error: str | None = None


@dataclass
class DailyReport:
    as_of: date
    holdings: list[HoldingReport] = field(default_factory=list)
    scan_hits: list[ScanReport] = field(default_factory=list)
    scanned: int = 0
    action_items: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [f"=== DAILY REPORT {self.as_of} ===", ""]
        if self.action_items:
            lines.append("ACTION ITEMS (most urgent first):")
            lines += [f"  {i + 1}. {a}" for i, a in enumerate(self.action_items)]
        else:
            lines.append("ACTION ITEMS: none — no signals today")
        lines.append("")
        lines.append(f"HOLDINGS ({len(self.holdings)}):")
        for h in self.holdings:
            if h.error:
                lines.append(f"  {h.ticker}: ERROR — {h.error}")
                continue
            earn = f", earnings in {h.days_to_earnings}d" if h.days_to_earnings is not None else ""
            lines.append(f"  {h.ticker} @ {h.price:.2f} — state {h.state}, CD {h.cd_state}{earn}")
            for a in h.alerts:
                lines.append(f"      ALERT {a}")
            for n in h.notes:
                lines.append(f"      {n}")
        lines.append("")
        lines.append(f"WATCHLIST SCAN: {len(self.scan_hits)} of {self.scanned} passed")
        for r in self.scan_hits:
            lines.append(f"  {r.ticker} {r.bucket.upper()} @ {r.price:.2f} (vol {r.volume_ratio:.1f}x)")
            lines += [f"      - {reason}" for reason in r.reasons]
        return "\n".join(lines)


def _short_views_and_alerts(
    pos: Position, spot: float, today: date, provider: DataProvider,
    days_to_event: int | None, cfg: Config,
) -> tuple[list[ShortOptionView], list[str]]:
    views: list[ShortOptionView] = []
    alerts: list[str] = []
    chains: dict[str, list] = {}
    for o in pos.open_shorts:
        expiry = datetime.strptime(o.expiry, "%Y-%m-%d").date()
        if expiry < today:
            alerts.append(
                f"[NOW ] {pos.ticker} {o.expiry} {o.strike:g} {o.kind}: EXPIRED — "
                "record the outcome (expired/assigned) in the ledger"
            )
            continue
        price = None
        try:
            key = o.expiry
            if key not in chains:
                chains[key] = provider.option_chain(pos.ticker, expiry)
            q = next((q for q in chains[key] if q.kind == o.kind and abs(q.strike - o.strike) < 1e-6), None)
            if q is not None:
                price = q.ask if q.ask > 0 else (q.last or None)  # buy-back side
        except Exception:  # noqa: BLE001 — chain fetch failure: alerts still run on spot
            pass
        views.append(ShortOptionView(
            kind=o.kind, strike=o.strike, expiry=expiry, contracts=o.contracts,
            premium_collected=o.premium_collected, current_price=price,
        ))
        so = ShortOption(pos.ticker, o.kind, o.strike, expiry, o.contracts,
                         o.premium_collected, today)
        for a in check_short_option(so, spot, price, today, days_to_event, cfg):
            alerts.append(str(a))
    return views, alerts


def run_daily(
    portfolio: Portfolio,
    provider: DataProvider,
    watchlist: list[str] | None = None,
    index_symbol: str = "^GSPC",
    scan_params: ScanParams | None = None,
    cfg: Config = DEFAULT,
) -> DailyReport:
    index_df = None
    try:
        index_df = provider.daily_ohlcv(index_symbol, lookback_days=420)
    except Exception:  # noqa: BLE001 — CD section degrades gracefully
        pass

    report = DailyReport(as_of=date.today())
    urgent: list[tuple[int, str]] = []   # (priority, message) — lower is first

    for ticker, pos in sorted(portfolio.positions.items()):
        h = HoldingReport(ticker=ticker, price=0.0, state="")
        report.holdings.append(h)
        try:
            df = provider.daily_ohlcv(ticker, lookback_days=300)
        except Exception as e:  # noqa: BLE001
            h.error = str(e)
            continue
        spot = float(df["close"].iloc[-1])
        today = df.index[-1].date() if hasattr(df.index[-1], "date") else date.today()
        report.as_of = today
        h.price = spot

        earnings = None
        try:
            earnings = provider.next_earnings_date(ticker)
        except Exception:  # noqa: BLE001
            pass
        h.days_to_earnings = (earnings - today).days if earnings and earnings >= today else None

        views, alerts = _short_views_and_alerts(pos, spot, today, provider, h.days_to_earnings, cfg)
        h.alerts = alerts
        for a in alerts:
            if "[NOW " in a:
                urgent.append((0, a.replace("[NOW ] ", "")))
            elif "[SOON]" in a:
                urgent.append((1, a.replace("[SOON] ", "")))

        snap = build_snapshot(
            ticker, df, shares_held=pos.shares, willing_to_add=pos.willing_to_add,
            short_options=views, days_to_next_event=h.days_to_earnings, cfg=cfg,
        )
        result = assess(snap, cfg)
        h.state = result.state.value
        h.actions = [a.value for a in result.actions]
        h.notes = result.notes
        for a in result.actions:
            if a not in (Action.HOLD, Action.NO_ACTION):
                urgent.append((2, f"{ticker}: {a.value} — see holding notes"))

        if pos.shares > 0 and pos.stop_loss_breached(spot, cfg.book.stock_stop_loss):
            h.stop_breached = True
            urgent.append((0, f"{ticker}: closed {cfg.book.stock_stop_loss:.0%}+ below cost — "
                              "book rule: sell and replace (close short calls first)"))

        if index_df is not None and pos.account == "long_term":
            cd = assess_cd(df["close"], index_df["close"])
            h.cd_state = cd.state
            h.cd_signals = cd.sell_signals + cd.buy_signals
            if cd.state == "sell_defend":
                urgent.append((1, f"{ticker}: CD deterioration — {cd.sell_signals[0]}"))

    if watchlist:
        holdings_set = set(portfolio.positions)
        candidates = [t for t in watchlist if t.upper() not in holdings_set]
        results = run_scan(candidates, provider, scan_params, cfg)
        report.scanned = len(results)
        report.scan_hits = [r for r in results if r.passed]
        for r in report.scan_hits:
            if r.bucket == "enter":
                urgent.append((2, f"{r.ticker}: scan ENTER candidate — {r.reasons[0]}"))

    report.action_items = [msg for _, msg in sorted(urgent, key=lambda x: x[0])]
    return report
