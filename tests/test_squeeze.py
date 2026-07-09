from datetime import date, timedelta

import numpy as np

from optionstrader.data.provider import DataProvider, OptionQuote
from optionstrader.data.short_interest import ShortInterest, ShortInterestProvider
from optionstrader.scanner import assess_squeeze, screen_squeeze

from conftest import make_ohlcv


def si(shares=80_000_000, prior=60_000_000, dtc=4.5):
    return ShortInterest("TEST", shares, prior, dtc, 0.12, date(2026, 6, 15))


def accumulation_frame():
    """Downtrend then a fresh upturn: MA cross, closes pinned near highs
    (positive CMF flip) — the book's 'price surge point'."""
    closes = list(np.linspace(6.0, 3.5, 120)) + list(np.linspace(3.5, 4.4, 25))
    df = make_ohlcv(closes)
    n = len(closes)
    # Final stretch closes at the bar highs -> strongly positive CMF.
    df.iloc[-30:, df.columns.get_loc("high")] = df["close"].iloc[-30:].values
    df.iloc[-30:, df.columns.get_loc("low")] = df["close"].iloc[-30:].values * 0.96
    df.iloc[-30:, df.columns.get_loc("volume")] = 2_000_000.0
    return df


def weak_flow_uptrend():
    """Price grinding up but closing at the lows of each bar -> negative CMF."""
    closes = list(np.linspace(4.0, 5.5, 145))
    df = make_ohlcv(closes)
    df.iloc[-40:, df.columns.get_loc("low")] = df["close"].iloc[-40:].values
    df.iloc[-40:, df.columns.get_loc("high")] = df["close"].iloc[-40:].values * 1.05
    return df


def test_candidate_on_surge_point():
    r = assess_squeeze("TEST", accumulation_frame(), si())
    assert r.verdict == "candidate"
    assert any("accumulation" in x for x in r.reasons)


def test_eliminate_when_si_not_building():
    r = assess_squeeze("TEST", accumulation_frame(), si(shares=60_000_000, prior=62_000_000))
    assert r.verdict == "eliminate"
    assert any("not building" in x for x in r.reasons)


def test_eliminate_low_days_to_cover():
    r = assess_squeeze("TEST", accumulation_frame(), si(dtc=0.8))
    assert r.verdict == "eliminate"
    assert any("days-to-cover" in x for x in r.reasons)


def test_eliminate_ma_up_without_flow():
    r = assess_squeeze("TEST", weak_flow_uptrend(), si())
    assert r.verdict == "eliminate"
    assert any("without money flow" in x for x in r.reasons)


def test_watch_on_shakeout_drop():
    # Sharp 12% drop with closes mid-range (CMF near zero) = shake-out watch.
    closes = list(np.linspace(4.0, 5.5, 140)) + list(np.linspace(5.5, 4.8, 5))
    r = assess_squeeze("TEST", make_ohlcv(closes), si())
    assert r.verdict == "watch"
    assert any("shake-out" in x for x in r.reasons)


def test_eliminate_distribution_drop():
    # Sharp drop with closes pinned at the lows -> CMF < -0.1: shorts are right.
    closes = list(np.linspace(4.0, 5.5, 140)) + list(np.linspace(5.5, 4.8, 5))
    df = make_ohlcv(closes)
    df.iloc[-25:, df.columns.get_loc("low")] = df["close"].iloc[-25:].values
    df.iloc[-25:, df.columns.get_loc("high")] = df["close"].iloc[-25:].values * 1.06
    r = assess_squeeze("TEST", df, si())
    assert r.verdict == "eliminate"
    assert any("shorts are right" in x for x in r.reasons)


def test_no_si_data_eliminates():
    r = assess_squeeze("TEST", accumulation_frame(), None)
    assert r.verdict == "eliminate"


# --- full screen with plays attached ---

class SqueezeStub(DataProvider):
    def __init__(self):
        self.df = accumulation_frame()
        self.today = date.today()

    def daily_ohlcv(self, ticker, lookback_days=300):
        return self.df

    def option_expirations(self, ticker):
        return [self.today + timedelta(days=d) for d in (60, 100, 130)]

    def option_chain(self, ticker, expiry):
        spot = float(self.df["close"].iloc[-1])   # ~4.4
        quotes = []
        for k in (2.5, 5.0, 7.5, 10.0):
            quotes.append(OptionQuote(k, expiry, "put",
                                      bid=round(max(k - spot, 0) + 0.45, 2),
                                      ask=round(max(k - spot, 0) + 0.55, 2),
                                      open_interest=500, volume=20, iv=0.8))
            call_price = 0.15 if k >= 7.5 else 0.60
            quotes.append(OptionQuote(k, expiry, "call", bid=call_price - 0.05,
                                      ask=call_price, open_interest=500, volume=20, iv=0.8))
        return quotes

    def next_earnings_date(self, ticker):
        return self.today + timedelta(days=25)


class StubSI(ShortInterestProvider):
    def get(self, ticker):
        return si()


def test_screen_attaches_itm_put_and_earnings_call():
    reports = screen_squeeze(["NXTL"], SqueezeStub(), si_provider=StubSI())
    r = reports[0]
    assert r.verdict == "candidate"
    assert r.itm_put is not None and r.itm_put.strike == 5.0        # nearest ITM above ~4.4
    assert r.itm_put.intrinsic > 0 and r.itm_put.time_value >= 0
    assert r.earnings_call is not None and r.earnings_call.ask <= 0.20
    assert r.earnings_call.strike == 7.5                            # cheapest ≤ $0.20 strike
    assert "ladder" in r.summary()


def test_screen_ranks_candidates_first():
    class MixedSI(ShortInterestProvider):
        def get(self, ticker):
            return si() if ticker == "GOOD" else si(shares=50_000_000, prior=60_000_000)

    reports = screen_squeeze(["BAD", "GOOD"], SqueezeStub(), si_provider=MixedSI())
    assert reports[0].ticker == "GOOD" and reports[0].verdict == "candidate"
    assert reports[1].verdict == "eliminate"
