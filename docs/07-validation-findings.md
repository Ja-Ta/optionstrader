# Backtest Validation Findings

Running log of what the Tier-4 harness has established. All results use
SYNTHETIC option pricing (Black-Scholes on realized vol × 1.2 IV premium,
5% friction) over a ~3-year window (mid-2023 → mid-2026, a strong bull
regime), 16-ticker mixed-regime universe. Treat as evidence about the
*timing logic*, not return forecasts. Raw data: `backtests/*.csv`.

## 1. Baseline sweep (2026-07)

- Median across the universe: buy-and-hold 69%, naive covered calls 71%
  (Sharpe 0.92), Elias engine 43% (Sharpe 0.61).
- The engine's wins clustered exactly where the book claims its edge:
  choppy/range names (TSLA, AMZN, MSFT beat naive; AMZN beat buy-and-hold).
- Its losses clustered in two failure modes: capped upside in monster bulls
  (NVDA, PLTR) and the **stop-out → surge-point re-entry whipsaw**
  (FCX lost money while the stock gained 72%; also F, T, COIN, INTC).
- Standing caveat: the fixed 1.2× IV premium mechanically favors whoever
  sells the most options — naive-cc by construction. Real IV premiums
  concentrate in high-fear chop, exactly where the engine's gates say sell.

## 2. Calibrated-threshold grid search (2026-07)

- Only `fade_volume_drop` mattered: 0.30 dominated 0.15/0.20 (adopted as the
  config default) — a deeper required volume drop stops premature call sales
  into running trends (NVDA +193 points on that change alone).
- The MA slope thresholds were NOT binding: the call-sale trigger fires on
  any of three fade signals and the volume signal fires far more often.
- Threshold tuning cannot close the gap to naive writing; the leaks are
  structural (whipsaw, capped bulls), not parametric.

## 3. CD relative-strength layer (2026-07)

Two mechanisms tested separately after the combined version failed:

**CD-triggered exits (EXPERIMENTAL, default OFF).** Median return fell
43% → 16%. Root causes: CD sell test (a) ("rising slower than the index")
is true of most stocks during an index bull run, and CMF < 0 is far too
weak a confirmation (it dips negative routinely inside healthy uptrends).
AAPL logged 18 CD actions in 3 years. Needs a stricter confirmation design
(e.g., require sell test (b)'s same-price divergence + an actual MA cross)
before it can be trusted.

**CD re-entry gate (default ON when an index series is provided).** Blocks
surge-point re-entry while the stock still underperforms its index.
Aggregate ~neutral (median 40.5% vs 43.0%), but tails matter:
- Repaired the whipsaw names (FCX +21, INTC +24, F +12) and transformed
  NVDA (+190 pts, Sharpe 0.94 → 1.49) and PLTR (+114, now beating naive).
- Cost AMD −93 pts: its baseline return came from re-entering rallies that
  began while it still lagged the index — a re-entry filter can only skip
  opportunities, and sometimes the skipped opportunity was the trade.
- Verdict: defensible default, not a proven edge. Re-test on real premiums.

**Indicator bug found by the flat-index invariance test:** CD sell test (b)
fired spuriously because its ±3% price-match band exceeded its 2% CD margin;
historical readings are now price-adjusted to the comparison price
(`indicators/cd.py`). This fix applies to the live `cd` command and daily
report as well. Related live-report note: sell test (a) fires frequently for
any index-lagging holding during bull markets — treat "CD deterioration"
action items as prompts for judgment, not automatic exits.

## 4. Open validation questions

1. All of the above on REAL historical option chains (ThetaData/Polygon) —
   the synthetic pricer both flatters naive-cc and understates put yields
   (no skew; live AMD 20%-OTM put yielded 34% vs 8.7% synthetic).
2. A bear/sideways regime window — this entire record is one bull market.
3. The 20/20/20 screen's qualification → performance link (blocked on real
   historical IV; the flat-vol proxy qualifies almost nothing).
4. Portfolio-level test: the book prescribes ≤8 *selected* stocks, not an
   arbitrary universe — repeat the comparison on screen-qualified names only.
