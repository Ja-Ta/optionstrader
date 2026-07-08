"""Glue: turn raw OHLCV (+ optional position) into a Snapshot and Assessment."""

from __future__ import annotations

from datetime import date

import pandas as pd

from .config import Config, DEFAULT
from .indicators import (
    add_cmf,
    add_moving_averages,
    analyze_volume,
    classify_cmf,
    detect_levels,
    nearest_resistance,
    nearest_support,
    evaluate_102030,
)
from .signals import Assessment, Snapshot, assess
from .signals.states import ShortOptionView


def build_snapshot(
    ticker: str,
    df: pd.DataFrame,
    shares_held: int = 0,
    willing_to_add: bool = False,
    short_options: list[ShortOptionView] | None = None,
    days_to_next_event: int | None = None,
    cfg: Config = DEFAULT,
) -> Snapshot:
    """df: daily OHLCV, ascending index, ≥ ~60 rows recommended."""
    df = add_cmf(add_moving_averages(df, cfg), cfg)
    price = float(df["close"].iloc[-1])
    t = evaluate_102030(df, cfg)
    cmf_val = float(df["cmf"].iloc[-1]) if pd.notna(df["cmf"].iloc[-1]) else 0.0

    w = cfg.calib.shakeout_window_days
    drop_pct = (
        price / float(df["close"].iloc[-1 - w]) - 1.0 if len(df) > w else 0.0
    )
    lb = cfg.book.post_crash_lookback_days
    low_20d = float(df["close"].tail(lb).min())
    pct_above_low = price / low_20d - 1.0 if low_20d > 0 else 0.0

    levels = detect_levels(df, cfg)
    res = nearest_resistance(levels, price)
    sup = nearest_support(levels, price)

    return Snapshot(
        ticker=ticker.upper(),
        as_of=df.index[-1].date() if hasattr(df.index[-1], "date") else date.today(),
        price=price,
        trend=t.trend,
        ma10_slope=t.ma10_slope,
        ma10_crossed_up_ema20=t.ma10_x_ema20.crossed_up,
        ma10_crossed_down_ema20=t.ma10_x_ema20.crossed_down,
        cmf=cmf_val,
        cmf_band=classify_cmf(cmf_val, cfg),
        volume=analyze_volume(df, cfg),
        drop_pct_window=drop_pct,
        pct_above_20d_low=pct_above_low,
        nearest_support=sup.price if sup else None,
        nearest_resistance=res.price if res else None,
        shares_held=shares_held,
        willing_to_add=willing_to_add,
        short_options=short_options or [],
        days_to_next_event=days_to_next_event,
    )


def analyze(ticker: str, df: pd.DataFrame, cfg: Config = DEFAULT, **position_kwargs) -> tuple[Snapshot, Assessment]:
    snap = build_snapshot(ticker, df, cfg=cfg, **position_kwargs)
    return snap, assess(snap, cfg)
