"""Per-position decision state machine (docs/03 §4).

Evaluation is priority-ordered: premium-management triggers and event hygiene
fire before trend states; the shake-out check fires before the breakdown check
(a sharp drop with weak money flow must NOT be treated as a breakdown).

All rule references are to docs/04-key-rules-reference.md.
"""

from __future__ import annotations

from ..config import Config, DEFAULT
from ..indicators.moving_averages import SlopeClass, TrendState
from ..indicators.cmf import CmfBand
from .states import Action, Assessment, PositionState, Snapshot, ShortOptionView


def _premium_triggers(snap: Snapshot, cfg: Config) -> tuple[list[Action], list[str]]:
    """Standing triggers checked in every state (docs/04 §1-3)."""
    actions: list[Action] = []
    notes: list[str] = []
    b = cfg.book
    for so in snap.short_options:
        # 25% buy-back rule — always.
        if so.current_price is not None and so.current_price <= b.buyback_fraction * so.premium_collected:
            act = Action.BUY_BACK_CALLS if so.kind == "call" else Action.BUY_BACK_PUTS
            if act not in actions:
                actions.append(act)
            notes.append(
                f"short {so.kind} {so.strike}: at {so.current_price:.2f} ≤ 25% of "
                f"{so.premium_collected:.2f} collected — buy back (75% captured)"
            )
        # Assignment watch: ≥ 3/4 point ITM and ≤ 2 weeks to expiry.
        itm = (snap.price - so.strike) if so.kind == "call" else (so.strike - snap.price)
        dte = (so.expiry - snap.as_of).days
        if itm >= b.itm_exercise_points and dte <= b.exercise_window_days:
            if Action.ROLL_OR_ACCEPT_ASSIGNMENT not in actions:
                actions.append(Action.ROLL_OR_ACCEPT_ASSIGNMENT)
            notes.append(
                f"short {so.kind} {so.strike}: {itm:.2f} ITM with {dte}d left — "
                "assignment likely; roll or accept per plan"
            )
    # Event hygiene: close threatened shorts before earnings/FOMC.
    if snap.short_options and snap.days_to_next_event is not None:
        if snap.days_to_next_event <= cfg.calib.event_close_window_days:
            if Action.CLOSE_SHORTS_BEFORE_EVENT not in actions:
                actions.append(Action.CLOSE_SHORTS_BEFORE_EVENT)
            notes.append(
                f"binary event in {snap.days_to_next_event}d — close short options that "
                "could gap through their strike"
            )
    return actions, notes


def _call_sale_gates(snap: Snapshot, cfg: Config) -> list[str]:
    """Gates that must pass before selling covered calls. Returns blockers."""
    blockers: list[str] = []
    b = cfg.book
    if snap.shares_held <= 0:
        blockers.append("no shares held — covered calls require the underlying")
    if snap.pct_above_20d_low < b.post_crash_bounce:
        blockers.append(
            f"stock only {snap.pct_above_20d_low:.0%} above its 20-day low "
            f"(rule: ≥ {b.post_crash_bounce:.0%} before selling calls after weakness)"
        )
    open_call_shares = sum(
        so.contracts * 100 for so in snap.short_options if so.kind == "call"
    )
    if open_call_shares >= snap.shares_held > 0:
        blockers.append("calls already sold against full share count — never go naked")
    return blockers


def assess(snap: Snapshot, cfg: Config = DEFAULT) -> Assessment:
    actions, notes = _premium_triggers(snap, cfg)
    c = cfg.calib

    # --- state classification (priority order) ---

    # Shake-out BEFORE breakdown: sharp drop with CMF inside ±0.1 bands = hold.
    sharp_drop = snap.drop_pct_window <= -c.shakeout_drop_pct
    if sharp_drop and abs(snap.cmf) <= cfg.book.cmf_band:
        state = PositionState.SHAKEOUT
        notes.append(
            f"{snap.drop_pct_window:.0%} drop with CMF {snap.cmf:+.2f} inside ±0.1 — "
            "shake-out signature, not distribution: HOLD, watch for re-entry"
        )
        if not actions:
            actions.append(Action.HOLD)
        return Assessment(state, actions, notes)

    # Confirmed breakdown: MA(10) below EMA(20) with heavy distribution.
    if snap.ma10_crossed_down_ema20 and snap.cmf_band in (
        CmfBand.HEAVY_DISTRIBUTION,
        CmfBand.EXTREME_DISTRIBUTION,
    ):
        state = PositionState.BREAKDOWN
        notes.append("MA(10) crossed below EMA(20) with CMF < −0.1 — confirmed breakdown")
        if snap.shares_held > 0:
            actions.append(Action.DEFENSIVE_CALL_LADDER)
            notes.append(
                "defense: sell calls at nearest strike, roll down as it falls; "
                "stock exit on long-term (CD) confirmation [Tier 2]"
            )
        return Assessment(state, actions, notes)

    # Range: flat MA(10) — MA signals invalid, boxing mode.
    if snap.ma10_slope == SlopeClass.FLAT:
        state = PositionState.RANGE_BOUND
        notes.append(
            "flat MA(10): 102030 signals invalid — use volume + double top/bottom; "
            "boxing mode (calls near resistance, puts near support)"
        )
        if snap.volume.fade_on_rise or snap.volume.failed_prior_high:
            blockers = _call_sale_gates(snap, cfg)
            if not blockers and snap.nearest_resistance:
                actions.append(Action.SELL_COVERED_CALLS)
                notes.append(
                    f"momentum fading near resistance {snap.nearest_resistance:.2f} — "
                    "sell calls one strike above it"
                )
            notes.extend(blockers)
        if not actions:
            actions.append(Action.NO_ACTION)
        return Assessment(state, actions, notes)

    # Approaching support with momentum turning up.
    near_support = (
        snap.nearest_support is not None
        and snap.price <= snap.nearest_support * 1.05
    )
    if near_support and snap.ma10_crossed_up_ema20:
        state = PositionState.APPROACHING_SUPPORT
        if Action.BUY_BACK_CALLS not in actions and any(
            so.kind == "call" for so in snap.short_options
        ):
            actions.append(Action.BUY_BACK_CALLS)
            notes.append("upturn at support — take profit on short calls")
        if snap.willing_to_add:
            actions.append(Action.SELL_PUTS)
            notes.append(
                f"sell puts one strike below support {snap.nearest_support:.2f} "
                "(gate passed: willing to add; 1030/102030 upturn)"
            )
        else:
            notes.append("not flagged willing-to-add — no put sale")
        if not actions:
            actions.append(Action.HOLD)
        return Assessment(state, actions, notes)

    # Uptrend: strong vs fading.
    if snap.trend == TrendState.UPTREND:
        fade_signals = sum(
            [
                snap.volume.fade_on_rise,
                snap.ma10_slope in (SlopeClass.DOWN, SlopeClass.STEEP_DOWN),
                snap.volume.failed_prior_high,
            ]
        )
        if fade_signals >= 1:
            state = PositionState.UPTREND_FADING
            blockers = _call_sale_gates(snap, cfg)
            notes.append(f"{fade_signals}/3 momentum-fade signals present")
            if not blockers:
                actions.append(Action.SELL_COVERED_CALLS)
                if snap.nearest_resistance:
                    notes.append(
                        f"sell calls one strike above resistance {snap.nearest_resistance:.2f}"
                    )
            else:
                notes.extend(blockers)
                if not actions:
                    actions.append(Action.HOLD)
        else:
            state = PositionState.UPTREND_STRONG
            notes.append("momentum intact — no new calls; let the stock run")
            if not actions:
                actions.append(Action.HOLD)
        return Assessment(state, actions, notes)

    # Fallback.
    state = PositionState.INSUFFICIENT_DATA if snap.trend == TrendState.MIXED else PositionState.RANGE_BOUND
    if not actions:
        actions.append(Action.NO_ACTION)
    notes.append("mixed/unclear trend — the book: no clear signal, no trade")
    return Assessment(state, actions, notes)


def validate_order(
    snap: Snapshot,
    kind: str,
    side: str,
    contracts: int,
    cfg: Config = DEFAULT,
) -> list[str]:
    """Standing constraints (docs/04 §1-2). Returns violations; empty = OK.

    kind: "call" | "put"; side: "sell" | "buy".
    """
    violations: list[str] = []
    if side != "sell":
        return violations
    shares = contracts * 100
    if kind == "call":
        open_calls = sum(
            so.contracts * 100 for so in snap.short_options if so.kind == "call"
        )
        if open_calls + shares > snap.shares_held:
            violations.append(
                f"NAKED CALL: {open_calls + shares} call-shares vs {snap.shares_held} held — forbidden"
            )
    if kind == "put":
        open_puts = sum(
            so.contracts * 100 for so in snap.short_options if so.kind == "put"
        )
        limit = cfg.book.max_put_share_multiple * max(snap.shares_held, 0)
        if snap.shares_held > 0 and open_puts + shares > limit:
            violations.append(
                f"puts on {open_puts + shares} shares exceed 2× held ({snap.shares_held}) — "
                "book cap for owned stock"
            )
        if not snap.willing_to_add:
            violations.append("put sale requires willingness to own at the strike")
    return violations
