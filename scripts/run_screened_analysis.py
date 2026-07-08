"""Split the baseline sweep results by capability-screen verdict.

Per docs/06 the screen refreshes weekly and holdings re-check quarterly — a
single-date verdict is meaningless (and bar 60 of the sweep window was the
Oct-2023 market low, failing `not_freefall` universally). So: fetch extra
history, evaluate the proxy at ~quarterly checkpoints (every 63 bars) across
the same period the baseline backtests traded, and classify each ticker by
its PASS RATE. A ticker "qualifies" if it passed at 25%+ of checkpoints
(entry opportunities existed reasonably often).

Usage: .venv/bin/python scripts/run_screened_analysis.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from optionstrader.data.yfinance_provider import YFinanceProvider  # noqa: E402
from optionstrader.screening import capability_proxy  # noqa: E402

UNIVERSE = [
    "AMD", "NVDA", "TSLA", "PLTR", "COIN", "MARA",
    "AAPL", "MSFT", "AMZN", "XOM", "FCX",
    "F", "INTC", "PFE", "T", "KO",
]
FETCH_DAYS = 1050          # 750-bar trade window + ~300 bars of screen history
TRADE_BARS = 750
CHECK_EVERY = 63           # ~quarterly
QUALIFY_RATE = 0.25
OUT = Path(__file__).resolve().parents[1] / "backtests"


def main() -> None:
    provider = YFinanceProvider()
    rows = {}
    for t in UNIVERSE:
        try:
            df = provider.daily_ohlcv(t, lookback_days=FETCH_DAYS)
        except Exception as e:  # noqa: BLE001
            print(f"{t}: ERROR {e}", flush=True)
            continue
        start = max(len(df) - TRADE_BARS, 260)   # first checkpoint has >=260 bars of history
        checkpoints = list(range(start, len(df), CHECK_EVERY))
        passes, leg_fail_counts = 0, {}
        for i in checkpoints:
            ok, detail = capability_proxy(df.iloc[: i + 1])
            passes += ok
            for k, v in detail.items():
                if isinstance(v, bool) and not v:
                    leg_fail_counts[k] = leg_fail_counts.get(k, 0) + 1
        rate = passes / len(checkpoints) if checkpoints else 0.0
        top_blockers = sorted(leg_fail_counts.items(), key=lambda kv: -kv[1])[:2]
        rows[t] = {
            "pass_rate": round(rate, 2),
            "qualifies": rate >= QUALIFY_RATE,
            "checkpoints": len(checkpoints),
            "top_blockers": ", ".join(f"{k}({v})" for k, v in top_blockers),
        }
        print(f"{t:<6} pass_rate={rate:.0%} ({passes}/{len(checkpoints)})  "
              f"blockers: {rows[t]['top_blockers'] or '—'}", flush=True)

    vd = pd.DataFrame(rows).T
    vd.to_csv(OUT / "screen_verdicts.csv")

    baseline = pd.read_csv(OUT / "baseline.csv")
    baseline["qualifies"] = baseline["ticker"].map(lambda t: bool(rows.get(t, {}).get("qualifies", False)))

    print("\n=== performance split by screen qualification (default config) ===")
    for strat in ("elias_engine", "naive_covered_call", "buy_and_hold"):
        sub = baseline[baseline.strategy == strat]
        for label, grp in (("QUALIFY", sub[sub.qualifies]), ("EXCLUDE", sub[~sub.qualifies])):
            if len(grp):
                print(f"{strat:<20} {label}: n={len(grp):2d}  "
                      f"median_return={grp.total_return.median():+.1%}  "
                      f"median_sharpe={grp.sharpe.median():+.2f}")

    qualified = [t for t, v in rows.items() if v["qualifies"]]
    print(f"\nqualified: {', '.join(qualified) or 'none'}")
    if qualified:
        piv = baseline[baseline.ticker.isin(qualified)].pivot(
            index="ticker", columns="strategy", values="total_return"
        )
        piv["elias_minus_naive"] = piv["elias_engine"] - piv["naive_covered_call"]
        print("\n=== qualified head-to-head (total_return) ===")
        print(piv.round(3).to_string())
        print(f"\nMEDIAN elias-naive on qualified: {piv['elias_minus_naive'].median():+.3f}")
    print("\ndone")


if __name__ == "__main__":
    main()
