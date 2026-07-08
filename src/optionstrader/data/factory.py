"""Provider factory — config-driven data-source selection.

Every CLI command gets its provider from here, so switching data sources
never touches engine code:

  OPTIONSTRADER_PROVIDER   provider name (default "yfinance")
  FINNHUB_API_KEY          if set, earnings dates come from Finnhub (free tier)
  OPTIONSTRADER_NO_CACHE   set to disable the SQLite cache/retry layer

To add a broker/vendor: implement DataProvider (start from
template_provider.py) and add one line to REGISTRY below.
"""

from __future__ import annotations

import os

from .provider import DataProvider


def _yfinance() -> DataProvider:
    from .yfinance_provider import YFinanceProvider

    return YFinanceProvider()


def _template() -> DataProvider:
    from .template_provider import TemplateProvider

    return TemplateProvider()


REGISTRY = {
    "yfinance": _yfinance,
    "template": _template,
    # "schwab": _schwab,        <- add yours here
    # "tradier": _tradier,
}


def get_provider(name: str | None = None, cache: bool | None = None) -> DataProvider:
    name = (name or os.environ.get("OPTIONSTRADER_PROVIDER", "yfinance")).lower()
    if name not in REGISTRY:
        raise ValueError(
            f"unknown provider {name!r} — available: {', '.join(sorted(REGISTRY))}. "
            "Implement DataProvider (see data/template_provider.py) and register it "
            "in data/factory.py."
        )
    provider = REGISTRY[name]()

    finnhub_key = os.environ.get("FINNHUB_API_KEY")
    if finnhub_key:
        from .finnhub_earnings import FinnhubEarningsWrapper

        provider = FinnhubEarningsWrapper(provider, finnhub_key)

    if cache is None:
        cache = not os.environ.get("OPTIONSTRADER_NO_CACHE")
    if cache:
        from .cache import CachedProvider

        provider = CachedProvider(provider)
    return provider
