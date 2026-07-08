"""Earnings-calendar override using Finnhub's free tier.

Yahoo's earnings calendar is the least reliable part of the yfinance feed;
Finnhub's is solid and free (register at finnhub.io, set FINNHUB_API_KEY).
This wrapper delegates everything to the inner provider and only replaces
next_earnings_date, falling back to the inner provider on any failure.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import date, timedelta

import pandas as pd

from .provider import DataProvider, OptionQuote


class FinnhubEarningsWrapper(DataProvider):
    def __init__(self, inner: DataProvider, api_key: str, horizon_days: int = 120) -> None:
        self.inner = inner
        self.api_key = api_key
        self.horizon_days = horizon_days

    # --- delegated ---

    def daily_ohlcv(self, ticker: str, lookback_days: int = 300) -> pd.DataFrame:
        return self.inner.daily_ohlcv(ticker, lookback_days)

    def option_expirations(self, ticker: str) -> list[date]:
        return self.inner.option_expirations(ticker)

    def option_chain(self, ticker: str, expiry: date) -> list[OptionQuote]:
        return self.inner.option_chain(ticker, expiry)

    # --- overridden ---

    def next_earnings_date(self, ticker: str) -> date | None:
        try:
            start = date.today()
            params = urllib.parse.urlencode({
                "from": start.isoformat(),
                "to": (start + timedelta(days=self.horizon_days)).isoformat(),
                "symbol": ticker.upper(),
                "token": self.api_key,
            })
            url = f"https://finnhub.io/api/v1/calendar/earnings?{params}"
            with urllib.request.urlopen(url, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            entries = sorted(
                (e for e in data.get("earningsCalendar", []) if e.get("date")),
                key=lambda e: e["date"],
            )
            if entries:
                return date.fromisoformat(entries[0]["date"])
        except Exception:  # noqa: BLE001 — degrade to the inner provider
            pass
        return self.inner.next_earnings_date(ticker)
