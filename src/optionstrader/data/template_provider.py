"""TEMPLATE — plug your broker or data-vendor API in here.

To integrate a new data source:
  1. Copy this file (e.g. schwab_provider.py) and implement the four methods.
  2. Register it in factory.py's REGISTRY under a short name.
  3. Select it with OPTIONSTRADER_PROVIDER=<name> (or pass name to get_provider).
The caching/retry layer wraps you automatically — implement plain fetches
only; no caching, retry, or rate-limit logic needed here.

Where the data lives on common APIs (as of 2026 — check current docs):
  Schwab       GET /marketdata/v1/pricehistory (OHLCV),
               GET /marketdata/v1/chains (full chain incl. greeks/IV)
  Tradier      GET /v1/markets/history, /v1/markets/options/expirations,
               /v1/markets/options/chains?greeks=true
  Alpaca       GET /v2/stocks/{sym}/bars, /v1beta1/options/snapshots/{sym}
  Polygon      GET /v2/aggs/ticker/{sym}/range/1/day/...,
               GET /v3/snapshot/options/{underlying}
  IBKR WebAPI  /iserver/marketdata/history, /iserver/secdef/strikes + /info

Return-shape contract (the engine depends on these exactly):
  daily_ohlcv      pandas DataFrame, ASCENDING tz-naive DatetimeIndex,
                   float columns open/high/low/close/volume, adjusted for
                   splits (dividends-adjusted preferred).
  option_expirations  list[datetime.date], ascending.
  option_chain     list[OptionQuote]; bid/ask 0.0 when the market is closed
                   is acceptable IF `last` is populated (screen falls back);
                   set `iv` when the vendor provides it (most do) — it feeds
                   delta computation in the capability screen.
  next_earnings_date  next CONFIRMED earnings date, or None. Never guess.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from .provider import DataProvider, OptionQuote

_MSG = (
    "TemplateProvider is a skeleton — implement {method}() for your broker/vendor "
    "(see the docstring at the top of template_provider.py for the contract), "
    "then register the class in factory.py."
)


class TemplateProvider(DataProvider):
    """Skeleton provider: fill in the four methods for your data source."""

    def __init__(self) -> None:
        # Authenticate here: read API keys/tokens from environment variables
        # (never hardcode credentials). e.g.:
        #   self.api_key = os.environ["MYBROKER_API_KEY"]
        pass

    def daily_ohlcv(self, ticker: str, lookback_days: int = 300) -> pd.DataFrame:
        raise NotImplementedError(_MSG.format(method="daily_ohlcv"))

    def option_expirations(self, ticker: str) -> list[date]:
        raise NotImplementedError(_MSG.format(method="option_expirations"))

    def option_chain(self, ticker: str, expiry: date) -> list[OptionQuote]:
        raise NotImplementedError(_MSG.format(method="option_chain"))

    def next_earnings_date(self, ticker: str) -> date | None:
        raise NotImplementedError(_MSG.format(method="next_earnings_date"))
