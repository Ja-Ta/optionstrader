"""Strategy parameters.

Two kinds of values live here, kept deliberately separate:

  BOOK  — numeric rules stated explicitly in the reference strategy
          (see docs/04-key-rules-reference.md for the rule and its source section).
  CALIB — defaults for thresholds the book states only qualitatively
          ("steep slope", "sharp drop"). These MUST be validated by backtest
          (docs/03 Tier 4) before live use; treat them as starting points.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BookRules:
    # --- premium management (docs/04 §1-2) ---
    buyback_fraction: float = 0.25          # BOOK: buy back short options at 25% of premium collected
    lock_profit_fraction: float = 0.75      # BOOK: alt trigger — 75% of premium captured
    post_crash_bounce: float = 0.20         # BOOK: stock must be ≥20% above 20-day closing low to sell calls
    post_crash_lookback_days: int = 20      # BOOK: 20-day closing low window

    # --- strike selection (docs/04 §1-2) ---
    call_target_min: float = 0.10           # BOOK: call target zone 10–20% above market
    call_target_max: float = 0.20
    put_target: float = 0.10                # BOOK: put target ~10% below market
    near_strike_band: float = 0.50          # BOOK: willing-to-sell/buy variant — within 1/2 point of strike

    # --- expiration & assignment (docs/04 §3) ---
    later_month_premium_ratio: float = 2.0  # BOOK: take later month if premium > 2× nearer month
    itm_exercise_points: float = 0.75       # BOOK: early exercise unlikely unless ≥ 3/4 point ITM ...
    exercise_window_days: int = 14          # BOOK: ... AND ≤ 2 weeks to expiration

    # --- bought options (docs/04 §4) ---
    max_long_option_price: float = 0.20     # BOOK: never pay > $0.20/share for bought options
    long_option_exit_dte: int = 14          # BOOK: sell bought calls by 2 weeks pre-expiry if target unmet

    # --- indicators (docs/04 §6) ---
    ma_fast: int = 10                       # BOOK: MA(10) simple
    ema_mid: int = 20                       # BOOK: EMA(20)
    ema_slow: int = 30                      # BOOK: EMA(30)
    cmf_period: int = 20                    # BOOK: 20-day Chaikin Money Flow
    cmf_band: float = 0.10                  # BOOK: ±0.1 accumulation/distribution bands
    cmf_extreme: float = 0.50               # BOOK: ≤ −0.5 = extreme distribution
    spike_volume_ratio: float = 1.20        # BOOK: tell-tale spike — volume ≥20% above average
    spike_close_band: tuple = (0.0, 0.20)   # BOOK: ... with close 0–20% above open
    heavy_down_close: float = 0.05          # BOOK: close down >5% on heavy volume = distribution warning
    min_volume_ratio: float = 1.10          # BOOK: trade-day volume ≥10% above average before initiating

    # --- money management (docs/04 §9) ---
    max_risk_per_trade: float = 0.02        # BOOK: max loss per trade = 2% of account
    stock_stop_loss: float = 0.15           # BOOK: sell any stock closing 15% below purchase
    max_put_share_multiple: float = 2.0     # BOOK: puts on ≤ 2× share count (owning the stock)


@dataclass(frozen=True)
class Calibrated:
    # Slope classification for MA(10) — the book requires a "steep" slope to act
    # and forbids action on a "flat" one, but never quantifies either.
    steep_slope_pct_per_day: float = 0.30   # CALIB: ≥0.30%/day = steep
    flat_slope_pct_per_day: float = 0.10    # CALIB: <0.10%/day = flat (no action / range mode)
    slope_lookback_days: int = 5            # CALIB: window for slope measurement

    # Shake-out detection — the book: "sharp drop" with CMF between −0.1 and +0.1.
    shakeout_drop_pct: float = 0.10         # CALIB: ≥10% drop over the window = sharp
    shakeout_window_days: int = 5           # CALIB

    # Support/resistance detection (docs/03 discussion; book gives strength factors,
    # not detection parameters).
    pivot_window: int = 5                   # CALIB: bar must be extreme vs ±5 bars
    level_cluster_tolerance: float = 0.02   # CALIB: pivots within 2% cluster into one level
    level_lookback_days: int = 250          # CALIB: ~1 year of dailies
    min_level_touches: int = 2              # CALIB: a level needs ≥2 pivots

    # Volume fade — book: "volume declining as price rises"; quantify the decline.
    # 2026-07 sweep (backtests/grid_agg.csv): 0.30 dominated 0.15/0.20 — a deeper
    # required volume drop avoids selling calls into still-running trends (NVDA).
    fade_volume_drop: float = 0.30          # CALIB: ≥30% volume drop from recent peak while price rises
    volume_avg_period: int = 50             # CALIB: average-volume window

    # Event hygiene
    event_close_window_days: int = 5        # CALIB: close threatened shorts within 5 days of a binary event


@dataclass(frozen=True)
class Config:
    book: BookRules = field(default_factory=BookRules)
    calib: Calibrated = field(default_factory=Calibrated)


DEFAULT = Config()
