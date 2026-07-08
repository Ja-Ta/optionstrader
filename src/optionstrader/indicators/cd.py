"""CD (Convergence/Divergence) charts — weekly relative strength (docs/04 §6).

The long-term account's designated EXIT tool: CD = stock close / index close,
normalized into the 1-10 range, sampled weekly on a consistent weekday
(Monday preferred). Deterioration of CD usually precedes long-term reversals.

Sell/defend tests (either fires):
  (a) CD falls while price rises — momentum weaker than the index
  (b) CD at the current price on the way DOWN is lower than CD was at the
      same price on the way UP

Buy tests (for new positions; enter only on exceptional strength):
  (a) price range-bound while CD rises
  (b) new price low WITHOUT a new CD low — strongest when CD at the low
      matches CD from a price 25%+ higher
  (c) price breakout with a CD breakout (lower risk, less profit)

Window/tolerance values are CALIB (book states the tests qualitatively).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import floor, log10

import pandas as pd


def weekly_series(daily_close: pd.Series) -> pd.Series:
    """Weekly samples anchored to Monday (book: same weekday every week;
    Monday preferred — weekend news lands Monday, Fridays are distorted
    by expirations)."""
    return daily_close.resample("W-MON").last().dropna()


def normalize_1_10(ratio: pd.Series) -> pd.Series:
    """Scale by a power of 10 so the median lands in [1, 10) (book method)."""
    med = float(ratio.median())
    if med <= 0:
        return ratio
    n = -floor(log10(med))
    return ratio * (10.0 ** n)


def cd_series(stock_daily_close: pd.Series, index_daily_close: pd.Series) -> pd.DataFrame:
    """Weekly frame with columns: price, cd (normalized 1-10)."""
    wp = weekly_series(stock_daily_close)
    wi = weekly_series(index_daily_close)
    joined = pd.concat([wp.rename("price"), wi.rename("index")], axis=1).dropna()
    joined["cd"] = normalize_1_10(joined["price"] / joined["index"])
    return joined[["price", "cd"]]


@dataclass
class CdAssessment:
    state: str                       # "sell_defend" | "buy_strength" | "neutral"
    sell_signals: list[str] = field(default_factory=list)
    buy_signals: list[str] = field(default_factory=list)
    latest_price: float = 0.0
    latest_cd: float = 0.0
    weeks: int = 0

    def summary(self) -> str:
        lines = [f"CD state: {self.state}  (price {self.latest_price:.2f}, CD {self.latest_cd:.3f}, {self.weeks}w)"]
        lines += [f"  SELL: {s}" for s in self.sell_signals]
        lines += [f"  BUY:  {s}" for s in self.buy_signals]
        if not (self.sell_signals or self.buy_signals):
            lines.append("  no CD signals")
        return "\n".join(lines)


def assess_cd(
    stock_daily_close: pd.Series,
    index_daily_close: pd.Series,
    lookback_weeks: int = 52,        # CALIB
    slope_weeks: int = 4,            # CALIB: recent-trend window
    price_match_tol: float = 0.03,   # CALIB: "same price" tolerance for test (b)
    cd_margin: float = 0.02,         # CALIB: CD must differ by 2%+ to signal
) -> CdAssessment:
    frame = cd_series(stock_daily_close, index_daily_close).tail(lookback_weeks)
    if len(frame) < slope_weeks + 8:
        return CdAssessment(state="neutral", weeks=len(frame))
    price, cd = frame["price"], frame["cd"]
    p_now, cd_now = float(price.iloc[-1]), float(cd.iloc[-1])
    sell: list[str] = []
    buy: list[str] = []

    # --- sell (a): CD falling while price rises ---
    p_chg = p_now / float(price.iloc[-1 - slope_weeks]) - 1.0
    cd_chg = cd_now / float(cd.iloc[-1 - slope_weeks]) - 1.0
    if p_chg > 0.01 and cd_chg < -cd_margin:
        sell.append(
            f"price +{p_chg:.1%} over {slope_weeks}w while CD {cd_chg:.1%} — "
            "rising slower than the index; momentum leaving"
        )

    # --- sell (b): lower CD at the same price on the down-leg ---
    peak_i = int(price.values.argmax())
    if peak_i < len(price) - 1 and float(price.iloc[peak_i]) > p_now * 1.03:
        ascent = frame.iloc[:peak_i]
        same_price = ascent[abs(ascent["price"] / p_now - 1.0) <= price_match_tol]
        if len(same_price):
            cd_then = float(same_price["cd"].max())
            if cd_now < cd_then * (1 - cd_margin):
                sell.append(
                    f"CD {cd_now:.3f} now vs {cd_then:.3f} at the same price "
                    f"(~{p_now:.2f}) on the way up — down-leg weaker; defend or exit"
                )

    # --- buy (b): new price low without a new CD low ---
    prior_p, prior_cd = price.iloc[:-1], cd.iloc[:-1]
    if p_now <= float(prior_p.min()) * 1.02 and cd_now > float(prior_cd.min()) * (1 + cd_margin):
        msg = "new price low WITHOUT a new CD low — shake-out signature"
        stronger = frame[(frame["price"] >= p_now * 1.25) & (frame["cd"] <= cd_now)]
        if len(stronger):
            msg += " (STRONG: CD matches a week priced 25%+ higher)"
        buy.append(msg)

    # --- buy (a): range-bound price, rising CD ---
    rng_weeks = min(12, len(frame) - 1)  # CALIB
    p_win, cd_win = price.tail(rng_weeks), cd.tail(rng_weeks)
    p_range = float(p_win.max()) / float(p_win.min()) - 1.0
    cd_rise = cd_now / float(cd_win.iloc[0]) - 1.0
    if p_range < 0.08 and cd_rise > cd_margin:
        buy.append(f"price range-bound ({p_range:.1%} over {rng_weeks}w) while CD +{cd_rise:.1%} — accumulation")

    # --- buy (c): joint breakout ---
    if p_now >= float(prior_p.max()) and cd_now >= float(prior_cd.max()):
        buy.append("price breakout WITH CD breakout — lower-risk second entry")

    state = "sell_defend" if sell else ("buy_strength" if buy else "neutral")
    return CdAssessment(
        state=state, sell_signals=sell, buy_signals=buy,
        latest_price=p_now, latest_cd=cd_now, weeks=len(frame),
    )
