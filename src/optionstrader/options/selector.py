"""Strike and expiration selection (docs/04 §1-3).

Strikes come from the support/resistance map — never from premium size:
  covered call -> first listed strike ABOVE the nearest strong resistance
  put          -> first listed strike BELOW the nearest strong support

Expiration month: prefer the nearer month unless a later month pays more than
2x the premium; require adequate open interest; flag months containing a
known binary event (earnings months demand a higher minimum strike).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class StrikeChoice:
    strike: float
    anchor_level: float          # the support/resistance the strike sits beyond
    rationale: str


@dataclass
class ExpiryQuote:
    expiry: date
    premium: float               # per share (use bid for sells)
    open_interest: int
    has_event_before_expiry: bool = False


def select_call_strike(
    strike_grid: list[float],
    resistance: float,
    price: float,
    target_min: float = 0.10,
) -> StrikeChoice | None:
    """First strike strictly above resistance.

    Warns (in rationale) when the strike caps the position below the book's
    10% minimum target zone above market.
    """
    above = sorted(s for s in strike_grid if s > resistance)
    if not above:
        return None
    strike = above[0]
    rationale = f"first strike above resistance {resistance:.2f}"
    if price > 0 and (strike / price - 1.0) < target_min:
        rationale += (
            f" — WARNING: only {strike / price - 1.0:.0%} above market, "
            f"below the {target_min:.0%} target zone; consider the next strike up"
        )
    return StrikeChoice(strike=strike, anchor_level=resistance, rationale=rationale)


def select_put_strike(
    strike_grid: list[float],
    support: float,
    price: float,
) -> StrikeChoice | None:
    """First strike strictly below support."""
    below = sorted((s for s in strike_grid if s < support), reverse=True)
    if not below:
        return None
    return StrikeChoice(
        strike=below[0],
        anchor_level=support,
        rationale=f"first strike below support {support:.2f}",
    )


def choose_expiration(
    quotes: list[ExpiryQuote],
    min_open_interest: int = 100,
    later_month_ratio: float = 2.0,
) -> tuple[ExpiryQuote | None, list[str]]:
    """Apply the 2x-premium month rule over liquid expirations.

    Walk expirations near-to-far; step out only when the later month pays
    > later_month_ratio x the currently chosen month. Returns (choice, notes).
    """
    notes: list[str] = []
    liquid = [q for q in sorted(quotes, key=lambda q: q.expiry) if q.open_interest >= min_open_interest]
    dropped = len(quotes) - len(liquid)
    if dropped:
        notes.append(f"dropped {dropped} expiration(s) below {min_open_interest} open interest")
    if not liquid:
        return None, notes + ["no liquid expirations"]

    choice = liquid[0]
    for later in liquid[1:]:
        if choice.premium > 0 and later.premium > later_month_ratio * choice.premium:
            notes.append(
                f"{later.expiry}: {later.premium:.2f} > {later_month_ratio:.0f}x "
                f"{choice.expiry}'s {choice.premium:.2f} — taking the later month"
            )
            choice = later
    if choice.has_event_before_expiry:
        notes.append(
            "chosen expiry contains a binary event (earnings/FOMC): use a higher "
            "minimum strike, and plan to close before the event"
        )
    return choice, notes
