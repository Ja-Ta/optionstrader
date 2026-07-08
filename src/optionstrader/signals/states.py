"""Position states and actions — the decision matrix of docs/03 §4 as types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from ..indicators.moving_averages import SlopeClass, TrendState
from ..indicators.cmf import CmfBand
from ..indicators.volume import VolumeSignals


class PositionState(Enum):
    UPTREND_STRONG = "uptrend_strong"          # hold; no new calls; harvest short puts at 25%
    UPTREND_FADING = "uptrend_fading"          # sell covered calls above resistance
    APPROACHING_SUPPORT = "approaching_support"  # buy back calls; sell puts if willing
    BREAKDOWN = "breakdown"                    # defensive call ladder / exit path
    SHAKEOUT = "shakeout"                      # sharp drop, weak flow — HOLD, do not panic
    RANGE_BOUND = "range_bound"                # boxing mode; MA signals invalid
    INSUFFICIENT_DATA = "insufficient_data"


class Action(Enum):
    HOLD = "hold"
    SELL_COVERED_CALLS = "sell_covered_calls"
    SELL_PUTS = "sell_puts"
    BUY_BACK_CALLS = "buy_back_calls"
    BUY_BACK_PUTS = "buy_back_puts"
    DEFENSIVE_CALL_LADDER = "defensive_call_ladder"
    ROLL_OR_ACCEPT_ASSIGNMENT = "roll_or_accept_assignment"
    CLOSE_SHORTS_BEFORE_EVENT = "close_shorts_before_event"
    EXIT_STOCK = "exit_stock"
    NO_ACTION = "no_action"


@dataclass
class ShortOptionView:
    """Minimal view of an open short option for state evaluation."""
    kind: str                    # "call" | "put"
    strike: float
    expiry: date
    contracts: int
    premium_collected: float     # per share
    current_price: float | None = None  # per share, if known


@dataclass
class Snapshot:
    """Everything the state machine needs about one position on one day."""
    ticker: str
    as_of: date
    price: float
    trend: TrendState
    ma10_slope: SlopeClass
    ma10_crossed_up_ema20: bool
    ma10_crossed_down_ema20: bool
    cmf: float
    cmf_band: CmfBand
    volume: VolumeSignals
    drop_pct_window: float               # % change over the shake-out window (negative = drop)
    pct_above_20d_low: float             # for the post-crash call gate
    nearest_support: float | None
    nearest_resistance: float | None
    shares_held: int = 0
    willing_to_add: bool = False         # user flag: would buy more at support strike
    short_options: list[ShortOptionView] = field(default_factory=list)
    days_to_next_event: int | None = None  # earnings/FOMC/ex-div


@dataclass
class Assessment:
    state: PositionState
    actions: list[Action]
    notes: list[str]

    def summary(self) -> str:
        acts = ", ".join(a.value for a in self.actions) or "none"
        lines = [f"state: {self.state.value}", f"actions: {acts}"]
        lines += [f"  - {n}" for n in self.notes]
        return "\n".join(lines)
