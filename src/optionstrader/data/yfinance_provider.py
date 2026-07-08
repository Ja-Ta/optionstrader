"""Default data provider backed by yfinance (delayed data; fine for EOD workflow)."""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from .provider import DataProvider, OptionQuote


class YFinanceProvider(DataProvider):
    def __init__(self) -> None:
        import yfinance  # deferred so the engine/tests work offline

        self._yf = yfinance

    def daily_ohlcv(self, ticker: str, lookback_days: int = 300) -> pd.DataFrame:
        df = self._yf.Ticker(ticker).history(period=f"{lookback_days}d", auto_adjust=True)
        if df.empty:
            raise ValueError(f"no price data for {ticker!r}")
        df = df.rename(
            columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
        )[["open", "high", "low", "close", "volume"]]
        df.index = pd.to_datetime(df.index).tz_localize(None)
        return df

    def option_expirations(self, ticker: str) -> list[date]:
        raw = self._yf.Ticker(ticker).options or ()
        return [datetime.strptime(s, "%Y-%m-%d").date() for s in raw]

    def option_chain(self, ticker: str, expiry: date) -> list[OptionQuote]:
        chain = self._yf.Ticker(ticker).option_chain(expiry.isoformat())

        def _f(x) -> float:
            try:
                v = float(x)
                return v if v == v else 0.0  # NaN -> 0
            except (TypeError, ValueError):
                return 0.0

        quotes: list[OptionQuote] = []
        for kind, frame in (("call", chain.calls), ("put", chain.puts)):
            for row in frame.itertuples():
                quotes.append(
                    OptionQuote(
                        strike=_f(row.strike),
                        expiry=expiry,
                        kind=kind,
                        bid=_f(row.bid),
                        ask=_f(row.ask),
                        open_interest=int(_f(row.openInterest)),
                        volume=int(_f(row.volume)),
                        iv=_f(getattr(row, "impliedVolatility", 0.0)),
                        last=_f(getattr(row, "lastPrice", 0.0)),
                    )
                )
        return quotes

    def next_earnings_date(self, ticker: str) -> date | None:
        try:
            cal = self._yf.Ticker(ticker).calendar
            dates = cal.get("Earnings Date") if isinstance(cal, dict) else None
            if dates:
                d = dates[0]
                return d if isinstance(d, date) else pd.Timestamp(d).date()
        except Exception:
            pass
        return None
