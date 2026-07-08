import numpy as np

from optionstrader.scanner import ScanParams, scan_ticker, ten_conditions, triage
from optionstrader.scanner.scanner import _breakaway_gap, _bullish_macd_divergence

from conftest import make_ohlcv


def reversal_setup(final_close=7.4, final_vol=1_200_000):
    """Downtrend 9 -> 6.8 (below EMA20), then a heavy-volume pop above it."""
    closes = list(np.linspace(9.0, 6.8, 120)) + [final_close]
    vols = [500_000.0] * 120 + [float(final_vol)]
    return make_ohlcv(closes, volumes=vols)


def test_ten_conditions_reversal_passes():
    df = reversal_setup()
    c = ten_conditions(df, ScanParams())
    assert all(c.values()), f"failed: {[k for k, v in c.items() if not v]}"


def test_condition_2_price_cap():
    closes = list(np.linspace(15.0, 11.0, 120)) + [12.5]
    df = make_ohlcv(closes, volumes=[500_000.0] * 120 + [1_200_000.0])
    c = ten_conditions(df, ScanParams())
    assert not c["2_price_below_cap"]


def test_condition_9_requires_flip():
    # Steady uptrend: today above stop but yesterday ALSO above -> not a reversal.
    closes = list(np.linspace(6.0, 8.0, 121))
    df = make_ohlcv(closes, volumes=[500_000.0] * 120 + [1_200_000.0])
    c = ten_conditions(df, ScanParams())
    assert not c["9_yesterday_below_stop"]


def test_condition_4_needs_volume_spike():
    df = reversal_setup(final_vol=520_000)  # barely above average
    c = ten_conditions(df, ScanParams())
    assert not c["4_volume_change_over_25pct"]


# --- triage ---

def test_triage_eliminates_runup():
    # Passed-scan shape but +25% in the last 20 days.
    closes = list(np.linspace(9.0, 6.0, 100)) + list(np.linspace(6.0, 7.8, 21))
    df = make_ohlcv(closes, volumes=[500_000.0] * 121)
    t = triage(df)
    assert t.bucket == "eliminate"
    assert any("already ran" in r for r in t.reasons)


def test_macd_divergence_detector():
    # Steep fall to a low, bounce, then a slow retest of the low:
    # histogram at the retest is far above the first-low histogram.
    closes = (list(np.linspace(10.0, 7.0, 25))          # steep drop -> deep negative hist
              + list(np.linspace(7.0, 8.5, 20))         # bounce
              + list(np.linspace(8.5, 7.05, 40)))       # slow retest of the low
    df = make_ohlcv(closes, volumes=[500_000.0] * len(closes))
    assert _bullish_macd_divergence(df)


def test_macd_divergence_absent_in_plain_downtrend():
    closes = list(np.linspace(10.0, 6.0, 85))
    df = make_ohlcv(closes, volumes=[500_000.0] * 85)
    assert not _bullish_macd_divergence(df)


def test_breakaway_gap_detector():
    closes = list(np.linspace(8.0, 7.0, 100))
    df = make_ohlcv(closes, volumes=[500_000.0] * 100)
    # Force a gap on the last bar: open 3% above prior high, heavy volume.
    df.iloc[-1, df.columns.get_loc("open")] = df["high"].iloc[-2] * 1.03
    df.iloc[-1, df.columns.get_loc("high")] = df["open"].iloc[-1] * 1.02
    df.iloc[-1, df.columns.get_loc("volume")] = 2_000_000.0
    assert _breakaway_gap(df)


def test_scan_report_watch_default():
    df = reversal_setup()
    report = scan_ticker("TEST", df, ScanParams())
    assert report.passed
    assert report.bucket in ("watch", "enter")
    assert report.volume_ratio > 2.0
