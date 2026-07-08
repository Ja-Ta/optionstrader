"""Multi-ticker baseline sweep + Calibrated-threshold grid search.

Usage: .venv/bin/python scripts/run_sweep.py
Writes CSVs and a summary to backtests/.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from optionstrader.backtest.sweep import excess_vs, make_config, run_baseline, run_grid  # noqa: E402
from optionstrader.backtest import EliasEngine, run_backtest  # noqa: E402
from optionstrader.data.yfinance_provider import YFinanceProvider  # noqa: E402

# Universe: mixed regimes — high-vol momentum, mega-cap, cyclical, cheap
# range-bound, calm dividend. All liquid and optionable with 3y history.
UNIVERSE = [
    "AMD", "NVDA", "TSLA", "PLTR", "COIN", "MARA",       # high volatility
    "AAPL", "MSFT", "AMZN",                              # mega-cap
    "XOM", "FCX",                                        # cyclical
    "F", "INTC", "PFE", "T",                             # cheap / range-bound / decliners
    "KO",                                                # calm control
]
TUNE_SET = ["AMD", "NVDA", "TSLA", "PLTR", "XOM", "F", "INTC", "KO"]  # tuning subset
DAYS = 750
OUT = Path(__file__).resolve().parents[1] / "backtests"
OUT.mkdir(exist_ok=True)

GRID = {
    "steep_slope_pct_per_day": [0.20, 0.30, 0.45],
    "flat_slope_pct_per_day": [0.05, 0.10],
    "fade_volume_drop": [0.15, 0.30],
}


def fetch(tickers: list[str]) -> dict[str, pd.DataFrame]:
    provider = YFinanceProvider()
    data = {}
    for t in tickers:
        try:
            data[t] = provider.daily_ohlcv(t, lookback_days=DAYS)
            print(f"fetched {t}: {len(data[t])} bars", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"SKIP {t}: {e}", flush=True)
    return data


def main() -> None:
    t0 = time.time()
    data = fetch(UNIVERSE)

    print("\n=== Phase A: baseline sweep (default config) ===", flush=True)
    baseline = run_baseline(data)
    baseline.to_csv(OUT / "baseline.csv", index=False)
    pivot_ret = baseline.pivot(index="ticker", columns="strategy", values="total_return")
    pivot_sharpe = baseline.pivot(index="ticker", columns="strategy", values="sharpe")
    print("\ntotal_return by ticker:\n", pivot_ret.round(3).to_string(), flush=True)
    print("\nsharpe by ticker:\n", pivot_sharpe.round(2).to_string(), flush=True)
    ex_naive = excess_vs(baseline, "elias_engine", "naive_covered_call")
    ex_bh = excess_vs(baseline, "elias_engine", "buy_and_hold")
    print("\nelias vs naive-cc (excess total_return):\n", ex_naive.round(3).to_string(), flush=True)
    print(f"\nMEDIAN excess vs naive: {ex_naive.iloc[:, 0].median():+.3f}", flush=True)
    print(f"MEDIAN excess vs buyhold: {ex_bh.iloc[:, 0].median():+.3f}", flush=True)

    print(f"\n=== Phase B: grid search on {TUNE_SET} ({time.time()-t0:.0f}s elapsed) ===", flush=True)
    tune_data = {t: data[t] for t in TUNE_SET if t in data}
    detail, agg = run_grid(tune_data, GRID)
    detail.to_csv(OUT / "grid_detail.csv", index=False)
    agg.to_csv(OUT / "grid_agg.csv", index=False)
    print("\ntop combos by median sharpe:\n", agg.head(6).round(3).to_string(index=False), flush=True)

    best = agg.iloc[0][list(GRID)].to_dict()
    print(f"\nbest combo: {best}", flush=True)

    print(f"\n=== Phase C: validate best combo on full universe ({time.time()-t0:.0f}s) ===", flush=True)
    cfg = make_config(**best)
    rows = []
    for t, df in data.items():
        r = run_backtest(df, EliasEngine(willing_to_add=True, cfg=cfg))
        rows.append({"ticker": t, **r.metrics})
    tuned = pd.DataFrame(rows)
    tuned.to_csv(OUT / "tuned_validation.csv", index=False)

    default_elias = baseline[baseline.strategy == "elias_engine"].set_index("ticker")
    naive = baseline[baseline.strategy == "naive_covered_call"].set_index("ticker")
    cmp = pd.DataFrame(
        {
            "default_return": default_elias["total_return"],
            "tuned_return": tuned.set_index("ticker")["total_return"],
            "naive_return": naive["total_return"],
            "default_sharpe": default_elias["sharpe"],
            "tuned_sharpe": tuned.set_index("ticker")["sharpe"],
            "naive_sharpe": naive["sharpe"],
        }
    )
    cmp["tuned_minus_naive"] = cmp["tuned_return"] - cmp["naive_return"]
    cmp.to_csv(OUT / "tuned_vs_default.csv")
    print("\ntuned vs default vs naive:\n", cmp.round(3).to_string(), flush=True)
    print("\nMEDIANS:", flush=True)
    print(cmp.median().round(3).to_string(), flush=True)
    print(f"\ndone in {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
