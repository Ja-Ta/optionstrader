"""CLI entry points — one command per workflow stage (see docs/08 §1).

  FIND     screen (capability) · scan (reversals + timing) · squeeze (SI build)
  ENTER    plan (half/half put tranches) · record (log fills, gated)
  MANAGE   daily (the after-close routine; file/email delivery) · analyze
  EXIT     cd (relative-strength deterioration) · record · status
  VERIFY   backtest (3-strategy comparison, synthetic pricing)

Run `optionstrader <command> -h` for flags. All commands obtain market data
via data.get_provider() (env-selectable, cached); none place orders.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def cmd_analyze(args: argparse.Namespace) -> int:
    from .analysis import analyze
    from .data import get_provider
    from .indicators import detect_levels

    provider = get_provider()
    df = provider.daily_ohlcv(args.ticker)
    snap, result = analyze(
        args.ticker,
        df,
        shares_held=args.shares,
        willing_to_add=args.willing_to_add,
    )

    print(f"{snap.ticker}  {snap.as_of}  close {snap.price:.2f}")
    print(
        f"trend={snap.trend.value}  ma10_slope={snap.ma10_slope.value}  "
        f"cmf={snap.cmf:+.3f} ({snap.cmf_band.value})"
    )
    print(
        f"vol_ratio={snap.volume.volume_ratio:.2f}  "
        f"above_20d_low={snap.pct_above_20d_low:.1%}  "
        f"{args.ticker.upper()} {snap.drop_pct_window:+.1%} over shakeout window"
    )
    sup = f"{snap.nearest_support:.2f}" if snap.nearest_support else "—"
    res = f"{snap.nearest_resistance:.2f}" if snap.nearest_resistance else "—"
    print(f"support {sup}  |  price {snap.price:.2f}  |  resistance {res}")
    if args.levels:
        for lv in detect_levels(df):
            print(
                f"  level {lv.price:8.2f}  {lv.role(snap.price):10s} "
                f"touches={lv.touches}  span={lv.span_days}d  strength={lv.strength():.1f}"
            )
    print()
    print(result.summary())
    if args.short_term:
        from .indicators import assess_short_term

        print()
        print("short-term toolkit (Ch-18 — decides WHEN/WHERE, never WHETHER):")
        for line in assess_short_term(df).lines():
            print(f"  {line}")
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    from datetime import date

    from .portfolio import Portfolio

    pf = Portfolio.load(Path(args.portfolio))
    pos = pf.get(args.ticker)
    day = args.date or date.today().isoformat()

    try:
        if args.action == "buy-stock":
            pos.buy_shares(args.shares, args.price, day, args.note or "")
            if args.account:
                pos.account = args.account
            print(f"bought {args.shares} {pos.ticker} @ {args.price:.2f} ({pos.account})")
        elif args.action == "sell-stock":
            proceeds = pos.sell_shares(args.shares, args.price, day, args.note or "")
            print(f"sold {args.shares} {pos.ticker} @ {args.price:.2f} — proceeds ${proceeds:,.2f}")
        elif args.action in ("sell-call", "sell-put"):
            kind = args.action.split("-")[1]
            warnings = pos.record_option_sale(
                kind, args.strike, args.expiry, args.contracts, args.premium, day, args.note or ""
            )
            credit = args.premium * args.contracts * 100
            print(f"sold {args.contracts}x {pos.ticker} {args.expiry} {args.strike:g} {kind} "
                  f"@ {args.premium:.2f} — ${credit:,.0f} collected")
            print(f"  25% buy-back trigger: repurchase at ≤ {0.25 * args.premium:.2f}")
            for w in warnings:
                print(f"  WARNING: {w}")
        elif args.action == "buyback":
            r = pos.record_buyback(args.kind, args.strike, args.expiry, args.price, day,
                                   args.contracts, args.note or "")
            print(f"bought back {r['contracts']}x {pos.ticker} {args.expiry} {args.strike:g} {args.kind} "
                  f"@ {args.price:.2f} — captured {r['captured_fraction']:.0%} of premium "
                  f"(${r['profit_per_share'] * r['contracts'] * 100:,.0f})")
            if not r["rule_25pct_met"]:
                print("  note: above the 25%-of-premium level — early/defensive close")
        elif args.action == "expired":
            r = pos.record_expired(args.kind, args.strike, args.expiry, day, args.contracts)
            print(f"{r['contracts']}x {pos.ticker} {args.expiry} {args.strike:g} {args.kind} "
                  f"expired worthless — ${r['premium_kept']:,.0f} premium kept")
        elif args.action == "assigned":
            r = pos.record_assigned(args.kind, args.strike, args.expiry, day, args.contracts)
            if "shares_acquired" in r:
                print(f"assigned: bought {r['shares_acquired']} {pos.ticker} @ {r['cost_per_share']:g} "
                      f"(effective {r['effective_cost']:.2f} after premium) — start selling covered calls")
            else:
                print(f"assigned: {r['shares_delivered']} {pos.ticker} called away @ {args.strike:g} "
                      f"— proceeds ${r['proceeds']:,.2f}")
    except ValueError as e:
        print(f"REFUSED: {e}")
        return 1

    pf.save()
    basis = pos.adjusted_basis_per_share
    print(f"position now: {pos.shares} shares, net premium ${pos.net_premium:,.2f}, "
          f"adjusted basis {f'{basis:.2f}' if basis is not None else '—'}, "
          f"open shorts {len(pos.open_shorts)}")
    return 0


def cmd_daily(args: argparse.Namespace) -> int:
    import json

    from .daily import run_daily
    from .data import get_provider
    from .portfolio import Portfolio
    from .scanner import ScanParams

    pf = Portfolio.load(Path(args.portfolio))
    watchlist = list(args.watchlist or [])
    if args.watchlist_file:
        raw = Path(args.watchlist_file).read_text().strip()
        watchlist += json.loads(raw) if raw.startswith("[") else raw.split()
    if not pf.positions and not watchlist:
        print("nothing to do: no positions in the portfolio and no watchlist given")
        print(f"  portfolio file: {args.portfolio} — add positions, or pass --watchlist TICKER...")
        return 1
    report = run_daily(
        pf,
        get_provider(),
        watchlist=watchlist,
        index_symbol=args.index,
        scan_params=ScanParams(max_price=args.scan_max_price),
    )
    text = report.summary()
    if not args.quiet:
        print(text)

    exit_code = 0
    if args.save_dir:
        from .reporting import save_report

        path = save_report(text, Path(args.save_dir), report.as_of)
        print(f"[saved] {path}")
    if args.email:
        from .reporting import email_report

        n_items = len(report.action_items)
        subject = f"optionstrader daily {report.as_of} — {n_items} action item{'s' if n_items != 1 else ''}"
        try:
            email_report(text, args.email, subject)
            print(f"[emailed] {args.email}")
        except RuntimeError as e:
            print(f"[email FAILED] {e}")
            exit_code = 1  # file (if any) is already saved; flag the failure for cron logs
    return exit_code


def cmd_scan(args: argparse.Namespace) -> int:
    from .data import get_provider
    from .scanner import ScanParams, run_scan

    p = ScanParams(min_price=args.min_price, max_price=args.max_price)
    reports = run_scan(args.tickers, get_provider(), p)
    hits = [r for r in reports if r.passed]
    print(f"scanned {len(reports)} tickers — {len(hits)} passed the 10 conditions\n")
    for r in hits:
        print(f"{r.ticker:<6} {r.bucket.upper():<10} price {r.price:.2f}  "
              f"vol {r.volume_ratio:.1f}x avg  day {r.day_change:+.1%}")
        for reason in r.reasons:
            print(f"    - {reason}")
        if r.timing:
            print(f"    timing: {r.timing}")
    if args.verbose:
        print("\nnon-passers:")
        for r in reports:
            if not r.passed:
                print(f"  {r.ticker:<6} failed: {', '.join(r.failed()) or ', '.join(r.reasons)}")
    if len(hits) > 10:
        print("\nNOTE: >10 hits — the book: too many means criteria too broad; tighten the band.")
    return 0


def cmd_squeeze(args: argparse.Namespace) -> int:
    from .data import get_provider
    from .scanner import screen_squeeze

    reports = screen_squeeze(args.tickers, get_provider())
    candidates = [r for r in reports if r.verdict == "candidate"]
    for r in reports:
        if r.verdict != "eliminate" or args.verbose:
            print(r.summary())
    print(f"\n{len(candidates)} candidate(s), "
          f"{sum(1 for r in reports if r.verdict == 'watch')} watch, "
          f"{sum(1 for r in reports if r.verdict == 'eliminate')} eliminated of {len(reports)}")
    print("book cadence: ONE squeeze candidate per month is enough; supply the "
          "published biggest-SI-increase list as the universe")
    return 0


def cmd_cd(args: argparse.Namespace) -> int:
    from .data import get_provider
    from .indicators import assess_cd, cd_series

    provider = get_provider()
    stock = provider.daily_ohlcv(args.ticker, lookback_days=args.days)
    index = provider.daily_ohlcv(args.index, lookback_days=args.days)
    result = assess_cd(stock["close"], index["close"])
    print(f"{args.ticker.upper()} vs {args.index}  (weekly CD, Monday-anchored)")
    print(result.summary())
    if args.table:
        frame = cd_series(stock["close"], index["close"]).tail(args.weeks)
        print("\n  week          price       cd")
        for ts, row in frame.iterrows():
            print(f"  {ts.date()}  {row['price']:9.2f}  {row['cd']:7.3f}")
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    from .data import get_provider
    from .options import plan_half_half

    plan = plan_half_half(
        args.ticker, get_provider(), target_shares=args.shares, cash_available=args.cash
    )
    print(plan.summary())
    print("\nNOTE: plan only — the book's gates still apply before selling "
          "(willingness to own at the strike; close before binary events; 25% buy-back after).")
    return 0


def cmd_screen(args: argparse.Namespace) -> int:
    from .data import get_provider
    from .screening import screen_live

    provider = get_provider()
    reports = []
    for ticker in args.tickers:
        try:
            reports.append(screen_live(ticker, provider))
        except Exception as e:  # noqa: BLE001
            print(f"{ticker.upper()}: ERROR — {e}")
    reports.sort(key=lambda r: (not r.passed, -r.score))
    for r in reports:
        print(r.summary() if args.verbose else
              f"{r.ticker:<6} {'PASS' if r.passed else 'FAIL'}  score={r.score:.1%}  "
              f"failed_legs={', '.join(l.name for l in r.legs if not l.passed) or '—'}")
        if args.verbose:
            print()
    passed = [r.ticker for r in reports if r.passed]
    print(f"\ncapability list ({len(passed)}/{len(reports)}): {', '.join(passed) or 'none'}")
    print("NOTE: extension screen (docs/06) — advisory shortlist only; portfolio "
          "selection stays a human decision (willingness-to-own cannot be screened).")
    return 0


def cmd_backtest(args: argparse.Namespace) -> int:
    from .backtest import BuyAndHold, EliasEngine, NaiveCoveredCall, comparison_table, run_backtest
    from .backtest.pricing import SyntheticPricer
    from .data import get_provider

    provider = get_provider()
    df = provider.daily_ohlcv(args.ticker, lookback_days=args.days)
    pricer = SyntheticPricer(iv_premium=args.iv_premium, friction=args.friction)

    strategies = {
        "buyhold": lambda: BuyAndHold(),
        "naive-cc": lambda: NaiveCoveredCall(),
        "elias": lambda: EliasEngine(willing_to_add=args.willing_to_add),
    }
    picked = list(strategies) if args.strategy == "all" else [args.strategy]

    print(
        f"{args.ticker.upper()}  {df.index[0].date()} → {df.index[-1].date()}  "
        f"({len(df)} bars, ${args.cash:,.0f} initial, iv_premium={args.iv_premium}, "
        f"friction={args.friction:.0%})"
    )
    print("NOTE: option premiums are SYNTHETIC (Black-Scholes on realized vol) — "
          "measures timing-rule value, not exact historical premiums.\n")

    results = [
        run_backtest(df, strategies[name](), initial_cash=args.cash, pricer=pricer)
        for name in picked
    ]
    print(comparison_table(results))
    if args.trades:
        for r in results:
            print(f"\n=== {r.strategy} trades ===")
            for t in r.trades:
                print(f"  {t.date}  {t.what:<14} {t.detail}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    from .portfolio import Portfolio

    pf = Portfolio.load(Path(args.file))
    if not pf.positions:
        print(f"no positions in {args.file}")
        return 0
    prices = dict(kv.split("=") for kv in (args.price or []))
    for t, pos in sorted(pf.positions.items()):
        print(f"— {t} ({pos.account}, willing_to_add={pos.willing_to_add})")
        px = float(prices[t]) if t in prices else None
        if px is not None:
            for k, v in pos.mark_to_market(px).items():
                print(f"    {k}: {v}")
            if pos.stop_loss_breached(px):
                print("    *** 15% STOP-LOSS BREACHED — book rule: sell and replace ***")
        else:
            basis = pos.adjusted_basis_per_share
            print(f"    shares: {pos.shares}  net_premium: {pos.net_premium:,.2f}")
            print(f"    adjusted_basis_per_share: {basis if basis is not None else '—'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="optionstrader")
    sub = parser.add_subparsers(dest="command", required=True)

    p_an = sub.add_parser("analyze", help="run the decision engine on a ticker")
    p_an.add_argument("ticker")
    p_an.add_argument("--shares", type=int, default=0)
    p_an.add_argument("--willing-to-add", action="store_true")
    p_an.add_argument("--levels", action="store_true", help="print detected S/R levels")
    p_an.add_argument("--short-term", action="store_true", help="Ch-18 oscillator/envelope timing block")
    p_an.set_defaults(func=cmd_analyze)

    p_rc = sub.add_parser("record", help="log a fill: keeps the ledger and open_shorts in sync")
    p_rc.add_argument("action", choices=["buy-stock", "sell-stock", "sell-call", "sell-put",
                                         "buyback", "expired", "assigned"])
    p_rc.add_argument("ticker")
    p_rc.add_argument("--portfolio", default="portfolio.json")
    p_rc.add_argument("--shares", type=int, help="stock actions")
    p_rc.add_argument("--price", type=float, help="stock price or option buy-back price per share")
    p_rc.add_argument("--kind", choices=["call", "put"], help="buyback/expired/assigned")
    p_rc.add_argument("--strike", type=float)
    p_rc.add_argument("--expiry", help="ISO date, e.g. 2026-08-21")
    p_rc.add_argument("--contracts", type=int, default=None)
    p_rc.add_argument("--premium", type=float, help="per-share premium collected (sell-call/sell-put)")
    p_rc.add_argument("--date", default=None, help="fill date (default today)")
    p_rc.add_argument("--note", default=None)
    p_rc.add_argument("--account", choices=["long_term", "short_term"], default=None,
                      help="account bucket on buy-stock (short_term gets envelope management in daily)")
    p_rc.set_defaults(func=cmd_record)

    p_dy = sub.add_parser("daily", help="the after-close routine: holdings + alerts + CD + watchlist scan")
    p_dy.add_argument("--portfolio", default="portfolio.json")
    p_dy.add_argument("--watchlist", nargs="*", metavar="TICKER")
    p_dy.add_argument("--watchlist-file", help="file with tickers (JSON list or whitespace-separated)")
    p_dy.add_argument("--index", default="^GSPC", help="benchmark index for CD charts")
    p_dy.add_argument("--scan-max-price", type=float, default=10.0)
    p_dy.add_argument("--save-dir", default=None, help="save the report to DIR/daily-YYYY-MM-DD.txt (+ latest.txt)")
    p_dy.add_argument("--email", default=None, metavar="ADDR", help="email the report (SMTP env vars; see reporting.py)")
    p_dy.add_argument("--quiet", action="store_true", help="suppress stdout (for cron; file/email only)")
    p_dy.set_defaults(func=cmd_daily)

    p_sn = sub.add_parser("scan", help="Chapter-19 10-condition reversal scan + triage over a ticker list")
    p_sn.add_argument("tickers", nargs="+", help="candidate list (broker screener output / watchlist)")
    p_sn.add_argument("--min-price", type=float, default=5.0)
    p_sn.add_argument("--max-price", type=float, default=10.0, help="scale to account size")
    p_sn.add_argument("--verbose", action="store_true", help="show non-passers with failed conditions")
    p_sn.set_defaults(func=cmd_scan)

    p_sq = sub.add_parser("squeeze", help="short-squeeze screen: SI build + accumulation filter, ITM-put ladder")
    p_sq.add_argument("tickers", nargs="+", help="candidate list (published biggest-SI-increase names)")
    p_sq.add_argument("--verbose", action="store_true", help="also show eliminated names")
    p_sq.set_defaults(func=cmd_squeeze)

    p_cd = sub.add_parser("cd", help="weekly CD relative-strength chart (long-term exit tool)")
    p_cd.add_argument("ticker")
    p_cd.add_argument("--index", default="^GSPC", help="benchmark index (^GSPC, ^IXIC, sector ETF)")
    p_cd.add_argument("--days", type=int, default=420)
    p_cd.add_argument("--table", action="store_true", help="print the weekly CD table")
    p_cd.add_argument("--weeks", type=int, default=16, help="table rows with --table")
    p_cd.set_defaults(func=cmd_cd)

    p_pl = sub.add_parser("plan", help="half/half put-sale entry plan for a new position")
    p_pl.add_argument("ticker")
    p_pl.add_argument("--shares", type=int, required=True, help="total shares desired")
    p_pl.add_argument("--cash", type=float, default=None, help="cash available to secure the puts")
    p_pl.set_defaults(func=cmd_plan)

    p_sc = sub.add_parser("screen", help="20/20/20 capability screen (docs/06) on live chains")
    p_sc.add_argument("tickers", nargs="+")
    p_sc.add_argument("--verbose", action="store_true", help="per-leg detail")
    p_sc.set_defaults(func=cmd_screen)

    p_bt = sub.add_parser("backtest", help="backtest strategies with synthetic option pricing")
    p_bt.add_argument("ticker")
    p_bt.add_argument("--strategy", choices=["buyhold", "naive-cc", "elias", "all"], default="all")
    p_bt.add_argument("--days", type=int, default=750, help="lookback trading days (default ~3y)")
    p_bt.add_argument("--cash", type=float, default=100_000)
    p_bt.add_argument("--iv-premium", type=float, default=1.20, help="IV = realized vol x this")
    p_bt.add_argument("--friction", type=float, default=0.05, help="per-side option slippage fraction")
    p_bt.add_argument("--willing-to-add", action="store_true", help="allow put selling at support")
    p_bt.add_argument("--trades", action="store_true", help="print the trade log")
    p_bt.set_defaults(func=cmd_backtest)

    p_st = sub.add_parser("status", help="show the portfolio ledger")
    p_st.add_argument("--file", default="portfolio.json")
    p_st.add_argument("--price", action="append", metavar="TICKER=PX")
    p_st.set_defaults(func=cmd_status)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
