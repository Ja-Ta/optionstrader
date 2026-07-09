"""Chapter-18 short-term toolkit (docs/04 §7) — pure per-ticker arithmetic.

Role per the book: patterns and indicators decide WHETHER to trade; these
numbers decide WHEN and WHERE. They surface as annotations on scanner hits,
as the short-term account's block in the daily report (the mirror image of
CD for the long-term account), and behind `analyze --short-term`.

  five-day oscillator   is the short-term trend on (0-30 bearish, >70 bullish;
                        for NEW buys want low readings turning up)
  three-day difference  how far the move will carry (large + = strong;
                        shrinking + = rally fading)
  strength index        which day to enter (close position within day range)
  buy/sell envelopes    computed price targets, valid ~5 trading days, with
                        four mechanical management rules; sell numbers are
                        commonly touched only intraday -> limit orders at the
                        envelope HIGH
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


def five_day_oscillator(df: pd.DataFrame) -> float:
    """(A + B) x 100 / (2 x (5d high - 5d low));
    A = 5-day high - open 5 days ago, B = last close - 5-day low."""
    w = df.tail(5)
    hi, lo = float(w["high"].max()), float(w["low"].min())
    if hi == lo:
        return 50.0
    a = hi - float(w["open"].iloc[0])
    b = float(w["close"].iloc[-1]) - lo
    return (a + b) * 100.0 / (2.0 * (hi - lo))


def oscillator_series(df: pd.DataFrame, tail: int = 10) -> list[float]:
    """Oscillator for each of the last `tail` days (needs tail+4 rows)."""
    out = []
    for i in range(len(df) - tail, len(df)):
        if i >= 4:
            out.append(five_day_oscillator(df.iloc[: i + 1]))
    return out


def three_day_difference(df: pd.DataFrame) -> float | None:
    """Today's oscillator minus the oscillator 3 days ago."""
    series = oscillator_series(df, tail=4)
    if len(series) < 4:
        return None
    return series[-1] - series[0]


def strength_index(df: pd.DataFrame) -> float:
    """(close - low) x 100 / (high - low) for the last bar."""
    r = df.iloc[-1]
    rng = float(r["high"]) - float(r["low"])
    if rng == 0:
        return 50.0
    return (float(r["close"]) - float(r["low"])) * 100.0 / rng


def band(reading: float) -> str:
    """0-30 bearish, 30-70 neutral, >70 bullish. For HOLDING decisions;
    new BUYS want bearish-and-turning-up readings (buy the start, not the top)."""
    if reading > 70:
        return "bullish"
    if reading < 30:
        return "bearish"
    return "neutral"


@dataclass
class Envelope:
    """Buy/sell targets for the NEXT session(s), from the last 4 completed bars.
    Valid ~5 trading days — recalculate after that."""
    buy_number: float
    sell_number: float
    sell_envelope_high: float   # P3S — the limit-sell tactic level
    valid_days: int = 5


def compute_envelope(df: pd.DataFrame) -> Envelope | None:
    """Four-point buy/sell envelopes (docs/04 §7). Needs >= 4 rows."""
    if len(df) < 4:
        return None
    w = df.tail(4)
    high, low, close = w["high"], w["low"], w["close"]
    h, l, c = float(high.iloc[-1]), float(low.iloc[-1]), float(close.iloc[-1])
    a = (h + l + c) / 3.0

    bbn = (low.diff().dropna()).mean()                    # low - prior low, last 3
    dn = (high.shift(1) - low).dropna().mean()            # prior high - low
    ban = (high.diff().dropna()).mean()                   # high - prior high
    rn = (high - low.shift(1)).dropna().mean()            # high - prior low

    buy_points = [2 * a - h, l, l - bbn, l - dn]
    p3s = h + ban
    sell_points = [2 * a - l, h, p3s, l + rn]
    return Envelope(
        buy_number=sum(buy_points) / 4.0,
        sell_number=sum(sell_points) / 4.0,
        sell_envelope_high=p3s,
    )


@dataclass
class ShortTermView:
    oscillator: float
    oscillator_band: str
    three_day_diff: float | None
    strength: float
    envelope: Envelope | None

    def lines(self) -> list[str]:
        out = [
            f"five-day oscillator {self.oscillator:.0f} ({self.oscillator_band})"
            + (f", 3-day diff {self.three_day_diff:+.0f}" if self.three_day_diff is not None else "")
            + f", strength {self.strength:.0f}"
        ]
        if self.envelope:
            e = self.envelope
            out.append(
                f"envelope (valid ~{e.valid_days}d): buy {e.buy_number:.2f} / sell {e.sell_number:.2f}"
                f" — limit sells at the envelope high {e.sell_envelope_high:.2f} (touched intraday)"
            )
        return out


def assess_short_term(df: pd.DataFrame) -> ShortTermView:
    osc = five_day_oscillator(df)
    return ShortTermView(
        oscillator=osc,
        oscillator_band=band(osc),
        three_day_diff=three_day_difference(df),
        strength=strength_index(df),
        envelope=compute_envelope(df),
    )


def timing_line(df: pd.DataFrame) -> str:
    """Compact one-line annotation for scanner hits."""
    return "; ".join(assess_short_term(df).lines())


def manage_five_day(df: pd.DataFrame) -> list[str]:
    """The envelope management rules for a HELD short-term position.

    Targets come from the 4 bars BEFORE today; today's bar is judged against
    them. Returns action strings (empty = hold within plan).
    """
    if len(df) < 5:
        return []
    env = compute_envelope(df.iloc[:-1])
    if env is None:
        return []
    today = df.iloc[-1]
    close, high = float(today["close"]), float(today["high"])
    signals: list[str] = []
    if close < env.buy_number:
        signals.append(
            f"closed {close:.2f} below the buy number {env.buy_number:.2f} — exit next day (envelope rule 3)"
        )
    elif high > env.sell_number and close < env.sell_number:
        signals.append(
            f"broke the sell number {env.sell_number:.2f} intraday (high {high:.2f}) but closed below — "
            "exit (envelope rule 2)"
        )
    elif close > env.sell_number:
        signals.append(
            f"closed above the sell number {env.sell_number:.2f} — recalculate targets and hold (envelope rule 4)"
        )
    return signals
