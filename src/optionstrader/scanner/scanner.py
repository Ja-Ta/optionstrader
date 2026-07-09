"""Chapter 19 reversal scanner (docs/04 §8, docs/03 §2).

The ten scan conditions identify the book's target setup — a heavy-volume
reversal from a downtrend — with EMA(20) as the trailing-stop line (one of
the book's suggested stop definitions). Conditions 9+10 are the reversal
flip: below the stop yesterday, above it today.

Every hit is then triaged into the book's three buckets:
  ELIMINATE   — already ran up · volatile on daily AND weekly · negative CMF
                divergence (mechanical proxies; "no clear pattern" needs eyes)
  ENTER-SOON  — bullish MACD-histogram divergence · breakaway gap (both
                computable; falling rectangles/wedges need chart review)
  DAILY-WATCH — everything else that passed (incl. big jump on heavy volume,
                which usually pulls back first)

Pattern recognition beyond these proxies is deliberately out of scope — the
book's own rule is "if you can't see the pattern, don't trade it", so the
scanner surfaces candidates and the human reads the charts.

Universe note: free data sources cannot sweep the whole market; supply a
candidate list (broker screener output, sector list, watchlist).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from ..config import Config, DEFAULT
from ..data.provider import DataProvider
from ..indicators import add_cmf


def _macd_hist(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.Series:
    macd = close.ewm(span=fast, adjust=False).mean() - close.ewm(span=slow, adjust=False).mean()
    return macd - macd.ewm(span=signal, adjust=False).mean()


@dataclass
class ScanParams:
    # The book's example targets a small account: $5-$10 stocks. Scale the
    # band to the account (docs/03 §2); the $5 floor is institutional-interest.
    min_price: float = 5.0
    max_price: float = 10.0
    max_runup: float = 0.50          # condition 3: % price change < 50
    runup_window: int = 60           # CALIB: window for condition 3
    min_volume_change: float = 0.25  # condition 4: % volume change > 25
    min_avg_volume: float = 250_000  # condition 5
    avg_volume_window: int = 50      # CALIB


@dataclass
class TriageResult:
    bucket: str                      # "enter" | "watch" | "eliminate"
    reasons: list[str] = field(default_factory=list)


@dataclass
class ScanReport:
    ticker: str
    price: float
    passed: bool
    conditions: dict[str, bool] = field(default_factory=dict)
    bucket: str = ""
    reasons: list[str] = field(default_factory=list)
    volume_ratio: float = 0.0
    day_change: float = 0.0
    timing: str = ""        # Ch-18 entry-timing numbers (populated for passers)

    def failed(self) -> list[str]:
        return [k for k, v in self.conditions.items() if not v]


def ten_conditions(df: pd.DataFrame, p: ScanParams) -> dict[str, bool]:
    """The book's ten conditions on a daily OHLCV frame (last row = today)."""
    close, vol = df["close"], df["volume"]
    stop = close.ewm(span=20, adjust=False).mean()   # EMA(20) as the stop line
    price = float(close.iloc[-1])
    avg_vol = float(vol.rolling(p.avg_volume_window).mean().iloc[-2])  # avg BEFORE today
    ago = close.iloc[-1 - p.runup_window] if len(close) > p.runup_window else close.iloc[0]
    return {
        "1_price_above_floor": price > p.min_price,
        "2_price_below_cap": price < p.max_price,
        "3_runup_under_50pct": (price / float(ago) - 1.0) < p.max_runup,
        "4_volume_change_over_25pct": float(vol.iloc[-1]) > avg_vol * (1 + p.min_volume_change),
        "5_avg_volume_over_250k": avg_vol > p.min_avg_volume,
        "6_price_up_today": price > float(close.iloc[-2]),
        "7_volume_up_today": float(vol.iloc[-1]) > float(vol.iloc[-2]),
        "8_stop_rising": float(stop.iloc[-1]) > float(stop.iloc[-2]),
        "9_yesterday_below_stop": float(close.iloc[-2]) < float(stop.iloc[-2]),
        "10_today_above_stop": price > float(stop.iloc[-1]),
    }


def _bullish_macd_divergence(df: pd.DataFrame, window: int = 60, recent: int = 10) -> bool:
    """New/retested price low with a HIGHER MACD-histogram low (same window)."""
    close = df["close"].tail(window)
    if len(close) < window:
        return False
    hist = _macd_hist(df["close"]).tail(window)
    earlier = close.iloc[: window - recent]
    i_min = earlier.values.argmin()
    p_low_early, h_early = float(earlier.iloc[i_min]), float(hist.iloc[i_min])
    p_low_recent = float(close.tail(recent).min())
    j = close.tail(recent).values.argmin()
    h_recent = float(hist.tail(recent).iloc[j])
    # The two lows must be DISTINCT: an intervening rally of ≥5% separates them
    # (a flattening histogram in one continuous slide is not a divergence).
    interim = close.iloc[i_min : window - recent]
    bounced = len(interim) > 1 and float(interim.max()) >= p_low_early * 1.05
    # Price at/below the earlier low (2% tolerance) while histogram is clearly higher.
    return bounced and p_low_recent <= p_low_early * 1.02 and h_early < 0 and h_recent > h_early * 0.5


def _breakaway_gap(df: pd.DataFrame, lookback: int = 2) -> bool:
    """Gap above the prior day's high on heavy volume within the last N days."""
    avg_vol = float(df["volume"].rolling(50).mean().iloc[-1])
    for i in range(-lookback, 0):
        if len(df) + i - 1 <= 0:
            continue
        gap = float(df["open"].iloc[i]) > float(df["high"].iloc[i - 1]) * 1.01
        heavy = avg_vol > 0 and float(df["volume"].iloc[i]) >= 1.5 * avg_vol
        if gap and heavy:
            return True
    return False


def triage(df: pd.DataFrame, cfg: Config = DEFAULT) -> TriageResult:
    """Book triage (docs/04 §8), mechanical proxies. Thresholds are CALIB."""
    reasons: list[str] = []
    close = df["close"]
    price = float(close.iloc[-1])

    # --- eliminate ---
    ran = price / float(close.iloc[-21]) - 1.0 if len(close) > 21 else 0.0
    if ran >= 0.20:
        reasons.append(f"already ran {ran:.0%} in 20d — the scan caught it late; low-risk entry gone")
    daily_sigma = close.pct_change().tail(60).std() * (252 ** 0.5)
    weekly = close.resample("W-MON").last().dropna()
    weekly_sigma = weekly.pct_change().tail(26).std() * (52 ** 0.5) if len(weekly) > 10 else 0.0
    if daily_sigma > 1.0 and weekly_sigma > 1.0:
        reasons.append(f"volatile on daily AND weekly (σ {daily_sigma:.0%}/{weekly_sigma:.0%}) — management-intensive")
    cmf = add_cmf(df, cfg)["cmf"]
    if len(cmf.dropna()) > 10:
        cmf_now, cmf_then = float(cmf.iloc[-1]), float(cmf.iloc[-11])
        if price > float(close.iloc[-11]) and cmf_now < min(cmf_then, 0.0):
            reasons.append(f"negative CMF divergence (price up, CMF {cmf_now:+.2f} and falling) — run-up likely temporary")
    if reasons:
        return TriageResult("eliminate", reasons)

    # --- enter within a couple of days ---
    if _bullish_macd_divergence(df):
        reasons.append("bullish MACD-histogram divergence — enter on breakout with rising volume")
    if _breakaway_gap(df):
        reasons.append("breakaway gap on heavy volume — wait one day to confirm the gap holds, then enter")
    if reasons:
        reasons.append("entry rule: buy next open only if within 2% of prior close; else limit order")
        return TriageResult("enter", reasons)

    # --- daily watch (default) ---
    day_chg = price / float(close.iloc[-2]) - 1.0
    if day_chg > 0.05:
        reasons.append(f"big one-day jump ({day_chg:+.0%}) on heavy volume — likely pulls back before continuing")
    reasons.append("watch daily for a pattern entry (flags/pennants/rectangles/VPV re-test need chart review)")
    return TriageResult("watch", reasons)


def scan_ticker(ticker: str, df: pd.DataFrame, p: ScanParams, cfg: Config = DEFAULT) -> ScanReport:
    conditions = ten_conditions(df, p)
    passed = all(conditions.values())
    avg_vol = float(df["volume"].rolling(p.avg_volume_window).mean().iloc[-2])
    report = ScanReport(
        ticker=ticker.upper(),
        price=float(df["close"].iloc[-1]),
        passed=passed,
        conditions=conditions,
        volume_ratio=float(df["volume"].iloc[-1]) / avg_vol if avg_vol else 0.0,
        day_change=float(df["close"].iloc[-1]) / float(df["close"].iloc[-2]) - 1.0,
    )
    if passed:
        t = triage(df, cfg)
        report.bucket, report.reasons = t.bucket, t.reasons
        from ..indicators.shortterm import timing_line

        report.timing = timing_line(df)  # Ch-18: the pattern says whether; these say when/where
    return report


def run_scan(tickers: list[str], provider: DataProvider, p: ScanParams | None = None,
             cfg: Config = DEFAULT) -> list[ScanReport]:
    p = p or ScanParams()
    reports: list[ScanReport] = []
    for t in tickers:
        try:
            df = provider.daily_ohlcv(t, lookback_days=300)
            reports.append(scan_ticker(t, df, p, cfg))
        except Exception as e:  # noqa: BLE001
            reports.append(ScanReport(ticker=t.upper(), price=0.0, passed=False,
                                      conditions={"data": False}, reasons=[str(e)]))
    order = {"enter": 0, "watch": 1, "eliminate": 2, "": 3}
    # Best candidates: volume spike with modest price move (book) — rank by ratio/|move|.
    reports.sort(key=lambda r: (not r.passed, order.get(r.bucket, 3), -r.volume_ratio))
    return reports
