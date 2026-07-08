"""Moving-average tests: the strategy's PRIMARY signal (docs/04 §6).

Implements MA(10)/EMA(20)/EMA(30), slope classification, and the 1030 /
102030 crossover tests. CMF (cmf.py) only confirms; these decide.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import pandas as pd

from ..config import Config, DEFAULT


class SlopeClass(Enum):
    STEEP_UP = "steep_up"
    UP = "up"
    FLAT = "flat"          # book: flat MA(10) = NO ACTION; switch to range-mode signals
    DOWN = "down"
    STEEP_DOWN = "steep_down"


class TrendState(Enum):
    UPTREND = "uptrend"        # MA(10) > EMA(20) > EMA(30)
    DOWNTREND = "downtrend"    # EMA(30) > EMA(20) > MA(10)
    MIXED = "mixed"


def add_moving_averages(df: pd.DataFrame, cfg: Config = DEFAULT) -> pd.DataFrame:
    """Append ma10 / ema20 / ema30 columns. Expects a 'close' column."""
    out = df.copy()
    b = cfg.book
    out["ma10"] = out["close"].rolling(b.ma_fast).mean()
    out["ema20"] = out["close"].ewm(span=b.ema_mid, adjust=False).mean()
    out["ema30"] = out["close"].ewm(span=b.ema_slow, adjust=False).mean()
    return out


def classify_slope(series: pd.Series, price: float, cfg: Config = DEFAULT) -> SlopeClass:
    """Classify the recent slope of an MA series as %-of-price per day.

    The book acts only on *steep* MA(10) slope changes and forbids action on a
    flat slope; thresholds are CALIB values (config.py).
    """
    c = cfg.calib
    window = c.slope_lookback_days
    s = series.dropna()
    if len(s) < window + 1 or price <= 0:
        return SlopeClass.FLAT
    pct_per_day = (s.iloc[-1] - s.iloc[-1 - window]) / window / price * 100.0
    if pct_per_day >= c.steep_slope_pct_per_day:
        return SlopeClass.STEEP_UP
    if pct_per_day >= c.flat_slope_pct_per_day:
        return SlopeClass.UP
    if pct_per_day <= -c.steep_slope_pct_per_day:
        return SlopeClass.STEEP_DOWN
    if pct_per_day <= -c.flat_slope_pct_per_day:
        return SlopeClass.DOWN
    return SlopeClass.FLAT


@dataclass
class CrossResult:
    crossed_up: bool
    crossed_down: bool
    fast_above: bool


def _cross(fast: pd.Series, slow: pd.Series) -> CrossResult:
    f, s = fast.dropna(), slow.dropna()
    n = min(len(f), len(s))
    if n < 2:
        return CrossResult(False, False, False)
    f, s = f.iloc[-n:], s.iloc[-n:]
    above_now = f.iloc[-1] > s.iloc[-1]
    above_prev = f.iloc[-2] > s.iloc[-2]
    return CrossResult(
        crossed_up=above_now and not above_prev,
        crossed_down=(not above_now) and above_prev,
        fast_above=bool(above_now),
    )


def evaluate_1030(close: pd.Series, weekly: bool = False) -> CrossResult:
    """1030 test (docs/04 §2): 10-period MA vs 30-period MA.

    crossed_up = the averaging-down / put-selling gate opens.
    Pass weekly resampled closes for long-term holdings.
    """
    if weekly:
        close = close.resample("W").last().dropna()
    ma10 = close.rolling(10).mean()
    ma30 = close.rolling(30).mean()
    return _cross(ma10, ma30)


@dataclass
class Test102030:
    trend: TrendState
    ma10_slope: SlopeClass
    ma10_x_ema20: CrossResult
    ma10_x_ema30: CrossResult

    @property
    def actionable_up(self) -> bool:
        """Steep MA(10) upturn crossing EMA(20) — buy-back-calls / sell-puts trigger."""
        return self.ma10_slope == SlopeClass.STEEP_UP and self.ma10_x_ema20.crossed_up

    @property
    def actionable_down(self) -> bool:
        """Steep MA(10) rollover crossing EMA(20) — sell-calls / defend trigger."""
        return self.ma10_slope == SlopeClass.STEEP_DOWN and self.ma10_x_ema20.crossed_down


def evaluate_102030(df: pd.DataFrame, cfg: Config = DEFAULT) -> Test102030:
    """102030 test (docs/04 §6) on a frame that has ma10/ema20/ema30 columns."""
    if "ma10" not in df.columns:
        df = add_moving_averages(df, cfg)
    last = df.iloc[-1]
    price = float(last["close"])
    if last["ma10"] > last["ema20"] > last["ema30"]:
        trend = TrendState.UPTREND
    elif last["ema30"] > last["ema20"] > last["ma10"]:
        trend = TrendState.DOWNTREND
    else:
        trend = TrendState.MIXED
    return Test102030(
        trend=trend,
        ma10_slope=classify_slope(df["ma10"], price, cfg),
        ma10_x_ema20=_cross(df["ma10"], df["ema20"]),
        ma10_x_ema30=_cross(df["ma10"], df["ema30"]),
    )
