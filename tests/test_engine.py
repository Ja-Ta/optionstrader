from datetime import date

from optionstrader.indicators.cmf import CmfBand
from optionstrader.indicators.moving_averages import SlopeClass, TrendState
from optionstrader.indicators.volume import VolumeSignals
from optionstrader.signals import Action, PositionState, Snapshot, assess, validate_order
from optionstrader.signals.states import ShortOptionView


def make_volume(**overrides) -> VolumeSignals:
    base = dict(
        avg_volume=1e6,
        volume_ratio=1.0,
        fade_on_rise=False,
        failed_prior_high=False,
        telltale_spike=False,
        heavy_down_day=False,
        correction_volume_shrinking=False,
    )
    base.update(overrides)
    return VolumeSignals(**base)


def make_snapshot(**overrides) -> Snapshot:
    base = dict(
        ticker="TEST",
        as_of=date(2026, 7, 1),
        price=20.0,
        trend=TrendState.UPTREND,
        ma10_slope=SlopeClass.UP,
        ma10_crossed_up_ema20=False,
        ma10_crossed_down_ema20=False,
        cmf=0.15,
        cmf_band=CmfBand.HEAVY_ACCUMULATION,
        volume=make_volume(),
        drop_pct_window=0.02,
        pct_above_20d_low=0.30,
        nearest_support=18.0,
        nearest_resistance=23.0,
        shares_held=1000,
        willing_to_add=False,
        short_options=[],
        days_to_next_event=None,
    )
    base.update(overrides)
    return Snapshot(**base)


def test_strong_uptrend_holds():
    r = assess(make_snapshot())
    assert r.state == PositionState.UPTREND_STRONG
    assert Action.SELL_COVERED_CALLS not in r.actions


def test_fading_uptrend_sells_calls():
    r = assess(make_snapshot(volume=make_volume(fade_on_rise=True)))
    assert r.state == PositionState.UPTREND_FADING
    assert Action.SELL_COVERED_CALLS in r.actions


def test_post_crash_gate_blocks_call_sale():
    # Fading momentum but stock only 5% above its 20-day low: gate must block.
    r = assess(
        make_snapshot(volume=make_volume(fade_on_rise=True), pct_above_20d_low=0.05)
    )
    assert r.state == PositionState.UPTREND_FADING
    assert Action.SELL_COVERED_CALLS not in r.actions


def test_shakeout_beats_breakdown():
    # Sharp drop with weak flow = shake-out (hold), even with a down-cross.
    r = assess(
        make_snapshot(
            drop_pct_window=-0.15,
            cmf=-0.05,
            cmf_band=CmfBand.WEAK_SELLING,
            ma10_crossed_down_ema20=True,
            trend=TrendState.MIXED,
        )
    )
    assert r.state == PositionState.SHAKEOUT
    assert Action.DEFENSIVE_CALL_LADDER not in r.actions


def test_breakdown_triggers_defense():
    r = assess(
        make_snapshot(
            trend=TrendState.DOWNTREND,
            ma10_crossed_down_ema20=True,
            cmf=-0.2,
            cmf_band=CmfBand.HEAVY_DISTRIBUTION,
            drop_pct_window=-0.04,
        )
    )
    assert r.state == PositionState.BREAKDOWN
    assert Action.DEFENSIVE_CALL_LADDER in r.actions


def test_buyback_trigger_fires_in_any_state():
    so = ShortOptionView(
        kind="call", strike=25.0, expiry=date(2026, 9, 18), contracts=10,
        premium_collected=1.00, current_price=0.20,
    )
    r = assess(make_snapshot(short_options=[so]))
    assert Action.BUY_BACK_CALLS in r.actions


def test_assignment_watch():
    so = ShortOptionView(
        kind="call", strike=19.0, expiry=date(2026, 7, 10), contracts=10,
        premium_collected=1.00, current_price=1.50,
    )
    r = assess(make_snapshot(price=20.0, short_options=[so]))
    assert Action.ROLL_OR_ACCEPT_ASSIGNMENT in r.actions


def test_naked_call_forbidden():
    snap = make_snapshot(shares_held=500)
    violations = validate_order(snap, kind="call", side="sell", contracts=10)
    assert violations and "NAKED" in violations[0]


def test_put_requires_willingness():
    snap = make_snapshot(willing_to_add=False)
    violations = validate_order(snap, kind="put", side="sell", contracts=5)
    assert any("willing" in v for v in violations)


def test_put_2x_cap():
    snap = make_snapshot(shares_held=1000, willing_to_add=True)
    assert validate_order(snap, "put", "sell", 20) == []          # exactly 2x: OK
    assert validate_order(snap, "put", "sell", 21) != []          # over 2x: violation
