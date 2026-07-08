"""Half/half put-sale planner (docs/04 §2, the book's entry method).

Plan a new position by getting paid to buy it:
  Tranche 1 — puts on HALF the intended shares at the strike below the
              nearest strong support; sell when price trades near the strike
              (fattest premium).
  Tranche 2 — puts on the second half at the strike below the NEXT lower
              support, sold only if the stock keeps falling; let tranche 1
              be assigned.

The planner computes strikes from real listed strikes, premiums from the live
chain, effective costs (strike − premium), the blended cost if both tranches
are assigned, and cash-secured requirements. It never places orders.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from ..data.provider import DataProvider
from ..indicators import detect_levels, evaluate_1030, nearest_support


@dataclass
class PutTranche:
    label: str
    strike: float
    contracts: int
    expiry: date
    est_premium: float           # per share (bid; last-trade fallback)
    effective_cost: float        # strike − premium if assigned
    cash_required: float         # cash-secured net of premium received
    trigger: str


@dataclass
class PutSalePlan:
    ticker: str
    as_of: date
    price: float
    target_shares: int
    ready: bool                  # tranche 1 sellable now (price near strike)
    tranches: list[PutTranche] = field(default_factory=list)
    blended_effective_cost: float | None = None
    total_est_premium: float = 0.0
    notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"{self.ticker}  {self.as_of}  price {self.price:.2f}  target {self.target_shares} shares",
            f"status: {'READY — sell tranche 1' if self.ready else 'WAIT'}",
        ]
        for t in self.tranches:
            lines.append(
                f"  {t.label}: sell {t.contracts}x {t.strike:g} put exp {t.expiry} "
                f"@ ~{t.est_premium:.2f} → effective cost {t.effective_cost:.2f} if assigned, "
                f"cash to secure ${t.cash_required:,.0f}"
            )
            lines.append(f"      trigger: {t.trigger}")
        if self.blended_effective_cost is not None:
            prem_dollars = sum(t.est_premium * t.contracts * 100 for t in self.tranches)
            lines.append(
                f"  if BOTH assigned: {self.target_shares} shares at blended "
                f"{self.blended_effective_cost:.2f} (${prem_dollars:,.0f} premium banked)"
            )
        lines += [f"  note: {n}" for n in self.notes]
        return "\n".join(lines)


def _quote_price(q) -> float:
    return q.bid if q.bid > 0 else q.last


def plan_half_half(
    ticker: str,
    provider: DataProvider,
    target_shares: int,
    cash_available: float | None = None,
    min_dte: int = 45,
    max_dte: int = 90,
) -> PutSalePlan:
    df = provider.daily_ohlcv(ticker, lookback_days=300)
    price = float(df["close"].iloc[-1])
    today = df.index[-1].date() if hasattr(df.index[-1], "date") else date.today()
    plan = PutSalePlan(ticker.upper(), today, price, target_shares, ready=False)

    if target_shares < 200:
        plan.notes.append("target under 200 shares — half/half needs at least 1 contract per tranche")
        return plan

    # Support map (the strikes' anchors — book: strike one level below support).
    levels = detect_levels(df)
    s1 = nearest_support(levels, price)
    if s1 is None:
        plan.notes.append("no support level detected — the book anchors put strikes at support; do not sell puts blind")
        return plan
    s2 = nearest_support(levels, s1.price)

    # Trend context (advisory): half/half is DESIGNED for entering into weakness,
    # but flag the trend so the user knows which phase they're in.
    t1030 = evaluate_1030(df["close"])
    plan.notes.append(
        "1030 test: MA10 %s MA30 — %s"
        % ("above" if t1030.fast_above else "below",
           "uptrend context" if t1030.fast_above
           else "falling stock: plan sells tranche 1 near support and keeps tranche 2 for lower — size for full assignment")
    )

    # Expiration: nearest listed expiry in the book's observed 45-90 DTE practice.
    expiries = [e for e in provider.option_expirations(ticker) if min_dte <= (e - today).days <= max_dte]
    if not expiries:
        plan.notes.append(f"no listed expiration {min_dte}-{max_dte} DTE")
        return plan
    expiry = expiries[0]
    chain = provider.option_chain(ticker, expiry)
    put_strikes = sorted({q.strike for q in chain if q.kind == "put"})
    if not put_strikes:
        plan.notes.append("no put strikes listed")
        return plan

    def strike_below(level_price: float) -> float | None:
        below = [k for k in put_strikes if k < level_price]
        return max(below) if below else None

    def premium_at(strike: float) -> float:
        qs = [q for q in chain if q.kind == "put" and q.strike == strike]
        return _quote_price(qs[0]) if qs else 0.0

    k1 = strike_below(s1.price)
    if k1 is None:
        plan.notes.append(f"no strike below support {s1.price:.2f}")
        return plan
    k2 = strike_below(s2.price) if s2 else None
    if k2 is None or k2 >= k1:
        below_k1 = [k for k in put_strikes if k < k1]
        k2 = max(below_k1) if below_k1 else None
        plan.notes.append("no distinct lower support — tranche 2 uses the next listed strike down")

    c1 = (target_shares // 2) // 100
    c2 = (target_shares // 100) - c1  # remainder lot goes to tranche 2

    p1 = premium_at(k1)
    tr1 = PutTranche(
        label="tranche 1 (half)", strike=k1, contracts=c1, expiry=expiry,
        est_premium=p1, effective_cost=k1 - p1,
        cash_required=(k1 - p1) * 100 * c1,
        trigger=f"sell when price trades near {k1:g} (support {s1.price:.2f}); "
                f"book: close to the strike = fattest premium",
    )
    plan.tranches.append(tr1)

    if k2 is not None and c2 > 0:
        p2 = premium_at(k2)
        anchor = f"support {s2.price:.2f}" if s2 and k2 < s2.price else "next strike down"
        tr2 = PutTranche(
            label="tranche 2 (half)", strike=k2, contracts=c2, expiry=expiry,
            est_premium=p2, effective_cost=k2 - p2,
            cash_required=(k2 - p2) * 100 * c2,
            trigger=f"ONLY if the stock keeps falling toward {k2:g} ({anchor}); "
                    "let tranche 1 be assigned",
        )
        plan.tranches.append(tr2)
        sh1, sh2 = c1 * 100, c2 * 100
        plan.blended_effective_cost = (
            (k1 * sh1 + k2 * sh2 - (p1 * sh1 + p2 * sh2)) / (sh1 + sh2)
        )
        plan.total_est_premium = p1 * c1 + p2 * c2

    # Ready check: book sells when price is within ~1/2 point of the strike
    # (scaled by 1% of price for higher-priced stocks — CALIB scaling).
    near = max(0.5, 0.01 * price)
    plan.ready = price <= k1 + max(2 * near, 0.05 * price)
    if not plan.ready:
        plan.notes.append(
            f"price {price:.2f} is far above tranche-1 strike {k1:g} — premium too thin; "
            f"WAIT for a dip toward {k1 + near:.2f} or re-anchor to a higher support"
        )

    total_cash = sum(t.cash_required for t in plan.tranches)
    if cash_available is not None:
        if total_cash > cash_available:
            plan.ready = False
            plan.notes.append(
                f"cash-secured requirement ${total_cash:,.0f} exceeds available ${cash_available:,.0f} — "
                "reduce target shares; never sell puts you cannot take delivery on"
            )
        else:
            plan.notes.append(f"cash-secured total ${total_cash:,.0f} of ${cash_available:,.0f} available")
    return plan
