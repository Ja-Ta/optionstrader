"""Short-squeeze screen (docs/04 §5) — the book's monthly routine.

Two-stage filter:
  1. SENTIMENT — short interest building: month-over-month shares-short
     increase and adequate days-to-cover (the fuel).
  2. STRENGTH — CMF/MA accumulation (the spark). High short interest with a
     weak chart means the shorts are RIGHT (bankruptcy candidates); a real
     squeeze needs rising shorts colliding with genuine buying.

Verdicts:
  candidate — rising shorts + confirmed accumulation; structure the ITM-put
              ladder (and the earnings-squeeze call if a report is near)
  watch     — rising shorts + a shake-out signature or flow improving but
              unconfirmed; re-check for a month or two
  eliminate — sentiment or strength leg fails (with the reason)

Cadence per the book: one candidate per month is enough. Universe note:
supply the ticker list (published biggest-short-interest-increase lists,
FINRA files, or a broker screener); free APIs cannot sweep the market.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import pandas as pd

from ..config import Config, DEFAULT
from ..data.provider import DataProvider
from ..data.short_interest import ShortInterest, ShortInterestProvider
from ..indicators import add_cmf, add_moving_averages, evaluate_102030
from ..indicators.moving_averages import SlopeClass


@dataclass
class SqueezeParams:
    min_days_to_cover: float = 2.0      # CALIB: fuel floor (book examples ran 3.5-5.5)
    min_si_increase: float = 0.10       # CALIB: MoM shares-short build >= 10%
    cross_lookback: int = 20            # CALIB: "fresh" MA cross window (bars)
    drop_window: int = 5                # shake-out detection window
    drop_pct: float = 0.10
    min_dte: int = 45                   # ITM-put tenor window (book: 2-6 months,
    max_dte: int = 150                  #   January favored for seasonal strength)
    max_call_price: float = 0.20        # BOOK: never pay > $0.20/share for calls
    call_budget_frac: float = 0.10      # BOOK: ~10% of ITM-put proceeds
    earnings_horizon_days: int = 45     # flag earnings-squeeze setups this close


@dataclass
class ItmPutSuggestion:
    strike: float
    expiry: date
    premium: float          # per share (bid; last fallback)
    intrinsic: float
    time_value: float


@dataclass
class EarningsCallSuggestion:
    strike: float
    expiry: date
    ask: float


@dataclass
class SqueezeReport:
    ticker: str
    price: float
    verdict: str                        # "candidate" | "watch" | "eliminate"
    reasons: list[str] = field(default_factory=list)
    days_to_cover: float | None = None
    si_change_pct: float | None = None
    cmf: float = 0.0
    itm_put: ItmPutSuggestion | None = None
    earnings_call: EarningsCallSuggestion | None = None
    next_earnings: date | None = None

    def summary(self) -> str:
        dtc = f"{self.days_to_cover:.1f}" if self.days_to_cover is not None else "?"
        chg = f"{self.si_change_pct:+.0%}" if self.si_change_pct is not None else "?"
        lines = [f"{self.ticker:<6} {self.verdict.upper():<10} price {self.price:.2f}  "
                 f"days-to-cover {dtc}  SI MoM {chg}  CMF {self.cmf:+.2f}"]
        lines += [f"    - {r}" for r in self.reasons]
        if self.itm_put:
            p = self.itm_put
            lines.append(
                f"    play: sell ITM {p.strike:g} put exp {p.expiry} @ ~{p.premium:.2f} "
                f"({p.intrinsic:.2f} intrinsic + {p.time_value:.2f} time); when the stock "
                f"crosses {p.strike:g}, buy back for time value and ladder to the next ITM strike"
            )
        if self.earnings_call:
            c = self.earnings_call
            lines.append(
                f"    earnings-squeeze add-on (earnings {self.next_earnings}): buy {c.strike:g} "
                f"calls exp {c.expiry} @ {c.ask:.2f} (≤ $0.20 rule; budget ~10% of put proceeds)"
            )
        return "\n".join(lines)


def assess_squeeze(
    ticker: str,
    df: pd.DataFrame,
    si: ShortInterest | None,
    params: SqueezeParams | None = None,
    cfg: Config = DEFAULT,
) -> SqueezeReport:
    """Pure verdict logic (no chain lookups) — testable offline."""
    p = params or SqueezeParams()
    price = float(df["close"].iloc[-1])
    report = SqueezeReport(ticker=ticker.upper(), price=price, verdict="eliminate")

    # --- stage 1: sentiment fuel ---
    if si is None or si.shares_short is None or si.shares_short_prior_month is None:
        report.reasons.append("no usable short-interest data")
        return report
    report.days_to_cover = si.days_to_cover
    report.si_change_pct = si.change_pct
    if si.change_pct is None or si.change_pct < p.min_si_increase:
        report.reasons.append(
            f"short interest not building (MoM {si.change_pct:+.0%})" if si.change_pct is not None
            else "short-interest change unknown"
        )
        return report
    if si.days_to_cover is not None and si.days_to_cover < p.min_days_to_cover:
        report.reasons.append(
            f"days-to-cover {si.days_to_cover:.1f} below {p.min_days_to_cover:g} — not enough fuel"
        )
        return report

    # --- stage 2: strength (the spark) ---
    frame = add_cmf(add_moving_averages(df, cfg), cfg)
    t = evaluate_102030(frame, cfg)
    cmf = frame["cmf"].dropna()
    cmf_now = float(cmf.iloc[-1]) if len(cmf) else 0.0
    report.cmf = cmf_now

    above = (frame["ma10"] > frame["ema20"]).fillna(False)
    fresh_cross = bool(above.iloc[-1] and not above.tail(p.cross_lookback).all())
    cmf_flip = bool(
        len(cmf) > p.cross_lookback and cmf_now > 0 and float(cmf.iloc[-p.cross_lookback]) <= 0
    )

    w = p.drop_window
    dropped = len(frame) > w and price <= float(frame["close"].iloc[-1 - w]) * (1 - p.drop_pct)
    if dropped:
        if cmf_now < -cfg.book.cmf_band:
            report.reasons.append(
                f"sharp drop with CMF {cmf_now:+.2f} < -0.1 — the shorts are right; do not fight distribution"
            )
            return report
        report.verdict = "watch"
        report.reasons.append(
            f"sharp drop on weak flow (CMF {cmf_now:+.2f} inside ±0.1) — shake-out signature; "
            "watchlist for the next month or two"
        )
        return report

    if above.iloc[-1] and cmf_now <= 0:
        report.reasons.append(
            f"MA rising without money flow (CMF {cmf_now:+.2f}) — run-up not institutionally backed"
        )
        return report

    accumulating = cmf_now > 0 and (
        fresh_cross or cmf_flip or t.ma10_slope in (SlopeClass.STEEP_UP, SlopeClass.UP)
    )
    if above.iloc[-1] and accumulating:
        report.verdict = "candidate"
        bits = []
        if fresh_cross:
            bits.append("fresh MA(10)×EMA(20) upcross")
        if cmf_flip:
            bits.append("CMF flipped negative→positive")
        bits.append(f"CMF {cmf_now:+.2f} with shorts building {si.change_pct:+.0%} MoM")
        report.reasons.append("rising shorts + confirmed accumulation: " + "; ".join(bits))
        return report

    report.verdict = "watch"
    report.reasons.append(
        "shorts building but accumulation unconfirmed (need MA(10) above EMA(20) with positive CMF)"
    )
    return report


def _attach_plays(report: SqueezeReport, provider: DataProvider, params: SqueezeParams) -> None:
    """Best-effort ITM-put ladder + earnings-call suggestions from live chains."""
    if report.verdict != "candidate":
        return
    try:
        today = date.today()
        expiries = [e for e in provider.option_expirations(report.ticker)
                    if params.min_dte <= (e - today).days <= params.max_dte]
        if expiries:
            chain = provider.option_chain(report.ticker, expiries[0])
            itm_puts = sorted((q for q in chain if q.kind == "put" and q.strike > report.price
                               and (q.bid > 0 or q.last > 0)), key=lambda q: q.strike)
            if itm_puts:
                q = itm_puts[0]  # nearest ITM strike above price (ladder start)
                prem = q.bid if q.bid > 0 else q.last
                intrinsic = q.strike - report.price
                report.itm_put = ItmPutSuggestion(
                    strike=q.strike, expiry=q.expiry, premium=prem,
                    intrinsic=intrinsic, time_value=max(prem - intrinsic, 0.0),
                )
        earnings = provider.next_earnings_date(report.ticker)
        if earnings and 0 <= (earnings - date.today()).days <= params.earnings_horizon_days:
            report.next_earnings = earnings
            # Expiry one month past the NEXT report (book rule); cheapest strike ≤ $0.20.
            target = earnings + timedelta(days=30)
            later = [e for e in provider.option_expirations(report.ticker) if e >= target]
            if later:
                chain = provider.option_chain(report.ticker, later[0])
                cheap = sorted(
                    (q for q in chain if q.kind == "call" and q.strike > report.price
                     and 0 < (q.ask if q.ask > 0 else q.last) <= params.max_call_price),
                    key=lambda q: q.strike,
                )
                if cheap:
                    q = cheap[0]
                    report.earnings_call = EarningsCallSuggestion(
                        strike=q.strike, expiry=q.expiry, ask=q.ask if q.ask > 0 else q.last
                    )
    except Exception:  # noqa: BLE001 — plays are suggestions; the verdict stands without them
        pass


def screen_squeeze(
    tickers: list[str],
    provider: DataProvider,
    si_provider: ShortInterestProvider | None = None,
    params: SqueezeParams | None = None,
    cfg: Config = DEFAULT,
) -> list[SqueezeReport]:
    p = params or SqueezeParams()
    if si_provider is None:
        from ..data.short_interest import YFinanceShortInterest

        si_provider = YFinanceShortInterest()
    reports: list[SqueezeReport] = []
    for t in tickers:
        try:
            df = provider.daily_ohlcv(t, lookback_days=300)
            si = si_provider.get(t)
            report = assess_squeeze(t, df, si, p, cfg)
            _attach_plays(report, provider, p)
            reports.append(report)
        except Exception as e:  # noqa: BLE001
            reports.append(SqueezeReport(ticker=t.upper(), price=0.0, verdict="eliminate",
                                         reasons=[f"data error: {e}"]))
    order = {"candidate": 0, "watch": 1, "eliminate": 2}
    reports.sort(key=lambda r: (order[r.verdict], -(r.si_change_pct or 0.0)))
    return reports
