"""Synthetic OHLCV builders for offline tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def make_ohlcv(closes: list[float], volumes: list[float] | None = None) -> pd.DataFrame:
    """Build a plausible daily OHLCV frame from a close series."""
    n = len(closes)
    closes_arr = np.asarray(closes, dtype=float)
    opens = np.concatenate([[closes_arr[0]], closes_arr[:-1]])
    highs = np.maximum(opens, closes_arr) * 1.01
    lows = np.minimum(opens, closes_arr) * 0.99
    vols = np.asarray(volumes, dtype=float) if volumes is not None else np.full(n, 1_000_000.0)
    idx = pd.bdate_range(end="2026-07-01", periods=n)
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes_arr, "volume": vols},
        index=idx,
    )


@pytest.fixture
def trending_up() -> pd.DataFrame:
    """120 bars: flat base then a steady uptrend."""
    base = [10.0] * 60
    up = [10.0 + 0.08 * i for i in range(1, 61)]
    return make_ohlcv(base + up)


@pytest.fixture
def range_bound() -> pd.DataFrame:
    """120 bars oscillating between ~9 and ~11 — repeated tops/bottoms."""
    closes = []
    for cycle in range(6):
        closes += list(np.linspace(9.0, 11.0, 10)) + list(np.linspace(11.0, 9.0, 10))
    return make_ohlcv(closes)
