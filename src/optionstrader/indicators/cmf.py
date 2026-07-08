"""Chaikin Money Flow — the strategy's SECONDARY/confirming signal (docs/04 §6).

Standard 20-day CMF:
    money-flow multiplier = ((close - low) - (high - close)) / (high - low)
    money-flow volume     = multiplier * volume
    CMF = sum(mfv, 20) / sum(volume, 20)

Band interpretation per the rulebook: ±0.1 accumulation/distribution bands,
with the shake-out signature (sharp drop, CMF inside the bands) as the key case.
"""

from __future__ import annotations

from enum import Enum

import numpy as np
import pandas as pd

from ..config import Config, DEFAULT


class CmfBand(Enum):
    HEAVY_ACCUMULATION = "heavy_accumulation"   # > +0.1: resistance likely breaks, support holds
    WEAK_BUYING = "weak_buying"                 # 0 .. +0.1
    WEAK_SELLING = "weak_selling"               # −0.1 .. 0: during a steep drop = shake-out
    HEAVY_DISTRIBUTION = "heavy_distribution"   # < −0.1: support likely breaks
    EXTREME_DISTRIBUTION = "extreme_distribution"  # ≤ −0.5: never buy "cheap" against this


def add_cmf(df: pd.DataFrame, cfg: Config = DEFAULT) -> pd.DataFrame:
    """Append a 'cmf' column. Expects high/low/close/volume columns."""
    out = df.copy()
    rng = (out["high"] - out["low"]).replace(0, np.nan)
    mult = ((out["close"] - out["low"]) - (out["high"] - out["close"])) / rng
    mfv = (mult * out["volume"]).fillna(0.0)
    period = cfg.book.cmf_period
    out["cmf"] = mfv.rolling(period).sum() / out["volume"].rolling(period).sum()
    return out


def classify_cmf(value: float, cfg: Config = DEFAULT) -> CmfBand:
    band = cfg.book.cmf_band
    if value <= -cfg.book.cmf_extreme:
        return CmfBand.EXTREME_DISTRIBUTION
    if value < -band:
        return CmfBand.HEAVY_DISTRIBUTION
    if value < 0:
        return CmfBand.WEAK_SELLING
    if value <= band:
        return CmfBand.WEAK_BUYING
    return CmfBand.HEAVY_ACCUMULATION


def is_shakeout_flow(value: float, cfg: Config = DEFAULT) -> bool:
    """True when money flow is inside the ±0.1 bands — a sharp price drop with
    this flow is a shake-out (weak hands flushed), NOT distribution. Hold."""
    return abs(value) <= cfg.book.cmf_band
