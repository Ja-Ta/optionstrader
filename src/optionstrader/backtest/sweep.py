"""Multi-ticker sweeps and Calibrated-threshold grid search (Tier 4).

Tunes ONLY `Calibrated` parameters (thresholds the book states qualitatively).
`BookRules` values are the spec and are never swept here.
"""

from __future__ import annotations

import dataclasses
import itertools

import pandas as pd

from ..config import DEFAULT, Config
from .engine import run_backtest
from .pricing import SyntheticPricer
from .strategies import BuyAndHold, EliasEngine, NaiveCoveredCall


def make_config(**calib_overrides) -> Config:
    return Config(calib=dataclasses.replace(DEFAULT.calib, **calib_overrides))


def run_baseline(
    data: dict[str, pd.DataFrame],
    cash: float = 100_000.0,
    pricer: SyntheticPricer | None = None,
) -> pd.DataFrame:
    """All three strategies on every ticker with default config."""
    rows = []
    for ticker, df in data.items():
        for make in (
            lambda: BuyAndHold(),
            lambda: NaiveCoveredCall(),
            lambda: EliasEngine(willing_to_add=True),
        ):
            strat = make()
            r = run_backtest(df, strat, initial_cash=cash, pricer=pricer or SyntheticPricer())
            rows.append({"ticker": ticker, "strategy": r.strategy, **r.metrics})
    return pd.DataFrame(rows)


def run_grid(
    data: dict[str, pd.DataFrame],
    grid_axes: dict[str, list],
    cash: float = 100_000.0,
    pricer: SyntheticPricer | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """EliasEngine over the cartesian product of Calibrated overrides.

    Returns (per-run detail, per-combo aggregate ranked by median Sharpe).
    """
    keys = list(grid_axes)
    rows = []
    for values in itertools.product(*grid_axes.values()):
        overrides = dict(zip(keys, values))
        cfg = make_config(**overrides)
        for ticker, df in data.items():
            r = run_backtest(
                df,
                EliasEngine(willing_to_add=True, cfg=cfg),
                initial_cash=cash,
                pricer=pricer or SyntheticPricer(),
            )
            rows.append({**overrides, "ticker": ticker, **r.metrics})
    detail = pd.DataFrame(rows)
    agg = (
        detail.groupby(keys)
        .agg(
            median_sharpe=("sharpe", "median"),
            median_return=("total_return", "median"),
            mean_return=("total_return", "mean"),
            worst_drawdown=("max_drawdown", "min"),
            median_net_premium=("net_premium", "median"),
            median_trades=("n_trades", "median"),
        )
        .reset_index()
        .sort_values(["median_sharpe", "median_return"], ascending=False)
    )
    return detail, agg


def excess_vs(baseline: pd.DataFrame, strategy: str, benchmark: str, metric: str = "total_return") -> pd.DataFrame:
    """Per-ticker excess of `strategy` over `benchmark` on `metric`."""
    a = baseline[baseline.strategy == strategy].set_index("ticker")[metric]
    b = baseline[baseline.strategy == benchmark].set_index("ticker")[metric]
    out = (a - b).rename(f"{strategy}_minus_{benchmark}").to_frame()
    out[strategy] = a
    out[benchmark] = b
    return out.sort_values(out.columns[0], ascending=False)
