"""Historical capability proxy for backtests.

No free historical option chains exist, so backtests approximate the 20/20/20
capability screen with the same synthetic pricer the backtester trades on:
Black-Scholes at realized vol x IV-premium, reference strikes ~20% OTM at a
~52-DTE tenor. The structure / freefall legs run on real OHLCV.

Same limitation as the backtester itself (see backtest/pricing.py): this
measures whether the *screen logic* helps, not exact historical yields.
"""

from __future__ import annotations

import pandas as pd

from ..indicators import detect_levels, evaluate_1030, nearest_resistance, nearest_support
from ..backtest.pricing import SyntheticPricer, bs_price
from .capability import ScreenParams, bs_delta


def capability_proxy(
    history: pd.DataFrame,
    pricer: SyntheticPricer | None = None,
    params: ScreenParams | None = None,
) -> tuple[bool, dict]:
    """Evaluate the capability screen at the last bar of `history`.

    Returns (passed, detail dict with per-leg booleans and the measured ROI).
    """
    p = params or ScreenParams()
    pricer = pricer or SyntheticPricer()
    closes = history["close"]
    spot = float(closes.iloc[-1])
    dte = 52  # midpoint of the 45-60 preferred tenor window
    sigma = pricer.sigma(closes)

    detail: dict = {}

    # Stock floors.
    avg_vol = float(history["volume"].tail(50).mean())
    detail["price_floor"] = spot >= p.min_price
    detail["stock_liquidity"] = avg_vol >= p.min_avg_volume

    # Not in freefall.
    new_low = spot <= float(closes.tail(20).min())
    detail["not_freefall"] = (not new_low) and evaluate_1030(closes).fast_above

    # Structure.
    levels = detect_levels(history)
    sup, res = nearest_support(levels, spot), nearest_resistance(levels, spot)
    detail["structure"] = (
        sup is not None and sup.price >= spot * (1 - p.structure_range)
        and res is not None and res.price <= spot * (1 + p.structure_range)
    )

    # 20/20/20 on synthetic pricing. PUT side gates (see capability.py — the
    # call-side joint requirement is infeasible under lognormal pricing);
    # call metrics are recorded as diagnostics only.
    put_strike = spot * (1 - p.otm_distance)
    call_strike = spot * (1 + p.otm_distance)
    put_prem = bs_price("put", spot, put_strike, dte, sigma)
    call_prem = bs_price("call", spot, call_strike, dte, sigma)
    put_roi = (put_prem / (put_strike - put_prem)) * (365.0 / dte) if put_strike > put_prem else 0.0
    detail["put_roi"] = round(put_roi, 3)
    detail["call_roi_diag"] = round((call_prem / spot) * (365.0 / dte), 3)
    detail["roi"] = put_roi >= p.roi_floor
    detail["delta"] = abs(bs_delta("put", spot, put_strike, dte, sigma)) < p.delta_ceiling

    passed = all(v for k, v in detail.items() if isinstance(v, bool))
    return passed, detail
