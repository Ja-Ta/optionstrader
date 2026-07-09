"""CD-gated exit and re-entry in the backtest engine.

Key property used in constructions: CD = stock/index, so with a FLAT index
CD is proportional to price and the sell tests can never fire (relative
strength equals absolute strength). Divergence requires the index to move.
"""

import numpy as np
import pandas as pd

from optionstrader.backtest import EliasEngine, run_backtest

from conftest import make_ohlcv


def series_from(closes):
    idx = pd.bdate_range(end="2026-07-01", periods=len(closes))
    return pd.Series(np.asarray(closes, dtype=float), index=idx)


def test_flat_index_never_triggers_cd():
    # Stock trends up then corrects; flat index -> CD proportional to price,
    # engine must behave identically to the no-index engine.
    closes = list(np.linspace(10, 14, 200)) + list(np.linspace(14, 12.5, 100))
    df = make_ohlcv(closes)
    flat_index = series_from([4000.0] * 300)
    with_cd = run_backtest(df, EliasEngine(index_close=flat_index, cd_exits=True), initial_cash=100_000)
    without = run_backtest(df, EliasEngine(), initial_cash=100_000)
    assert with_cd.metrics["total_return"] == without.metrics["total_return"]
    assert not any("CD" in t.note if hasattr(t, "note") else "CD" in t.detail for t in with_cd.trades)


def whipsaw_scenario():
    """Stock: uptrend -> crash (stop-out) -> weak bounce while the INDEX
    rallies hard. The bounce produces a surge-point signal, but relative
    strength (CD) is deteriorating — the old engine re-enters, the CD gate
    must refuse."""
    stock = (list(np.linspace(10.0, 13.0, 150))          # uptrend
             + list(np.linspace(13.0, 9.0, 40))          # crash ~ -30% (stop fires)
             + list(np.linspace(9.0, 9.9, 110)))         # weak +10% drift
    index = ([4000.0] * 190
             + list(4000.0 * np.cumprod([1.004] * 110)))  # index rallies ~55%
    return make_ohlcv(stock), series_from(index)


def test_cd_gate_blocks_whipsaw_reentry():
    df, index = whipsaw_scenario()
    gated = run_backtest(df, EliasEngine(index_close=index), initial_cash=100_000)
    ungated = run_backtest(df, EliasEngine(), initial_cash=100_000)

    def reentries(result):
        return [t for t in result.trades if "re-entry" in t.detail]

    # The ungated engine re-enters the weak bounce; the gated one must not
    # (or at minimum strictly fewer times).
    assert len(reentries(ungated)) >= 1, "scenario must produce a surge-point re-entry to be meaningful"
    assert len(reentries(gated)) < len(reentries(ungated))


def test_cd_exit_fires_before_stop():
    """Stock rises strongly vs a flat index, then bleeds slowly (never a
    quick -15% close) while the index rallies — CD sell test (b) fires on the
    down-leg (lower CD at the same price) and the engine exits via CD."""
    stock = (list(np.linspace(10.0, 16.0, 150))          # strong run
             + list(np.linspace(16.0, 13.5, 150)))       # slow bleed, -16% over 7 months
    index = ([4000.0] * 150
             + list(4000.0 * np.cumprod([1.002] * 150)))  # index grinds up ~35%
    df = make_ohlcv(stock)
    result = run_backtest(df, EliasEngine(index_close=series_from(index), cd_exits=True), initial_cash=100_000)
    cd_exits = [t for t in result.trades if "CD exit" in t.detail]
    assert cd_exits, f"expected a CD exit; trades: {[(t.what, t.detail) for t in result.trades]}"


def test_cd_engine_runs_on_realistic_chop():
    rng = np.random.default_rng(23)
    stock, index = [20.0], [4000.0]
    for _ in range(400):
        stock.append(max(stock[-1] * (1 + rng.normal(0, 0.02)) + (20 - stock[-1]) * 0.03, 1.0))
        index.append(index[-1] * (1 + rng.normal(0.0004, 0.008)))
    df = make_ohlcv(stock)
    result = run_backtest(df, EliasEngine(willing_to_add=True, index_close=series_from(index)))
    assert np.isfinite(result.metrics["final_equity"])
    assert result.strategy == "elias_engine_cd_gate"
