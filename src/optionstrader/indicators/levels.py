"""Support/resistance detection via pivot clustering.

Method (see the discussion in docs/03): find swing highs/lows (local extrema
over ±N bars), cluster pivots within a price tolerance, and score each level
using the book's three strength factors — touches over time, duration, and
volume traded at the level. A broken support is re-tagged as resistance
(and vice versa) relative to the current price, matching the book's usage.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from ..config import Config, DEFAULT


@dataclass
class Pivot:
    date: pd.Timestamp
    price: float
    kind: str  # "high" | "low"
    volume: float


@dataclass
class Level:
    price: float                     # median of clustered pivot prices
    touches: int
    first_touch: pd.Timestamp
    last_touch: pd.Timestamp
    total_volume: float
    pivots: list[Pivot] = field(default_factory=list)

    @property
    def span_days(self) -> int:
        return int((self.last_touch - self.first_touch).days)

    def strength(self) -> float:
        """Composite strength: touches weighted by volume share and duration.

        Relative score for ranking levels of the same stock; not comparable
        across stocks.
        """
        return self.touches * (1.0 + self.span_days / 365.0)

    def role(self, current_price: float) -> str:
        """A level above price acts as resistance; below, as support —
        including formerly-broken levels (support becomes resistance)."""
        return "resistance" if self.price > current_price else "support"


def find_pivots(df: pd.DataFrame, cfg: Config = DEFAULT) -> list[Pivot]:
    """Swing highs/lows: bar extreme vs ±pivot_window bars."""
    w = cfg.calib.pivot_window
    df = df.tail(cfg.calib.level_lookback_days)
    highs, lows, vol = df["high"], df["low"], df["volume"]
    pivots: list[Pivot] = []
    for i in range(w, len(df) - w):
        window_hi = highs.iloc[i - w : i + w + 1]
        window_lo = lows.iloc[i - w : i + w + 1]
        if highs.iloc[i] == window_hi.max():
            pivots.append(Pivot(df.index[i], float(highs.iloc[i]), "high", float(vol.iloc[i])))
        if lows.iloc[i] == window_lo.min():
            pivots.append(Pivot(df.index[i], float(lows.iloc[i]), "low", float(vol.iloc[i])))
    return pivots


def detect_levels(df: pd.DataFrame, cfg: Config = DEFAULT) -> list[Level]:
    """Cluster pivots within tolerance into levels with ≥ min_level_touches."""
    tol = cfg.calib.level_cluster_tolerance
    pivots = sorted(find_pivots(df, cfg), key=lambda p: p.price)
    levels: list[Level] = []
    cluster: list[Pivot] = []

    def flush(cluster: list[Pivot]) -> None:
        if len(cluster) >= cfg.calib.min_level_touches:
            prices = sorted(p.price for p in cluster)
            median = prices[len(prices) // 2]
            levels.append(
                Level(
                    price=median,
                    touches=len(cluster),
                    first_touch=min(p.date for p in cluster),
                    last_touch=max(p.date for p in cluster),
                    total_volume=sum(p.volume for p in cluster),
                    pivots=list(cluster),
                )
            )

    for p in pivots:
        if cluster and (p.price - cluster[0].price) / cluster[0].price > tol:
            flush(cluster)
            cluster = []
        cluster.append(p)
    flush(cluster)
    return sorted(levels, key=lambda lv: lv.price)


def nearest_resistance(levels: list[Level], price: float) -> Level | None:
    above = [lv for lv in levels if lv.price > price]
    return min(above, key=lambda lv: lv.price) if above else None


def nearest_support(levels: list[Level], price: float) -> Level | None:
    below = [lv for lv in levels if lv.price < price]
    return max(below, key=lambda lv: lv.price) if below else None
