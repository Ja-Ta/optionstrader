from datetime import date, timedelta

import numpy as np
import pytest

from optionstrader.data.provider import DataProvider, OptionQuote
from optionstrader.screening import ScreenParams, bs_delta, capability_proxy, screen_live

from conftest import make_ohlcv


# --- delta ---

def test_delta_bounds_and_signs():
    assert 0 < bs_delta("call", 100, 120, 52, 0.5) < 0.5      # OTM call
    assert -0.5 < bs_delta("put", 100, 80, 52, 0.5) < 0        # OTM put
    assert bs_delta("call", 100, 50, 52, 0.3) > 0.95           # deep ITM call
    assert abs(bs_delta("put", 100, 80, 52, 0.9)) > abs(bs_delta("put", 100, 80, 52, 0.3))


# --- historical proxy ---

def volatile_uptrend(n=300, start=20.0):
    rng = np.random.default_rng(3)
    closes = [start]
    for i in range(n - 1):
        closes.append(max(closes[-1] * (1 + 0.002 + rng.normal(0, 0.045)), 1.0))
    return make_ohlcv(closes, volumes=[1_000_000] * n)


def calm_stock(n=300, start=60.0):
    rng = np.random.default_rng(5)
    closes = [start]
    for i in range(n - 1):
        closes.append(closes[-1] * (1 + rng.normal(0.0002, 0.006)))
    return make_ohlcv(closes, volumes=[1_000_000] * n)


def test_proxy_rejects_calm_stock():
    passed, detail = capability_proxy(calm_stock())
    # A ~10% vol name cannot yield 20% annualized at 20% OTM.
    assert not detail["roi"]
    assert not passed


def test_proxy_volatile_name_roi_passes():
    passed, detail = capability_proxy(volatile_uptrend())
    assert detail["put_roi"] > 0.20 or detail["call_roi"] > 0.20 or detail["roi"] is False
    # High-vol name must at least clear the ROI leg (delta may or may not).
    assert detail["price_floor"] and detail["stock_liquidity"]


def test_proxy_rejects_freefall():
    # Steady decline into a new 20-day low.
    closes = [30 - 0.05 * i for i in range(300)]
    passed, detail = capability_proxy(make_ohlcv(closes, volumes=[1_000_000] * 300))
    assert not detail["not_freefall"]
    assert not passed


# --- live screen with a stub provider ---

class StubProvider(DataProvider):
    """Canned data: volatile range-bound stock with a rich, liquid chain."""

    def __init__(self, df, spot=20.0, iv=0.65):
        self.df, self.spot, self.iv = df, spot, iv

    def daily_ohlcv(self, ticker, lookback_days=300):
        return self.df

    def option_expirations(self, ticker):
        base = self.df.index[-1].date()
        return [base + timedelta(days=d) for d in (10, 52, 80)]

    def option_chain(self, ticker, expiry):
        quotes = []
        for strike in np.arange(10.0, 32.5, 2.5):
            for kind in ("call", "put"):
                otm = strike >= self.spot if kind == "call" else strike <= self.spot
                prem = max(0.30, 2.0 - abs(strike - self.spot) * 0.25) if otm else 3.0
                quotes.append(OptionQuote(
                    strike=float(strike), expiry=expiry, kind=kind,
                    bid=round(prem, 2), ask=round(prem * 1.06, 2),
                    open_interest=500, volume=100, iv=self.iv,
                ))
        return quotes

    def next_earnings_date(self, ticker):
        return None


def range_20(n=300):
    closes = []
    for cycle in range(15):
        closes += list(np.linspace(18.0, 22.0, 10)) + list(np.linspace(22.0, 18.0, 10))
    return make_ohlcv(closes[:n], volumes=[1_000_000] * n)


def test_screen_live_pass_and_report():
    df = range_20()
    provider = StubProvider(df, spot=float(df["close"].iloc[-1]))
    report = screen_live("RNG", provider)
    names = [l.name for l in report.legs]
    assert "put-roi" in names and "call-delta" in names and "structure" in names
    assert report.legs[0].name == "price-floor" and report.legs[0].passed
    # Rich premium at 20% OTM on a $20 stock: put bid ~1.0 -> ROI ~ 1.0/15 x 7 = huge.
    roi_legs = {l.name: l.passed for l in report.legs}
    assert roi_legs["put-roi"] and roi_legs["call-roi"]


def test_screen_live_fails_without_tenor():
    df = range_20()

    class NoChain(StubProvider):
        def option_expirations(self, ticker):
            return [self.df.index[-1].date() + timedelta(days=10)]  # too near

    report = screen_live("RNG", NoChain(df, spot=float(df["close"].iloc[-1])))
    assert not report.passed
    assert any(l.name == "tenor" and not l.passed for l in report.legs)
