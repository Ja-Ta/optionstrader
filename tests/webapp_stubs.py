"""Shared helpers for webapp tests: app factory wiring + stub providers.

Kept separate from conftest.py so the core test fixtures stay untouched.
Import fastapi lazily — callers guard with pytest.importorskip("fastapi").
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np

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


class StubProvider(DataProvider):
    """Holding HLD ~20 with a cheap short call; index and watch ticker available."""

    def __init__(self):
        self.frames = {
            "HLD": range_frame(20.0),
            "^GSPC": range_frame(4000.0),
            "WCH": range_frame(8.0),
        }
        self.today = self.frames["HLD"].index[-1].date()

    def daily_ohlcv(self, ticker, lookback_days=300):
        t = ticker.upper()
        if t not in self.frames:
            raise KeyError(f"no data for {ticker}")
        return self.frames[t]

    def option_expirations(self, ticker):
        return [self.today + timedelta(days=40), self.today + timedelta(days=70)]

    def option_chain(self, ticker, expiry):
        # The open short call trades at 0.20 (<= 25% of the 1.00 collected).
        return [
            OptionQuote(strike=22.5, expiry=expiry, kind="call",
                        bid=0.15, ask=0.20, open_interest=300, volume=10, iv=0.4),
            OptionQuote(strike=18.0, expiry=expiry, kind="put",
                        bid=0.55, ask=0.65, open_interest=250, volume=15, iv=0.4),
            OptionQuote(strike=17.0, expiry=expiry, kind="put",
                        bid=0.35, ask=0.45, open_interest=200, volume=12, iv=0.4),
        ]

    def next_earnings_date(self, ticker):
        return self.today + timedelta(days=30)


def seed_portfolio(path: Path, expiry: date | None = None) -> Portfolio:
    """One holding (HLD, 1000 sh @ 19) with 10 short 22.5 calls — saved to path."""
    expiry = expiry or (date(2026, 7, 1) + timedelta(days=40))
    pf = Portfolio(path=path)
    pos = Position(ticker="HLD", willing_to_add=True)
    pos.lots.append(StockLot("2026-01-05", 1000, 19.0))
    pos.open_shorts.append(OpenShort(
        kind="call", strike=22.5, expiry=expiry.isoformat(),
        contracts=10, premium_collected=1.00, opened="2026-06-01",
    ))
    pf.positions["HLD"] = pos
    pf.save()
    return pf


def make_client(tmp_path: Path, provider: DataProvider | None = None, sync_jobs: bool = True):
    """TestClient wired to a tmp portfolio/reports dir and a stub provider."""
    from fastapi.testclient import TestClient

    from optionstrader.webapp.app import create_app
    from optionstrader.webapp.deps import get_data_provider
    from optionstrader.webapp.services.jobs import JobRegistry
    from optionstrader.webapp.settings import UISettings

    settings = UISettings(
        portfolio_path=tmp_path / "pf.json",
        reports_dir=tmp_path / "reports",
    )
    jobs = JobRegistry(executor="sync" if sync_jobs else "thread")
    app = create_app(settings, jobs=jobs)
    stub = provider or StubProvider()
    app.dependency_overrides[get_data_provider] = lambda: stub
    client = TestClient(app)
    client.stub = stub  # convenient handle for tests
    return client
