"""Measure what CD gating adds: re-run EliasEngine with the index series on
the full sweep universe and compare against the saved baseline (no-CD elias,
naive covered calls, buy-and-hold from backtests/baseline.csv).

Usage: .venv/bin/python scripts/run_cd_validation.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from optionstrader.backtest import EliasEngine, run_backtest  # noqa: E402
from optionstrader.data.yfinance_provider import YFinanceProvider  # noqa: E402

UNIVERSE = [
    "AMD", "NVDA", "TSLA", "PLTR", "COIN", "MARA",
    "AAPL", "MSFT", "AMZN", "XOM", "FCX",
    "F", "INTC", "PFE", "T", "KO",
]
DAYS = 750
OUT = Path(__file__).resolve().parents[1] / "backtests"


def main() -> None:
    provider = YFinanceProvider()
    index_df = provider.daily_ohlcv("^GSPC", lookback_days=DAYS + 50)
    index_close = index_df["close"]

    rows = []
    for t in UNIVERSE:
        try:
            df = provider.daily_ohlcv(t, lookback_days=DAYS)
            r = run_backtest(df, EliasEngine(willing_to_add=True, index_close=index_close, cd_exits=False))
            cd_trades = sum(1 for tr in r.trades if "CD" in tr.detail)
            rows.append({"ticker": t, **r.metrics, "cd_actions": cd_trades})
            print(f"{t:<6} return={r.metrics['total_return']:+.1%}  sharpe={r.metrics['sharpe']:+.2f}  "
                  f"cd_actions={cd_trades}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"{t}: ERROR {e}", flush=True)
    cd = pd.DataFrame(rows).set_index("ticker")
    cd.to_csv(OUT / "cd_gate_only.csv")

    baseline = pd.read_csv(OUT / "baseline.csv")
    piv_r = baseline.pivot(index="ticker", columns="strategy", values="total_return")
    piv_s = baseline.pivot(index="ticker", columns="strategy", values="sharpe")

    cmp = pd.DataFrame({
        "elias_noCD": piv_r["elias_engine"],
        "elias_gate": cd["total_return"],
        "naive": piv_r["naive_covered_call"],
        "buyhold": piv_r["buy_and_hold"],
        "sharpe_noCD": piv_s["elias_engine"],
        "sharpe_gate": cd["sharpe"],
        "sharpe_naive": piv_s["naive_covered_call"],
    })
    cmp["gate_minus_nocd"] = cmp["elias_gate"] - cmp["elias_noCD"]
    cmp["gate_minus_naive"] = cmp["elias_gate"] - cmp["naive"]
    cmp = cmp.sort_values("gate_minus_nocd", ascending=False)
    cmp.to_csv(OUT / "cd_gate_vs_baseline.csv")

    print("\n=== CD-gated vs baseline (total_return) ===")
    print(cmp.round(3).to_string())
    print("\nMEDIANS:")
    print(cmp.median().round(3).to_string())
    improved = int((cmp["gate_minus_nocd"] > 0.01).sum())
    worse = int((cmp["gate_minus_nocd"] < -0.01).sum())
    print(f"\ntickers improved by CD gating: {improved}, worsened: {worse}, "
          f"~unchanged: {len(cmp) - improved - worse}")


if __name__ == "__main__":
    main()
