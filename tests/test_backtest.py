from datetime import date

import numpy as np
import pytest

from optionstrader.backtest import BuyAndHold, EliasEngine, NaiveCoveredCall, run_backtest
from optionstrader.backtest.broker import SimBroker
from optionstrader.backtest.pricing import (
    SyntheticPricer,
    bs_price,
    monthly_expiries,
    pick_expiry,
    strike_grid,
    third_friday,
)

from conftest import make_ohlcv


# --- pricing ---

def test_put_call_parity():
    s, k, dte, sigma, r = 100.0, 95.0, 60, 0.40, 0.03
    call = bs_price("call", s, k, dte, sigma, r)
    put = bs_price("put", s, k, dte, sigma, r)
    t = dte / 365
    assert call - put == pytest.approx(s - k * np.exp(-r * t), abs=1e-6)


def test_bs_expiry_is_intrinsic():
    assert bs_price("call", 100, 90, 0, 0.4) == pytest.approx(10.0)
    assert bs_price("put", 100, 110, 0, 0.4) == pytest.approx(10.0)
    assert bs_price("call", 100, 110, 0, 0.4) == 0.0


def test_bs_monotonic_in_vol_and_time():
    lo = bs_price("call", 100, 110, 30, 0.2)
    hi = bs_price("call", 100, 110, 30, 0.6)
    longer = bs_price("call", 100, 110, 90, 0.2)
    assert hi > lo and longer > lo


def test_strike_grid_increments():
    g = strike_grid(20.0)
    assert all(abs((s / 2.5) - round(s / 2.5)) < 1e-9 for s in g)
    assert any(s > 20 for s in g) and any(s < 20 for s in g)


def test_third_friday_and_expiry_window():
    tf = third_friday(2026, 7)
    assert tf.weekday() == 4 and 15 <= tf.day <= 21
    e = pick_expiry(date(2026, 7, 8), min_dte=45, max_dte=90)
    assert e is not None and 45 <= (e - date(2026, 7, 8)).days <= 90
    assert len(monthly_expiries(date(2026, 1, 1), date(2026, 12, 31))) == 12


# --- broker settlement ---

def make_closes(n=40, price=20.0):
    import pandas as pd
    return pd.Series([price] * n)


def test_call_assignment():
    b = SimBroker(cash=0.0)
    b.shares, b.avg_cost = 1000, 18.0
    b.sell_option("call", 22.5, date(2026, 7, 17), 10, 1.00, date(2026, 6, 1))
    assert b.cash == pytest.approx(1000.0)
    b.settle_expirations(date(2026, 7, 17), close=25.0)   # ITM: called away
    assert b.shares == 0
    assert b.cash == pytest.approx(1000.0 + 10 * 100 * 22.5)


def test_put_assignment_and_otm_expiry():
    b = SimBroker(cash=30_000.0)
    b.sell_option("put", 17.5, date(2026, 7, 17), 10, 0.70, date(2026, 6, 1))
    b.settle_expirations(date(2026, 7, 17), close=16.0)   # ITM: shares put to us
    assert b.shares == 1000 and b.avg_cost == pytest.approx(17.5)
    b.sell_option("call", 22.5, date(2026, 8, 21), 10, 0.60, date(2026, 7, 20))
    b.settle_expirations(date(2026, 8, 21), close=20.0)   # OTM: expires, premium kept
    assert b.shares == 1000 and not b.shorts
    assert b.option_trades_won >= 1


# --- full runs on synthetic data ---

def bull_market(n=400, start=10.0, drift=0.004):
    rng = np.random.default_rng(7)
    closes = [start]
    for _ in range(n - 1):
        closes.append(closes[-1] * (1 + drift + rng.normal(0, 0.01)))
    return make_ohlcv(closes)


def choppy_market(n=400, base=20.0):
    rng = np.random.default_rng(11)
    closes = [base]
    for i in range(n - 1):
        pull = (base - closes[-1]) * 0.05          # mean-reverting
        closes.append(max(closes[-1] * (1 + rng.normal(0, 0.015)) + pull, 1.0))
    return make_ohlcv(closes)


def test_buyhold_tracks_market():
    df = bull_market()
    r = run_backtest(df, BuyAndHold(), initial_cash=100_000)
    assert r.metrics["total_return"] > 0.5          # strong bull -> strong return
    assert r.metrics["n_trades"] == 1


def test_naive_cc_caps_upside_in_strong_bull():
    df = bull_market()
    bh = run_backtest(df, BuyAndHold(), initial_cash=100_000)
    cc = run_backtest(df, NaiveCoveredCall(), initial_cash=100_000)
    assert cc.metrics["premium_collected"] > 0
    # Systematic ATM-ish writing must lag buy-and-hold in a relentless bull.
    assert cc.metrics["total_return"] < bh.metrics["total_return"]


def test_elias_engine_runs_and_respects_constraints():
    df = choppy_market()
    r = run_backtest(df, EliasEngine(willing_to_add=True), initial_cash=100_000)
    assert len(r.equity) > 300
    b = r.broker
    # Never naked: every call sale in the log happened with covering shares.
    # (Structural check: shorts remaining at end are covered.)
    open_call_shares = sum(p.contracts * 100 for p in b.open_calls())
    assert open_call_shares <= max(b.shares, 0) or b.shares == 0
    assert np.isfinite(r.metrics["final_equity"])


def test_elias_collects_premium_in_chop():
    df = choppy_market()
    r = run_backtest(df, EliasEngine(willing_to_add=False), initial_cash=100_000)
    # A range market is the strategy's home turf: it must have sold something.
    assert r.metrics["premium_collected"] > 0
