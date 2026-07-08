# Success Metrics — How the Strategy Defines and Measures Winning

## 1. The book's primary definition: cash generated, not stocks picked

The strategy's headline promise is a **20%+ annual cash return on stock holdings, on winners or losers, in addition to any capital gains** — e.g., >$50,000/year of option income on a $250,000 portfolio slice. Success is *cash flow against capital*, measured continuously, not terminal portfolio value against an index.

The book's own success ladder, from baseline to aspirational:

| Metric | Level | Where stated |
|---|---|---|
| ≥ 20%/year cash income on holdings | Baseline promise | Introduction, Ch. 2 |
| ≥ 10%/month compounded, short-term account | Stated account goal | Epilogue |
| ~12%/month average | Author's claimed personal average | Introduction |
| > 20%/month combined | Author's claimed two-year result | Epilogue |
| Case-history results | 21% in 4 months (JNPR), 34% in 75 days (LSI), 107% cash on cost (JDSU), 58–64% (CHK) | Ch. 2–12 |

(See 02-why-it-works — the 20%/year baseline is defensible in spirit; the monthly figures are era-specific and hindsight-selected and should not be encoded as targets.)

## 2. The operational scoreboard: cost basis marching to zero

The book's working metric per position is **premium-adjusted cost basis**: every dollar of net premium banked reduces the stock's effective cost. Success at position level = the basis trending steadily toward zero ("within a year or less your cost basis... will be below $5 and in many cases close to zero"). Two consequences the book uses deliberately:

- **Profit targets fall as basis falls.** LSI's "sell at 5×" target dropped from $50 to $36.75 as premiums accumulated — the strategy manufactures its own achievability.
- **"Cash to keep" is the score of each trade cycle**: the 75% of premium locked by the buy-back rule, plus whole premiums kept at expiration.

An implementation should show this ledger per position (basis, cumulative premium, current target) alongside honest mark-to-market P&L, because the book's own JDSU history shows the gap: 107% cash return on invested capital while the underlying fell 56% — mark-to-market, the premium engine *was* the profit.

## 3. Per-trade success criteria (mechanical)

A trade is successful and complete when any of:
- A short option is repurchased at ≤ 25% of collected premium (the standard win — 75% captured);
- A short option expires worthless (full premium kept);
- Assignment happens *as planned* (called away at the pre-chosen exit price + premium, e.g., SFA effectively sold at $67 vs. a $62 peak; or shares put at the pre-chosen entry price − premium);
- A bought option hits its plan (target price, channel edge, or the 2-weeks-before-expiry deadline) — with losses capped at $0.05/share net by construction.

A trade is a *managed loss* (still within-system) when: a breakout forces a financed roll; a bought call is cut at the support break; a stop closes stock + short call together. Failure is only exiting *outside* the pre-written plan.

## 4. Risk-adjusted definitions of success

Success is explicitly conditioned on never blowing up:
- No single trade may lose more than **2% of the account**; no position sized such that "I cannot afford to lose this" applies.
- The 15% stop-loss caps any stock-picking mistake.
- Success in adverse trades = how much premium was recovered on the way down (CHK: +14%/month with the stock *down*; MCK: a 79% loser exited at a small net profit). The book: how you handle trades that go against you determines overall success.
- Consistency over magnitude: the casino model — frequent small-to-medium captures, compounded ("even 3%/week or 15%/month compounded turns a few thousand into several hundred thousand"), rather than home runs.

## 5. Process metrics (leading indicators)

The book implies a cadence that an app can measure directly:
- Premium events per holding per quarter (case histories run 3–6);
- % of short options closed at the 25% trigger vs. bought back at a loss vs. assigned unplanned;
- Time-in-plan: % of actions taken that matched the pre-written playbook (the discipline metric the book cares most about);
- Workload staying within ~15–30 min/day, one CD calc per holding per week;
- Opportunity budget respected: ≤ 1 squeeze play/month, ≤ 4 earnings plays/year, 1–2 distressed plays/year, straddles ≤ 2% of account each.

## 6. Realistic targets for a modern implementation

Recommended scoreboard for the app, blending the book's definitions with the critical assessment in 02-why-it-works:

| Metric | Book's figure | Realistic modern expectation |
|---|---|---|
| Long-term account gross premium yield | 20%+/yr (to 12%/mo claims) | ~1–2%/mo gross in normal IV; more in high-IV regimes |
| Short-term account | 10%/mo compounded | Treat as aspirational; measure vs. benchmark instead |
| Benchmark | none used | Buy-and-hold of same stocks; BXM/PUT-style naive writing (the timing layer must beat these to justify itself) |
| Drawdown discipline | 2%/trade, 15% stop | Same — these transfer directly |
| Basis-to-zero ledger | primary scoreboard | Keep, but display alongside mark-to-market P&L |

Bottom line: the book defines success as **getting paid continuously for stocks you'd own anyway, capturing 75% of every premium sold, driving cost basis toward zero, and never taking an unplanned loss** — a definition that survives modernization intact even where the advertised percentages do not.
