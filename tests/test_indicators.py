import numpy as np

from optionstrader.indicators import (
    add_cmf,
    add_moving_averages,
    classify_cmf,
    evaluate_1030,
    evaluate_102030,
)
from optionstrader.indicators.cmf import CmfBand, is_shakeout_flow
from optionstrader.indicators.moving_averages import SlopeClass, TrendState

from conftest import make_ohlcv


def test_moving_average_columns(trending_up):
    df = add_moving_averages(trending_up)
    assert {"ma10", "ema20", "ema30"} <= set(df.columns)
    assert df["ma10"].notna().sum() > 100


def test_uptrend_alignment_and_slope(trending_up):
    df = add_moving_averages(trending_up)
    t = evaluate_102030(df)
    assert t.trend == TrendState.UPTREND
    assert t.ma10_slope in (SlopeClass.UP, SlopeClass.STEEP_UP)


def test_1030_upcross_detected():
    # Downtrend then sharp reversal — MA10 should cross above MA30 somewhere;
    # verify state at the end: fast above slow.
    closes = [20 - 0.1 * i for i in range(60)] + [14 + 0.2 * i for i in range(40)]
    df = make_ohlcv(closes)
    result = evaluate_1030(df["close"])
    assert result.fast_above


def test_cmf_sign_tracks_close_position():
    # Closes pinned at the high of each bar -> strong positive CMF.
    n = 60
    closes = [10 + 0.05 * i for i in range(n)]
    df = make_ohlcv(closes)
    df["high"] = df["close"]          # close at the high
    df["low"] = df["close"] * 0.97
    df = add_cmf(df)
    assert df["cmf"].iloc[-1] > 0.5


def test_cmf_bands():
    assert classify_cmf(0.25) == CmfBand.HEAVY_ACCUMULATION
    assert classify_cmf(0.05) == CmfBand.WEAK_BUYING
    assert classify_cmf(-0.05) == CmfBand.WEAK_SELLING
    assert classify_cmf(-0.2) == CmfBand.HEAVY_DISTRIBUTION
    assert classify_cmf(-0.6) == CmfBand.EXTREME_DISTRIBUTION
    assert is_shakeout_flow(-0.08)
    assert not is_shakeout_flow(-0.15)
