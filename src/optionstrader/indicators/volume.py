"""Volume statistics and the momentum-fade / accumulation signals (docs/04 §6).

The three momentum-fade triggers that time covered-call sales:
  1. volume declining while price rises        (this module)
  2. MA(10) curling down                       (moving_averages.py)
  3. failure to exceed the prior day's high    (this module)
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..config import Config, DEFAULT


@dataclass
class VolumeSignals:
    avg_volume: float
    volume_ratio: float           # today's volume / average
    fade_on_rise: bool            # volume falling while price rises (call-sale trigger 1)
    failed_prior_high: bool       # short-term double top (call-sale trigger 3)
    telltale_spike: bool          # accumulation spike (docs/04 §6)
    heavy_down_day: bool          # close down >5% on heavy volume — distribution warning
    correction_volume_shrinking: bool  # volume shrinking on down days — temporary correction signature


def analyze_volume(df: pd.DataFrame, cfg: Config = DEFAULT) -> VolumeSignals:
    """Compute volume signals from a daily OHLCV frame (last row = today)."""
    b, c = cfg.book, cfg.calib
    vol = df["volume"]
    close = df["close"]
    avg = float(vol.rolling(c.volume_avg_period).mean().iloc[-1])
    today_vol = float(vol.iloc[-1])
    ratio = today_vol / avg if avg > 0 else 0.0

    # 1. Fade: price up over the slope window, volume down ≥20% from its recent peak.
    w = c.slope_lookback_days
    price_rising = len(close) > w and close.iloc[-1] > close.iloc[-1 - w]
    recent_peak_vol = float(vol.iloc[-w - 1:-1].max()) if len(vol) > w + 1 else today_vol
    volume_dropping = recent_peak_vol > 0 and today_vol <= recent_peak_vol * (1 - c.fade_volume_drop)
    fade_on_rise = bool(price_rising and volume_dropping)

    # 3. Failure to take out the prior day's high.
    failed_prior_high = bool(
        len(df) >= 2 and df["high"].iloc[-1] <= df["high"].iloc[-2] and price_rising
    )

    # Tell-tale accumulation spike: volume ≥ 20% above average AND close 0–20% above open.
    o = float(df["open"].iloc[-1])
    cl = float(close.iloc[-1])
    close_gain = (cl - o) / o if o > 0 else 0.0
    lo_band, hi_band = b.spike_close_band
    telltale_spike = bool(
        ratio >= b.spike_volume_ratio and lo_band <= close_gain <= hi_band
    )

    # Distribution warning: close down > 5% on heavy volume.
    heavy_down_day = bool(ratio >= b.spike_volume_ratio and close_gain < -b.heavy_down_close)

    # Correction vs reversal: volume shrinking across the last 3 down days = temporary.
    down = df[df["close"] < df["close"].shift(1)].tail(3)
    correction_volume_shrinking = bool(
        len(down) == 3 and down["volume"].is_monotonic_decreasing
    )

    return VolumeSignals(
        avg_volume=avg,
        volume_ratio=ratio,
        fade_on_rise=fade_on_rise,
        failed_prior_high=failed_prior_high,
        telltale_spike=telltale_spike,
        heavy_down_day=heavy_down_day,
        correction_volume_shrinking=correction_volume_shrinking,
    )
