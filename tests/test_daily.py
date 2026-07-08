from datetime import timedelta
from pathlib import Path

import numpy as np
import pytest

from optionstrader.daily import run_daily
from optionstrader.data.provider import DataProvider, OptionQuote
from optionstrader.portfolio import OpenShort, Portfolio, Position, StockLot

from conftest import make_ohlcv


def range_frame(base=20.0, n=280, end=None):
    closes = []
    for _ in range(10):
        closes += list(np.linspace(base * 0.95, base * 1.1, 14)) + list(np.linspace(base * 1.1, base * 0.95, 14))
    closes = closes[:n]
    if end is not None:
        closes[-1] = end
    return make_ohlcv(closes, volumes=[1_000_000.0] * n)


class DailyStub(DataProvider):
    """Holding HLD trading ~20 with a cheap short call; index available."""

    def __init__(self):
        self.frames = {
            "HLD": range_frame(20.0),
            "^GSPC": range_frame(4000.0),
            "WCH": range_frame(8.0),
        }
        self.today = self.frames["HLD"].index[-1].date()

    def daily_ohlcv(self, ticker, lookback_days=300):
        return self.frames[ticker.upper()]

    def option_expirations(self, ticker):
        return [self.today + timedelta(days=40)]

    def option_chain(self, ticker, expiry):
        # The open short call trades at 0.20 (<= 25% of 1.00 collected).
        return [OptionQuote(strike=22.5, expiry=expiry, kind="call",
                            bid=0.15, ask=0.20, open_interest=300, volume=10, iv=0.4)]

    def next_earnings_date(self, ticker):
        return self.today + timedelta(days=30)


def make_portfolio(tmp_path: Path, stub: DailyStub) -> Portfolio:
    pf = Portfolio(path=tmp_path / "pf.json")
    pos = Position(ticker="HLD", willing_to_add=True)
    pos.lots.append(StockLot("2026-01-05", 1000, 19.0))
    pos.open_shorts.append(OpenShort(
        kind="call", strike=22.5, expiry=(stub.today + timedelta(days=40)).isoformat(),
        contracts=10, premium_collected=1.00, opened="2026-06-01",
    ))
    pf.positions["HLD"] = pos
    return pf


def test_daily_report_buyback_alert(tmp_path):
    stub = DailyStub()
    report = run_daily(make_portfolio(tmp_path, stub), stub, watchlist=["WCH"])
    h = report.holdings[0]
    assert h.ticker == "HLD" and h.error is None
    assert any("buy back now" in a for a in h.alerts)
    assert any("HLD" in item and "buy back" in item for item in report.action_items)


def test_daily_report_earnings_countdown_and_cd(tmp_path):
    stub = DailyStub()
    report = run_daily(make_portfolio(tmp_path, stub), stub)
    h = report.holdings[0]
    assert h.days_to_earnings == 30
    assert h.cd_state in ("neutral", "sell_defend", "buy_strength")


def test_daily_stop_breach_flagged(tmp_path):
    stub = DailyStub()
    stub.frames["HLD"] = range_frame(20.0, end=15.0)   # close 15 vs 19 cost = -21%
    report = run_daily(make_portfolio(tmp_path, stub), stub)
    h = report.holdings[0]
    assert h.stop_breached
    assert any("sell and replace" in a for a in report.action_items)
    # Stop breach must outrank ordinary state-machine actions.
    assert "sell and replace" in report.action_items[0] or "buy back" in report.action_items[0]


def test_daily_expired_short_housekeeping(tmp_path):
    stub = DailyStub()
    pf = make_portfolio(tmp_path, stub)
    pf.positions["HLD"].open_shorts[0].expiry = (stub.today - timedelta(days=3)).isoformat()
    report = run_daily(pf, stub)
    assert any("EXPIRED" in a for a in report.holdings[0].alerts)
    assert any("record the outcome" in i for i in report.action_items)


def test_daily_watchlist_scan_runs(tmp_path):
    stub = DailyStub()
    report = run_daily(make_portfolio(tmp_path, stub), stub, watchlist=["WCH", "HLD"])
    assert report.scanned == 1  # HLD excluded: already held


def test_open_shorts_persist_roundtrip(tmp_path):
    path = tmp_path / "pf.json"
    pf = Portfolio(path=path)
    pos = pf.get("TEST")
    pos.open_shorts.append(OpenShort("put", 17.5, "2026-09-18", 5, 0.80, "2026-07-01"))
    pf.save()
    loaded = Portfolio.load(path)
    o = loaded.get("TEST").open_shorts[0]
    assert o.kind == "put" and o.strike == 17.5 and o.contracts == 5
    assert o.premium_collected == pytest.approx(0.80)
