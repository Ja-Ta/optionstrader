"""Pluggable market-data interface.

Everything the Tier-1 engine needs is daily OHLCV plus options chains and an
event calendar. yfinance (delayed data) is the default; a broker API
(Schwab / IBKR / Alpaca / Tradier) can implement the same interface for live
chains later without touching the engine.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date

import pandas as pd


@dataclass
class OptionQuote:
    strike: float
    expiry: date
    kind: str            # "call" | "put"
    bid: float
    ask: float
    open_interest: int
    volume: int
    iv: float = 0.0      # implied volatility (annualized), 0 if unknown
    last: float = 0.0    # last trade price; fallback quote when bid/ask are 0 (closed market)


class DataProvider(ABC):
    @abstractmethod
    def daily_ohlcv(self, ticker: str, lookback_days: int = 300) -> pd.DataFrame:
        """Daily bars, ascending index, columns: open/high/low/close/volume."""

    @abstractmethod
    def option_expirations(self, ticker: str) -> list[date]:
        ...

    @abstractmethod
    def option_chain(self, ticker: str, expiry: date) -> list[OptionQuote]:
        ...

    @abstractmethod
    def next_earnings_date(self, ticker: str) -> date | None:
        ...
