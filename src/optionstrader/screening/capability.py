"""Live 20/20/20 capability screen (docs/06-screening-module.md).

Extension module — NOT from the book. Answers one question per ticker:
"can this stock pay the rent the strategy promises?" All trading decisions
(strikes, timing, management) remain the book's rules, downstream.

Legs (both put AND call reference strikes must pass 1-3):
  1. a listed strike >= otm_distance from spot with a live market
  2. annualized premium yield at that strike >= roi_floor
  3. |delta| < delta_ceiling (yield is time-value richness, not crash pricing)
Supplemental legs: liquidity, price/volume floors, chart structure,
not-in-freefall, event hygiene.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from math import log, sqrt

import pandas as pd

from ..config import DEFAULT
from ..data.provider import DataProvider, OptionQuote
from ..indicators import detect_levels, evaluate_1030, nearest_resistance, nearest_support
from ..backtest.pricing import norm_cdf, realized_vol


@dataclass
class ScreenParams:
    otm_distance: float = 0.20      # reference strikes ~20% OTM
    roi_floor: float = 0.20         # annualized premium yield >= 20%
    delta_ceiling: float = 0.20     # |delta| < 0.20
    min_dte: int = 45               # reference tenor window
    max_dte: int = 75               # (45-60 preferred; allow to 75 for sparse chains)
    min_open_interest: int = 100
    max_spread_frac: float = 0.10   # bid/ask spread <= 10% of premium (mid)
    min_price: float = 5.0
    min_avg_volume: float = 250_000
    structure_range: float = 0.25   # need support AND resistance within +/-25%
    iv_fallback_mult: float = 1.20  # if chain IV missing, use realized vol x this


@dataclass
class LegResult:
    name: str
    passed: bool
    detail: str


@dataclass
class ScreenReport:
    ticker: str
    as_of: date
    passed: bool
    score: float                    # min(put ROI, call ROI); ranking key
    legs: list[LegResult] = field(default_factory=list)

    def summary(self) -> str:
        head = f"{self.ticker}: {'PASS' if self.passed else 'FAIL'}  (score={self.score:.1%})"
        return "\n".join([head] + [
            f"  [{'x' if l.passed else ' '}] {l.name}: {l.detail}" for l in self.legs
        ])


def bs_delta(kind: str, spot: float, strike: float, dte_days: float, sigma: float, r: float = 0.03) -> float:
    """Black-Scholes delta. Put delta returned as negative."""
    t = max(dte_days, 1e-9) / 365.0
    if sigma <= 0 or spot <= 0 or strike <= 0:
        return 0.0
    d1 = (log(spot / strike) + (r + 0.5 * sigma**2) * t) / (sigma * sqrt(t))
    return norm_cdf(d1) if kind == "call" else norm_cdf(d1) - 1.0


def _quote_price(q: OptionQuote) -> float:
    """Effective premium: live bid, else last trade (closed-market fallback)."""
    return q.bid if q.bid > 0 else q.last


def _reference_quote(chain: list[OptionQuote], kind: str, spot: float, p: ScreenParams) -> OptionQuote | None:
    """Nearest listed strike at least otm_distance OTM with a usable quote."""
    if kind == "put":
        eligible = [q for q in chain if q.kind == "put" and q.strike <= spot * (1 - p.otm_distance) and _quote_price(q) > 0]
        return max(eligible, key=lambda q: q.strike) if eligible else None
    eligible = [q for q in chain if q.kind == "call" and q.strike >= spot * (1 + p.otm_distance) and _quote_price(q) > 0]
    return min(eligible, key=lambda q: q.strike) if eligible else None


def _side_legs(
    q: OptionQuote | None, kind: str, spot: float, dte: int, fallback_sigma: float, p: ScreenParams
) -> tuple[list[LegResult], float]:
    """The three 20/20/20 legs for one side. Returns (legs, roi)."""
    if q is None:
        return [LegResult(f"{kind}-strike", False, f"no live strike ≥{p.otm_distance:.0%} OTM")], 0.0
    stale = "" if q.bid > 0 else " [last-trade quote — market closed, re-check live]"
    prem = _quote_price(q)
    legs = [LegResult(f"{kind}-strike", True, f"{q.strike:g} ({abs(q.strike / spot - 1):.0%} OTM, {dte}d){stale}")]

    collateral = (q.strike - prem) if kind == "put" else spot
    roi = (prem / collateral) * (365.0 / dte) if collateral > 0 and dte > 0 else 0.0
    legs.append(LegResult(f"{kind}-roi", roi >= p.roi_floor, f"{roi:.1%} annualized (prem {prem:.2f})"))

    sigma = q.iv if q.iv > 0.01 else fallback_sigma
    delta = abs(bs_delta(kind, spot, q.strike, dte, sigma))
    legs.append(LegResult(f"{kind}-delta", delta < p.delta_ceiling, f"|Δ|={delta:.2f} (σ={sigma:.0%})"))

    mid = (q.bid + q.ask) / 2 if q.ask > 0 else q.bid
    spread_ok = q.ask <= 0 or (q.ask - q.bid) <= p.max_spread_frac * mid or (q.ask - q.bid) <= 0.05
    legs.append(LegResult(f"{kind}-liquidity", q.open_interest >= p.min_open_interest and spread_ok,
                          f"OI={q.open_interest}, spread={max(q.ask - q.bid, 0):.2f}"))
    return legs, roi


def screen_live(ticker: str, provider: DataProvider, params: ScreenParams | None = None,
                as_of: date | None = None) -> ScreenReport:
    p = params or ScreenParams()
    df = provider.daily_ohlcv(ticker, lookback_days=300)
    spot = float(df["close"].iloc[-1])
    today = as_of or (df.index[-1].date() if hasattr(df.index[-1], "date") else date.today())
    legs: list[LegResult] = []

    # Stock floors.
    avg_vol = float(df["volume"].tail(50).mean())
    legs.append(LegResult("price-floor", spot >= p.min_price, f"{spot:.2f} (min {p.min_price:g})"))
    legs.append(LegResult("stock-liquidity", avg_vol >= p.min_avg_volume, f"avg vol {avg_vol:,.0f}"))

    # Not in freefall: no new 20-day closing low, 1030 direction check.
    closes = df["close"]
    new_low = float(closes.iloc[-1]) <= float(closes.tail(DEFAULT.book.post_crash_lookback_days).min())
    t1030 = evaluate_1030(closes)
    legs.append(LegResult("not-freefall", (not new_low) and t1030.fast_above,
                          f"new 20d low={new_low}, MA10>MA30={t1030.fast_above}"))

    # Chart structure: support and resistance within +/-structure_range.
    levels = detect_levels(df)
    sup, res = nearest_support(levels, spot), nearest_resistance(levels, spot)
    sup_ok = sup is not None and sup.price >= spot * (1 - p.structure_range)
    res_ok = res is not None and res.price <= spot * (1 + p.structure_range)
    legs.append(LegResult("structure", sup_ok and res_ok,
                          f"support={f'{sup.price:.2f}' if sup else '—'}, resistance={f'{res.price:.2f}' if res else '—'}"))

    # Reference expiry in the tenor window.
    expiries = [e for e in provider.option_expirations(ticker) if p.min_dte <= (e - today).days <= p.max_dte]
    if not expiries:
        legs.append(LegResult("tenor", False, f"no expiration {p.min_dte}-{p.max_dte} DTE"))
        return ScreenReport(ticker.upper(), today, False, 0.0, legs)
    expiry = expiries[0]
    dte = (expiry - today).days
    legs.append(LegResult("tenor", True, f"{expiry} ({dte}d)"))

    # Event hygiene: ADVISORY only (never gates). With quarterly earnings and a
    # 45-75 DTE tenor an earnings date sits inside the window almost always —
    # the flag means "measured yield may be event-inflated; re-check after".
    earnings = provider.next_earnings_date(ticker)
    event_inside = earnings is not None and today <= earnings <= expiry
    legs.append(LegResult("event-hygiene[advisory]", True,
                          f"earnings {earnings or 'unknown'}" + (" INSIDE tenor — yield may be event-inflated" if event_inside else "")))

    # The 20/20/20 legs. The PUT side is the gate (the rule is about being
    # paid to buy shares); the call side is reported as a diagnostic only —
    # jointly requiring call ROI >= 20% AND call |delta| < 0.20 is infeasible
    # under lognormal pricing (ROI needs sigma >= ~0.6, delta needs <= ~0.5).
    chain = provider.option_chain(ticker, expiry)
    fallback_sigma = realized_vol(closes) * p.iv_fallback_mult
    put_legs, put_roi = _side_legs(_reference_quote(chain, "put", spot, p), "put", spot, dte, fallback_sigma, p)
    call_legs, _ = _side_legs(_reference_quote(chain, "call", spot, p), "call", spot, dte, fallback_sigma, p)
    for l in call_legs:
        l.detail += "  [diagnostic — not gating]"
    legs += put_legs + call_legs

    passed = all(l.passed for l in legs if not l.name.startswith("call-"))
    return ScreenReport(ticker.upper(), today, passed, put_roi, legs)
