"""SQLite-backed caching + retry wrapper for any DataProvider.

Wraps an inner provider and adds three behaviors:
  1. CACHE   — responses stored in SQLite with per-kind TTLs, so repeated
               commands (screen + daily + analyze in one afternoon) don't
               re-fetch the same data.
  2. RETRY   — transient fetch failures retried with backoff before failing.
  3. STALE   — if the inner provider fails outright but an expired cached
               copy exists, serve the stale copy (marked in logs) instead of
               going dark. This keeps the scheduled daily run alive through
               upstream outages/rate limits.

Configuration (env):
  OPTIONSTRADER_CACHE_DB   cache file path (default .cache/optionstrader.db)
  OPTIONSTRADER_NO_CACHE   set to any value to bypass caching entirely
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import asdict
from datetime import date, datetime
from io import StringIO
from pathlib import Path

import pandas as pd

from .provider import DataProvider, OptionQuote

DEFAULT_TTLS = {
    "ohlcv": 3600,          # 1h — long enough for one session's commands, short enough to catch the close
    "expirations": 43200,   # 12h
    "chain": 600,           # 10min — quotes go stale fast
    "earnings": 43200,      # 12h
}


class CachedProvider(DataProvider):
    def __init__(
        self,
        inner: DataProvider,
        db_path: Path | None = None,
        ttls: dict | None = None,
        retries: int = 3,
        backoff: float = 0.75,
        sleep=time.sleep,
    ) -> None:
        self.inner = inner
        self.ttls = {**DEFAULT_TTLS, **(ttls or {})}
        self.retries = retries
        self.backoff = backoff
        self._sleep = sleep
        path = db_path or Path(os.environ.get("OPTIONSTRADER_CACHE_DB", ".cache/optionstrader.db"))
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, payload TEXT, updated REAL)"
        )
        self._db.commit()

    # --- store ---

    def _get(self, key: str) -> tuple[str | None, float]:
        row = self._db.execute("SELECT payload, updated FROM cache WHERE key = ?", (key,)).fetchone()
        return (row[0], row[1]) if row else (None, 0.0)

    def _put(self, key: str, payload: str) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO cache (key, payload, updated) VALUES (?, ?, ?)",
            (key, payload, time.time()),
        )
        self._db.commit()

    def _fetch(self, kind: str, key: str, fetch, encode, decode):
        payload, updated = self._get(key)
        if payload is not None and time.time() - updated <= self.ttls[kind]:
            return decode(payload)
        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
                value = fetch()
                fresh_payload = encode(value)
                self._put(key, fresh_payload)
                # Round-trip even fresh fetches so cached and fresh results
                # are always identical (e.g. DataFrame index freq is dropped
                # by serialization — callers must never depend on it).
                return decode(fresh_payload)
            except Exception as e:  # noqa: BLE001 — provider errors are heterogeneous
                last_error = e
                if attempt < self.retries - 1:
                    self._sleep(self.backoff * (attempt + 1))
        if payload is not None:  # stale grace: better yesterday's data than none
            print(f"[cache] {key}: provider failed ({last_error}); serving STALE copy")
            return decode(payload)
        raise last_error  # type: ignore[misc]

    # --- DataProvider interface ---

    def daily_ohlcv(self, ticker: str, lookback_days: int = 300) -> pd.DataFrame:
        def decode(p: str) -> pd.DataFrame:
            df = pd.read_json(StringIO(p), orient="split")
            df.index = pd.to_datetime(df.index).tz_localize(None)
            return df

        return self._fetch(
            "ohlcv",
            f"ohlcv:{ticker.upper()}:{lookback_days}",
            lambda: self.inner.daily_ohlcv(ticker, lookback_days),
            lambda df: df.to_json(orient="split", date_format="iso"),
            decode,
        )

    def option_expirations(self, ticker: str) -> list[date]:
        return self._fetch(
            "expirations",
            f"expirations:{ticker.upper()}",
            lambda: self.inner.option_expirations(ticker),
            lambda ds: json.dumps([d.isoformat() for d in ds]),
            lambda p: [date.fromisoformat(s) for s in json.loads(p)],
        )

    def option_chain(self, ticker: str, expiry: date) -> list[OptionQuote]:
        def decode(p: str) -> list[OptionQuote]:
            out = []
            for d in json.loads(p):
                d["expiry"] = date.fromisoformat(d["expiry"])
                out.append(OptionQuote(**d))
            return out

        return self._fetch(
            "chain",
            f"chain:{ticker.upper()}:{expiry.isoformat()}",
            lambda: self.inner.option_chain(ticker, expiry),
            lambda qs: json.dumps([{**asdict(q), "expiry": q.expiry.isoformat()} for q in qs]),
            decode,
        )

    def next_earnings_date(self, ticker: str) -> date | None:
        return self._fetch(
            "earnings",
            f"earnings:{ticker.upper()}",
            lambda: self.inner.next_earnings_date(ticker),
            lambda d: json.dumps(d.isoformat() if d else None),
            lambda p: (lambda v: date.fromisoformat(v) if v else None)(json.loads(p)),
        )
