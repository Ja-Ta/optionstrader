"""Short-premium tracker (docs/04 §1, §3).

Monitors every open short option against:
  - the 25% buy-back trigger (lock 75% of premium, recycle)
  - the assignment watch (≥ 3/4 point ITM AND ≤ 2 weeks to expiry)
  - expiration-day auto-assignment (modern rule: ≥ $0.01 ITM assigns)
  - the event calendar (close threatened shorts before binary events)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from ..config import Config, DEFAULT


class AlertKind(Enum):
    BUYBACK_TRIGGER = "buyback_trigger"
    ASSIGNMENT_RISK = "assignment_risk"
    EXPIRY_ITM = "expiry_itm"
    EVENT_WARNING = "event_warning"


@dataclass
class ShortOption:
    ticker: str
    kind: str                 # "call" | "put"
    strike: float
    expiry: date
    contracts: int
    premium_collected: float  # per share
    opened: date

    def itm_amount(self, spot: float) -> float:
        raw = (spot - self.strike) if self.kind == "call" else (self.strike - spot)
        return max(raw, 0.0)

    def dte(self, today: date) -> int:
        return (self.expiry - today).days


@dataclass
class Alert:
    kind: AlertKind
    message: str
    urgency: int  # 0 = informational, 1 = act soon, 2 = act now

    def __str__(self) -> str:
        flag = ["INFO", "SOON", "NOW "][self.urgency]
        return f"[{flag}] {self.message}"


def check_short_option(
    so: ShortOption,
    spot: float,
    option_price: float | None,
    today: date,
    days_to_next_event: int | None = None,
    cfg: Config = DEFAULT,
) -> list[Alert]:
    """Evaluate one open short option. option_price is per share (ask for buybacks)."""
    b = cfg.book
    alerts: list[Alert] = []
    label = f"{so.ticker} {so.expiry:%b%d} {so.strike:g} {so.kind} x{so.contracts}"

    if option_price is not None and option_price <= b.buyback_fraction * so.premium_collected:
        captured = (so.premium_collected - option_price) * so.contracts * 100
        alerts.append(
            Alert(
                AlertKind.BUYBACK_TRIGGER,
                f"{label}: {option_price:.2f} ≤ 25% of {so.premium_collected:.2f} collected — "
                f"buy back now, banking ${captured:,.0f} (75%+ captured); re-sell on the next swing",
                urgency=2,
            )
        )

    itm = so.itm_amount(spot)
    dte = so.dte(today)
    if itm >= b.itm_exercise_points and dte <= b.exercise_window_days:
        alerts.append(
            Alert(
                AlertKind.ASSIGNMENT_RISK,
                f"{label}: {itm:.2f} ITM with {dte}d to expiry — early exercise likely; "
                "roll (finance buyback with next strike out) or accept assignment per plan",
                urgency=2,
            )
        )
    elif itm > 0 and dte <= 1:
        alerts.append(
            Alert(
                AlertKind.EXPIRY_ITM,
                f"{label}: {itm:.2f} ITM at expiration — auto-assignment at ≥ $0.01 ITM "
                "(modern rule); close today if assignment is unwanted",
                urgency=2,
            )
        )
    elif itm > 0:
        alerts.append(
            Alert(
                AlertKind.ASSIGNMENT_RISK,
                f"{label}: {itm:.2f} ITM but {dte}d remain — early exercise unlikely "
                "(needs ≥ 3/4 point ITM AND ≤ 2 weeks); don't panic-close",
                urgency=0,
            )
        )

    if days_to_next_event is not None and 0 <= days_to_next_event <= cfg.calib.event_close_window_days:
        if days_to_next_event * 1 <= dte:  # event lands before expiry matters
            alerts.append(
                Alert(
                    AlertKind.EVENT_WARNING,
                    f"{label}: binary event in {days_to_next_event}d before expiry — "
                    "close if a surprise could gap the stock through the strike",
                    urgency=1,
                )
            )
    return alerts
