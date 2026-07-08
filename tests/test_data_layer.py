from datetime import date

import pandas as pd
import pytest

from optionstrader.data import get_provider
from optionstrader.data.cache import CachedProvider
from optionstrader.data.finnhub_earnings import FinnhubEarningsWrapper
from optionstrader.data.provider import DataProvider, OptionQuote
from optionstrader.data.short_interest import parse_short_info
from optionstrader.data.template_provider import TemplateProvider

from conftest import make_ohlcv


class CountingStub(DataProvider):
    def __init__(self):
        self.calls = {"ohlcv": 0, "expirations": 0, "chain": 0, "earnings": 0}
        self.fail_next = 0

    def _maybe_fail(self):
        if self.fail_next > 0:
            self.fail_next -= 1
            raise ConnectionError("simulated outage")

    def daily_ohlcv(self, ticker, lookback_days=300):
        self.calls["ohlcv"] += 1
        self._maybe_fail()
        return make_ohlcv([10.0, 10.5, 11.0])

    def option_expirations(self, ticker):
        self.calls["expirations"] += 1
        self._maybe_fail()
        return [date(2026, 8, 21), date(2026, 9, 18)]

    def option_chain(self, ticker, expiry):
        self.calls["chain"] += 1
        self._maybe_fail()
        return [OptionQuote(strike=10.0, expiry=expiry, kind="put",
                            bid=0.5, ask=0.6, open_interest=100, volume=5, iv=0.4, last=0.55)]

    def next_earnings_date(self, ticker):
        self.calls["earnings"] += 1
        self._maybe_fail()
        return date(2026, 8, 1)


def cached(stub, tmp_path, **kw):
    return CachedProvider(stub, db_path=tmp_path / "cache.db", sleep=lambda s: None, **kw)


def test_cache_avoids_repeat_fetches(tmp_path):
    stub = CountingStub()
    c = cached(stub, tmp_path)
    df1 = c.daily_ohlcv("ABC")
    df2 = c.daily_ohlcv("ABC")
    assert stub.calls["ohlcv"] == 1
    pd.testing.assert_frame_equal(df1, df2)
    c.option_chain("ABC", date(2026, 8, 21))
    q = c.option_chain("ABC", date(2026, 8, 21))[0]
    assert stub.calls["chain"] == 1
    assert q.strike == 10.0 and q.expiry == date(2026, 8, 21) and q.iv == 0.4


def test_cache_key_separation(tmp_path):
    stub = CountingStub()
    c = cached(stub, tmp_path)
    c.daily_ohlcv("ABC")
    c.daily_ohlcv("XYZ")
    c.daily_ohlcv("ABC", lookback_days=500)
    assert stub.calls["ohlcv"] == 3


def test_retry_then_success(tmp_path):
    stub = CountingStub()
    stub.fail_next = 2  # fail twice, succeed on third attempt
    c = cached(stub, tmp_path)
    assert c.next_earnings_date("ABC") == date(2026, 8, 1)
    assert stub.calls["earnings"] == 3


def test_stale_served_on_total_failure(tmp_path):
    stub = CountingStub()
    c = cached(stub, tmp_path, ttls={"expirations": 0})  # every call refetches
    first = c.option_expirations("ABC")
    stub.fail_next = 99
    stale = c.option_expirations("ABC")   # provider down -> stale copy
    assert stale == first


def test_error_raised_when_no_cache_exists(tmp_path):
    stub = CountingStub()
    stub.fail_next = 99
    c = cached(stub, tmp_path)
    with pytest.raises(ConnectionError):
        c.daily_ohlcv("ABC")


def test_earnings_none_is_cached(tmp_path):
    class NoEarnings(CountingStub):
        def next_earnings_date(self, ticker):
            self.calls["earnings"] += 1
            return None

    stub = NoEarnings()
    c = cached(stub, tmp_path)
    assert c.next_earnings_date("ABC") is None
    assert c.next_earnings_date("ABC") is None
    assert stub.calls["earnings"] == 1


# --- short interest parsing ---

def test_parse_short_info_full():
    si = parse_short_info("nxtl", {
        "sharesShort": 86_000_000, "sharesShortPriorMonth": 60_000_000,
        "shortRatio": 4.8, "shortPercentOfFloat": 0.12, "dateShortInterest": 1780000000,
    })
    assert si.ticker == "NXTL" and si.rising and si.days_to_cover == 4.8
    assert si.change_pct == pytest.approx(86 / 60 - 1)


def test_parse_short_info_empty():
    assert parse_short_info("ABC", {}) is None
    si = parse_short_info("ABC", {"shortRatio": 2.0})
    assert si.days_to_cover == 2.0 and si.rising is None


# --- factory & template ---

def test_factory_unknown_name():
    with pytest.raises(ValueError, match="unknown provider"):
        get_provider("nonexistent")


def test_factory_template_uncached():
    p = get_provider("template", cache=False)
    assert isinstance(p, TemplateProvider)
    with pytest.raises(NotImplementedError, match="daily_ohlcv"):
        p.daily_ohlcv("ABC")


def test_factory_default_is_cached(tmp_path, monkeypatch):
    monkeypatch.setenv("OPTIONSTRADER_CACHE_DB", str(tmp_path / "c.db"))
    monkeypatch.delenv("OPTIONSTRADER_NO_CACHE", raising=False)
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    p = get_provider("yfinance")
    assert isinstance(p, CachedProvider)


# --- finnhub wrapper ---

def test_finnhub_overrides_earnings(monkeypatch):
    stub = CountingStub()
    w = FinnhubEarningsWrapper(stub, api_key="k")

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"earningsCalendar": [{"date": "2026-07-28"}, {"date": "2026-10-27"}]}'

    monkeypatch.setattr("urllib.request.urlopen", lambda url, timeout=15: FakeResp())
    assert w.next_earnings_date("ABC") == date(2026, 7, 28)
    assert stub.calls["earnings"] == 0  # inner never consulted


def test_finnhub_falls_back_on_failure(monkeypatch):
    stub = CountingStub()
    w = FinnhubEarningsWrapper(stub, api_key="k")

    def boom(url, timeout=15):
        raise OSError("api down")

    monkeypatch.setattr("urllib.request.urlopen", boom)
    assert w.next_earnings_date("ABC") == date(2026, 8, 1)  # inner's answer
    assert stub.calls["earnings"] == 1
