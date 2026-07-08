from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

from optionstrader.data.provider import DataProvider, OptionQuote
from optionstrader.indicators import assess_cd, cd_series
from optionstrader.indicators.cd import normalize_1_10
from optionstrader.options import plan_half_half

from conftest import make_ohlcv


# --- CD chart ---

def daily_index(n, start=4000.0, drift=0.0):
    idx = pd.bdate_range(end="2026-07-01", periods=n)
    vals = start * np.cumprod(1 + np.full(n, drift))
    return pd.Series(vals, index=idx)


def daily_stock(n, path):
    idx = pd.bdate_range(end="2026-07-01", periods=n)
    return pd.Series(path, index=idx)


def test_normalize_lands_in_1_10():
    s = pd.Series([0.00123, 0.00150, 0.00110])
    out = normalize_1_10(s)
    assert 1 <= out.median() < 10


def test_cd_flat_when_stock_tracks_index():
    n = 300
    index = daily_index(n, drift=0.001)
    stock = index / 100.0  # perfectly correlated
    frame = cd_series(stock, index)
    assert frame["cd"].std() / frame["cd"].mean() < 1e-9


def test_cd_sell_signal_price_up_cd_down():
    # Index rises 2x faster than the stock in the final stretch:
    # stock price rises (test a's price leg) while CD falls.
    n = 400
    index_path = [4000.0]
    stock_path = [40.0]
    for i in range(n - 1):
        index_path.append(index_path[-1] * (1 + (0.004 if i > n - 60 else 0.0005)))
        stock_path.append(stock_path[-1] * (1 + (0.001 if i > n - 60 else 0.0005)))
    result = assess_cd(daily_stock(n, stock_path), daily_stock(n, index_path))
    assert result.state == "sell_defend"
    assert any("rising slower" in s for s in result.sell_signals)


def test_cd_buy_signal_new_price_low_without_cd_low():
    # Index collapses harder than the stock at the end: stock makes a new
    # price low, but relative strength (CD) holds above its earlier lows.
    n = 400
    index_path, stock_path = [4000.0], [40.0]
    for i in range(n - 1):
        if i < 200:
            ix_r, st_r = 0.0002, -0.0008     # stock drifts down, CD makes its lows here
        elif i < 340:
            ix_r, st_r = 0.0002, 0.0004      # stock recovers, CD rises
        else:
            ix_r, st_r = -0.0080, -0.0045    # crash: stock falls less than index
        index_path.append(index_path[-1] * (1 + ix_r))
        stock_path.append(stock_path[-1] * (1 + st_r))
    result = assess_cd(daily_stock(n, stock_path), daily_stock(n, index_path))
    assert any("WITHOUT a new CD low" in s for s in result.buy_signals)


# --- half/half planner ---

class PlanStub(DataProvider):
    """Range-bound $20 stock with supports near 18 and levels below, plus a
    liquid put chain at 2.5-point strikes."""

    def __init__(self):
        closes = []
        for _ in range(8):
            closes += list(np.linspace(21.5, 18.0, 18)) + list(np.linspace(18.0, 21.5, 18))
        closes = closes[:280] + [18.4]  # end near support
        self.df = make_ohlcv(closes, volumes=[1_000_000] * len(closes))

    def daily_ohlcv(self, ticker, lookback_days=300):
        return self.df

    def option_expirations(self, ticker):
        base = self.df.index[-1].date()
        return [base + timedelta(days=d) for d in (20, 55, 85, 120)]

    def option_chain(self, ticker, expiry):
        out = []
        for k in np.arange(10.0, 27.5, 2.5):
            prem = max(0.10, 1.6 - abs(18.4 - k) * 0.35)
            out.append(OptionQuote(strike=float(k), expiry=expiry, kind="put",
                                   bid=round(prem, 2), ask=round(prem * 1.08, 2),
                                   open_interest=400, volume=50, iv=0.5))
        return out

    def next_earnings_date(self, ticker):
        return None


def test_planner_builds_two_tranches():
    plan = plan_half_half("RNG", PlanStub(), target_shares=1200)
    assert len(plan.tranches) == 2
    t1, t2 = plan.tranches
    assert t1.contracts == 6 and t2.contracts == 6
    assert t2.strike < t1.strike                       # tranche 2 below tranche 1
    assert t1.strike < 18.5                            # below the ~18 support zone
    assert t1.effective_cost == pytest.approx(t1.strike - t1.est_premium)
    assert plan.blended_effective_cost < t1.strike     # premium lowers blended cost


def test_planner_ready_near_support():
    plan = plan_half_half("RNG", PlanStub(), target_shares=1000)
    # Price 18.4 with strike just below support — should be actionable.
    assert plan.ready


def test_planner_cash_gate():
    plan = plan_half_half("RNG", PlanStub(), target_shares=1200, cash_available=5_000)
    assert not plan.ready
    assert any("exceeds available" in n for n in plan.notes)


def test_planner_rejects_tiny_target():
    plan = plan_half_half("RNG", PlanStub(), target_shares=150)
    assert not plan.tranches
    assert any("at least 1 contract" in n for n in plan.notes)


def test_planner_odd_lots_split():
    plan = plan_half_half("RNG", PlanStub(), target_shares=1100)
    c = [t.contracts for t in plan.tranches]
    assert sum(c) == 11 and c[0] == 5 and c[1] == 6
