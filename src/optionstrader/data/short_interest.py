"""Short-interest data (free) — feeds the book's monthly squeeze screen.

Source: Yahoo statistics via yfinance's info payload (sharesShort,
sharesShortPriorMonth, shortRatio = days-to-cover, dateShortInterest).
Free and sufficient for the book's screen: biggest month-over-month
short-interest increases with rising days-to-cover.

Swappable: implement ShortInterestProvider against FINRA's equity
short-interest files (published twice monthly, free with registration)
or a paid feed, and pass it wherever the screen needs it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class ShortInterest:
    ticker: str
    shares_short: int | None
    shares_short_prior_month: int | None
    days_to_cover: float | None       # shortRatio: shares short / avg daily volume
    pct_of_float: float | None
    as_of: date | None

    @property
    def rising(self) -> bool | None:
        """Month-over-month short interest increasing — the squeeze precondition."""
        if self.shares_short is None or self.shares_short_prior_month in (None, 0):
            return None
        return self.shares_short > self.shares_short_prior_month

    @property
    def change_pct(self) -> float | None:
        if self.shares_short is None or not self.shares_short_prior_month:
            return None
        return self.shares_short / self.shares_short_prior_month - 1.0


class ShortInterestProvider(ABC):
    @abstractmethod
    def get(self, ticker: str) -> ShortInterest | None:
        ...


def parse_short_info(ticker: str, info: dict) -> ShortInterest | None:
    """Pure parser for Yahoo-style statistics payloads (testable offline)."""
    if not info:
        return None
    raw_date = info.get("dateShortInterest")
    as_of = None
    if raw_date:
        try:
            as_of = datetime.fromtimestamp(int(raw_date)).date()
        except (ValueError, TypeError, OSError):
            pass
    shares = info.get("sharesShort")
    prior = info.get("sharesShortPriorMonth")
    if shares is None and prior is None and info.get("shortRatio") is None:
        return None
    return ShortInterest(
        ticker=ticker.upper(),
        shares_short=int(shares) if shares else None,
        shares_short_prior_month=int(prior) if prior else None,
        days_to_cover=float(info["shortRatio"]) if info.get("shortRatio") else None,
        pct_of_float=float(info["shortPercentOfFloat"]) if info.get("shortPercentOfFloat") else None,
        as_of=as_of,
    )


class YFinanceShortInterest(ShortInterestProvider):
    def __init__(self) -> None:
        import yfinance

        self._yf = yfinance

    def get(self, ticker: str) -> ShortInterest | None:
        try:
            info = self._yf.Ticker(ticker).get_info()
        except Exception:  # noqa: BLE001
            return None
        return parse_short_info(ticker, info or {})
