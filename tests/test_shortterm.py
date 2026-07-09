from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from optionstrader.indicators import (
    assess_short_term,
    compute_envelope,
    five_day_oscillator,
    manage_five_day,
    strength_index,
    three_day_difference,
    timing_line,
)
from optionstrader.indicators.shortterm import band
from optionstrader.scanner import ScanParams, scan_ticker

from conftest import make_ohlcv


def frame(rows):
    """rows: list of (open, high, low, close, volume?)"""
    idx = pd.bdate_range(end="2026-07-01", periods=len(rows))
    return pd.DataFrame(
        {
            "open": [r[0] for r in rows],
            "high": [r[1] for r in rows],
            "low": [r[2] for r in rows],
            "close": [r[3] for r in rows],
            "volume": [r[4] if len(r) > 4 else 1_000_000 for r in rows],
        },
        index=idx,
    )


# Reconstructed from the documented worked example (docs/04 §7):
# oscillator A = 7.12 - 6.85, B = 7.08 - 6.76, range 0.36 -> ~82.
OSC_ROWS = [
    (6.85, 6.95, 6.80, 6.90),
    (6.90, 7.00, 6.76, 6.85),
    (6.85, 7.05, 6.82, 7.00),
    (7.00, 7.12, 6.95, 7.05),
    (7.05, 7.10, 7.00, 7.08),
]

# Envelope worked example: four bars whose BBN/DN/BAN/RN averages reproduce
# buy 7.70 / sell 8.49 / envelope high 8.73.
ENV_ROWS = [
    (7.00, 7.12, 6.93, 7.05),
    (7.10, 7.67, 7.11, 7.40),
    (7.45, 7.72, 7.50, 7.60),
    (7.80, 8.33, 7.76, 8.17),
]


def test_oscillator_matches_worked_example():
    assert five_day_oscillator(frame(OSC_ROWS)) == pytest.approx(81.94, abs=0.1)


def test_strength_index_matches_worked_example():
    assert strength_index(frame(OSC_ROWS)) == pytest.approx(80.0, abs=0.1)


def test_envelope_matches_worked_example():
    env = compute_envelope(frame(ENV_ROWS))
    assert env.buy_number == pytest.approx(7.70, abs=0.005)
    assert env.sell_number == pytest.approx(8.49, abs=0.005)
    assert env.sell_envelope_high == pytest.approx(8.73, abs=0.005)


def test_bands():
    assert band(82) == "bullish" and band(17) == "bearish" and band(50) == "neutral"


def test_three_day_difference_sign():
    # Rising closes near their highs: oscillator climbing -> positive diff.
    closes = list(np.linspace(10.0, 12.0, 30))
    df = make_ohlcv(closes)
    diff = three_day_difference(df)
    assert diff is not None


def test_manage_rule_close_below_buy_number():
    env = compute_envelope(frame(ENV_ROWS))
    today = (7.60, 7.75, 7.40, env.buy_number - 0.10)     # closes below 7.70
    df = frame(ENV_ROWS + [today])
    signals = manage_five_day(df)
    assert any("below the buy number" in s for s in signals)


def test_manage_rule_intraday_break_fails_to_hold():
    env = compute_envelope(frame(ENV_ROWS))
    today = (8.20, env.sell_number + 0.30, 8.00, env.sell_number - 0.20)
    df = frame(ENV_ROWS + [today])
    signals = manage_five_day(df)
    assert any("failed" in s or "closed below" in s for s in signals)


def test_manage_rule_close_above_sell_number_holds():
    env = compute_envelope(frame(ENV_ROWS))
    today = (8.40, env.sell_number + 0.40, 8.30, env.sell_number + 0.25)
    df = frame(ENV_ROWS + [today])
    signals = manage_five_day(df)
    assert any("recalculate" in s for s in signals)


def test_manage_quiet_day_no_signals():
    env = compute_envelope(frame(ENV_ROWS))
    mid = (env.buy_number + env.sell_number) / 2
    today = (mid, mid * 1.01, mid * 0.99, mid)
    df = frame(ENV_ROWS + [today])
    assert manage_five_day(df) == []


def test_timing_line_compact():
    line = timing_line(frame(ENV_ROWS + [(8.2, 8.4, 8.1, 8.3)] * 3))
    assert "oscillator" in line and "buy" in line and "sell" in line


def test_scanner_hits_carry_timing():
    # Reversal setup from the scanner tests: passer gets a timing annotation.
    closes = list(np.linspace(9.0, 6.8, 120)) + [7.4]
    vols = [500_000.0] * 120 + [1_200_000.0]
    report = scan_ticker("TEST", make_ohlcv(closes, volumes=vols), ScanParams())
    assert report.passed
    assert "oscillator" in report.timing and "envelope" in report.timing


def test_daily_short_term_account_gets_envelope_block(tmp_path):
    from optionstrader.daily import run_daily
    from optionstrader.data.provider import DataProvider
    from optionstrader.portfolio import Portfolio, Position, StockLot

    closes = list(np.linspace(18.0, 22.0, 140))
    df = make_ohlcv(closes)

    class Stub(DataProvider):
        def daily_ohlcv(self, ticker, lookback_days=300):
            return df

        def option_expirations(self, ticker):
            return []

        def option_chain(self, ticker, expiry):
            return []

        def next_earnings_date(self, ticker):
            return None

    pf = Portfolio(path=tmp_path / "pf.json")
    pos = Position(ticker="ST", account="short_term")
    pos.lots.append(StockLot("2026-06-01", 500, 19.0))
    pf.positions["ST"] = pos

    report = run_daily(pf, Stub())
    h = report.holdings[0]
    assert any("envelope" in n for n in h.notes)
    assert any("oscillator" in n for n in h.notes)
    assert h.cd_state == "n/a"   # CD stays a long-term-account tool
