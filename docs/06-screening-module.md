# Candidate Screening Module — Modified 20/20/20

**Status: extension module, not part of the book's strategy.** The book gives no mechanical screen for selecting the ≤8 long-term account stocks (it assumes the reader already owns stocks). This module fills that gap only. It answers one question — *is this stock capable of generating the book's promised premium income?* — and hands its output to the book's own gates and rules, which are unchanged. No trading decision (strike, timing, sizing, management, exit) is made here.

---

## 1. Where it sits in the pipeline

```
Universe (all optionable US stocks)
        │
        ▼
[THIS MODULE] 20/20/20 capability screen + liquidity/structure legs
        │            "can this stock pay the rent?"
        ▼
Book's qualification gates (unchanged)
        │  willing to own at lower prices · sector strength · fundamentals
        │  clear support/resistance structure · index trend
        ▼
Human selects the ≤ 8 long-term holdings (as the author practiced)
        │
        ▼
Book's strategy takes over completely (docs 01/04)
        │  entries via half/half put selling at support strikes
        │  covered calls at resistance · 25% buy-back · CD-chart exits
```

Key property: the screen measures a stock's option chain at reference points (20% OTM) purely as a *yield gauge*. Actual traded strikes always come from the book's support/resistance map — the screen's reference strike and the traded strike are unrelated by design.

## 2. The three legs (reinterpreted for screening)

For each candidate, look at the put and call strikes nearest **20% OTM** at the expiration nearest **45–60 days** (a stable, comparable reference tenor):

| Leg | Test | What it proxies |
|---|---|---|
| **20% OTM** | A listed strike exists ≥20% from spot with a live market (nonzero bid, quoted size) | The chain is deep enough to support the book's strike-laddering (rolls, boxing, defensive ladders need strikes in both directions) |
| **20% annualized ROI** | Annualized premium yield at that reference strike ≥ 20%: `(bid ÷ collateral) × (365 ÷ DTE) ≥ 0.20`, put-side collateral = strike − premium, call-side = spot | The stock carries enough implied volatility that the book's income engine can plausibly hit its 20%/yr baseline; calm mega-caps fail this — matching the book's volatile-stock universe |
| **< 20 delta** | The reference strike's |delta| < 0.20 | The 20%-OTM premium is genuine time-value richness, not the chain pricing an imminent collapse; also confirms far-OTM strikes still behave like income strikes |

A stock passes the capability screen when both sides (put and call reference strikes) pass all three legs — the book's engine sells both directions, so one-sided richness (e.g., puts fat only because of crash pricing) is a red flag, not a pass.

## 3. Supplemental legs (the book's implied criteria, made explicit)

These come from the book's case-history practice (see 03-implementation-guide §2) and complete the module:

1. **Options liquidity**: open interest at the reference strikes and the two adjacent months; bid/ask spread ≤ ~10% of premium (the 25% buy-back rule dies in wide markets).
2. **Stock liquidity**: average daily volume > 250k (the book's own scan floor); price ≥ $5 (institutional-interest floor).
3. **Price tier vs. account**: price band scaled to account size (book: < $15 for small accounts; higher-priced names for larger accounts — bigger absolute premiums).
4. **Chart structure**: identifiable support and resistance levels within ±25% of spot (computable via the pivot-clustering detector, Tier 1) — "if you can't see the pattern, don't trade it."
5. **Not in freefall**: stock not making new 20-day lows, and passes the 1030 test direction check — this leg exists specifically so the ROI leg cannot select the book's forbidden falling-knife trades.
6. **Event hygiene** *(advisory, non-gating — revised 2026-07)*: flag when an earnings/binary event sits inside the reference tenor, since event-inflated premium overstates sustainable yield; re-measure after the event. Originally specified as a gate, but with quarterly earnings and a 45–75 DTE tenor an event is inside the window almost always, so as a gate it disqualified everything — and the book itself sells across earnings months (with higher strikes and event-exit discipline).

## 4. Output and ordering

- Output: a ranked capability list (rank by ROI leg, tie-break on liquidity), refreshed weekly. Target size ~10–25 names — the book's own calibration for a reviewable shortlist.
- The list is **advisory input to a human decision**, exactly as the author practiced: fundamentals/sector conviction and willingness-to-own cannot be screened, only checked. The app should present each candidate with its support/resistance map, trend state, and yield figures, and the user picks the portfolio.
- Re-screen holdings quarterly: a holding whose chain no longer passes (IV collapsed, liquidity dried up) stops paying rent and is a candidate for replacement at the next CD-chart exit — replacement *timing* remains the book's CD rules, never the screen.

## 5. Tunable parameters (defaults = 20/20/20)

| Parameter | Default | Note |
|---|---|---|
| OTM reference distance | 20% | Raising it narrows to very-high-IV names; lowering toward 10% converges on the book's own strike zone |
| Annualized ROI floor | 20% | Matches the book's baseline promise; in low-IV regimes may need lowering or the list goes empty — surface that regime fact to the user rather than silently relaxing |
| Delta ceiling | 0.20 | |
| Reference tenor | 45–60 DTE | |
| All supplemental thresholds | as listed | |

## 6. Feasibility finding (2026-07 backtest validation)

Implementing the screen surfaced a mathematical fact: the original spec's
"both put AND call sides must pass" requirement is **infeasible on the call
side** under lognormal option pricing. At 20% OTM / ~52 DTE, call ROI ≥ 20%
requires σ ≥ ~0.60, while call |Δ| < 0.20 requires σ ≤ ~0.50 — no volatility
satisfies both (lognormal drift puts far more probability above the +20%
strike than below the −20% strike). The put side has a genuine feasible band,
roughly **σ ≈ 0.70–0.88** at default thresholds.

Resolution: the screen **gates on the put side only** — faithful to the
rule's original intent ("delta = the chance we actually buy the shares",
i.e., short-put assignment). Call-side metrics are still computed and shown
as diagnostics. Consequence to be aware of: the put-side band σ ≈ 0.70–0.88
is a *narrow, very-high-volatility* admission window; in low-IV regimes the
list will often be empty, and that emptiness is information ("the rent
doesn't meet the target right now"), not a bug.

## 7. Known caveats

- The three legs jointly select high-IV names (roughly 60%+ IV at the default tenor). That matches the book's universe, but concentrates tail risk — which is why the willingness-to-own gate and the 2%-risk sizing rule downstream are non-negotiable.
- Delta approximates probability of expiring ITM; probability of the strike being *touched* during the trade is roughly 2× that. The screen's delta leg is a yield-quality gauge here, not an assignment promise — assignment odds on actual traded positions are governed by the book's strike placement and buy-back management.
- Yield measured at a point in time decays with IV; hence the weekly refresh and quarterly holding re-check.
