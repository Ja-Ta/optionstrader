"""Synthetic option pricing for backtests.

LIMITATION (stated, by design): free data sources carry no historical option
chains, so backtests price options with Black-Scholes off trailing realized
volatility, scaled by an IV-premium multiplier (implied vol persistently
trades above realized — the variance risk premium the strategy harvests).
Results therefore measure the *timing rules'* value, not exact historical
premiums. Validate any live-sizing decision against real chains (Tier 2+).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from math import erf, exp, log, sqrt

import numpy as np
import pandas as pd


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


def bs_price(
    kind: str,
    spot: float,
    strike: float,
    dte_days: float,
    sigma: float,
    r: float = 0.03,
) -> float:
    """Black-Scholes European price per share. kind: 'call' | 'put'."""
    intrinsic = max(spot - strike, 0.0) if kind == "call" else max(strike - spot, 0.0)
    t = max(dte_days, 0.0) / 365.0
    if t <= 0 or sigma <= 0 or spot <= 0 or strike <= 0:
        return intrinsic
    d1 = (log(spot / strike) + (r + 0.5 * sigma**2) * t) / (sigma * sqrt(t))
    d2 = d1 - sigma * sqrt(t)
    call = spot * norm_cdf(d1) - strike * exp(-r * t) * norm_cdf(d2)
    if kind == "call":
        return max(call, 0.0)
    return max(call - spot + strike * exp(-r * t), 0.0)  # put-call parity


def realized_vol(closes: pd.Series, window: int = 30) -> float:
    """Annualized close-to-close realized volatility."""
    rets = np.log(closes / closes.shift(1)).dropna().tail(window)
    if len(rets) < 5:
        return 0.0
    return float(rets.std(ddof=1) * sqrt(252.0))


def strike_grid(price: float, span: float = 0.6) -> list[float]:
    """Exchange-style strike increments around the current price."""
    if price < 25:
        inc = 2.5
    elif price < 50:
        inc = 2.5
    elif price < 200:
        inc = 5.0
    else:
        inc = 10.0
    lo = max(inc, (price * (1 - span)) // inc * inc)
    hi = price * (1 + span)
    grid, s = [], lo
    while s <= hi:
        grid.append(round(s, 2))
        s += inc
    return grid


def third_friday(year: int, month: int) -> date:
    d = date(year, month, 15)
    while d.weekday() != 4:  # Friday
        d += timedelta(days=1)
    return d


def monthly_expiries(start: date, end: date) -> list[date]:
    out = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        f = third_friday(y, m)
        if start <= f <= end:
            out.append(f)
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def pick_expiry(today: date, min_dte: int = 45, max_dte: int = 90) -> date | None:
    """Nearest monthly expiration inside the DTE window.

    Stands in for the book's 2x-premium month rule: with smooth BS pricing the
    2x ratio between adjacent months essentially never triggers, so the
    backtest uses the book's *observed practice* (2-5 month expirations,
    45-90 DTE default) instead.
    """
    horizon = monthly_expiries(today, today + timedelta(days=max_dte + 40))
    for f in horizon:
        dte = (f - today).days
        if min_dte <= dte <= max_dte:
            return f
    return horizon[-1] if horizon else None


@dataclass
class SyntheticPricer:
    """Prices any option from the current bar's history. Frictions applied
    symmetrically: sells fill below fair value, buys above."""

    iv_premium: float = 1.20     # IV = realized vol x this multiplier
    friction: float = 0.05      # 5% of premium lost to spread/slippage per side
    r: float = 0.03
    vol_window: int = 30
    min_sigma: float = 0.15     # floor: quiet stretches still price some risk

    def sigma(self, closes: pd.Series) -> float:
        return max(realized_vol(closes, self.vol_window) * self.iv_premium, self.min_sigma)

    def fair(self, kind: str, spot: float, strike: float, today: date, expiry: date, closes: pd.Series) -> float:
        dte = (expiry - today).days
        return bs_price(kind, spot, strike, dte, self.sigma(closes), self.r)

    def sell_fill(self, *args) -> float:
        return self.fair(*args) * (1.0 - self.friction)

    def buy_fill(self, *args) -> float:
        return self.fair(*args) * (1.0 + self.friction)
