# Key Rules Reference — Every Threshold, Formula, and Decision Rule

Consolidated rulebook extracted from the full text. Numbers are the book's; items marked ⚠ had OCR ambiguity or internal inconsistency in the source.

---

## 1. Covered-call rules

| Rule | Value |
|---|---|
| Target zone for strike | 10–20% above market → nearest strong resistance → strike **one level above** it |
| When to sell | Into fading strength only; never right after a steep fall |
| Post-crash gate | Stock must be ≥ **20% above its 20-day closing low** before selling calls |
| Momentum-fade triggers (any) | volume falling as price rises · MA(10) curling down · failure to exceed prior day's high |
| Buy-back trigger | Option at **25% of premium collected** (keep 75%) — never get greedy |
| Alternate lock trigger | ≥ 75% of premium captured **or** before a known catalyst, whichever first |
| Earnings months | Use a higher minimum strike (pre-earnings run-up risk) |
| Nearly-expired far-OTM shorts | Let expire (don't pay to close), unless assignment must be prevented |
| Roll-up on breakout | Buy back at a loss; finance with a new call one strike higher (later month if needed) |
| Willing-to-sell variant | Strike = your exit price; sell the call when stock is within 1/2 point below the strike |
| Absolute prohibitions | No calls beyond share count · no selling stock while short calls remain open · close old calls before selling new ones |

## 2. Put-selling rules

| Rule | Value |
|---|---|
| Precondition | Genuine willingness to own (more) stock at the strike, cash/margin ready |
| Trend gate | **1030 test**: 10-period MA crosses above 30-period MA (weekly for long-term) before averaging down |
| Strike | ~10% below market → nearest strong support → strike **one level below** it |
| Timing | Sell as stock approaches support with downside momentum fading; never at the exact low (unknowable) |
| Buy-back | Same 25%-of-premium rule |
| Sizing | Puts on up to **2× share count** acceptable (you own the stock); an aggressive, leveraged act — plan the assignment |
| Half/half entry | Sell puts on half the intended position at support strike; second half at next lower support if it falls |
| Willing-to-buy variant | Strike = your entry price; sell the put when stock is within 1/2 point above the strike |
| Roll-down | If assignment unwanted: buy back, sell next lower strike, later month funds the buyback |
| Ratio rule (boxing) | More **calls** than puts if bearish into expiration; more **puts** than calls if bullish |

## 3. Expiration & assignment

- **Month selection**: if the next month out pays **> 2× the near month's premium**, take the later month. Prefer large open interest. Typical book usage: 2–5 months out; January expirations favored for seasonal strength.
- **Early-exercise likelihood**: rare unless **both** (a) ≥ 3/4 point in the money and (b) ≤ 2 weeks to expiration. Don't panic-close a short the moment the strike is touched.
- (Modern note: at expiration, ≥ $0.01 ITM auto-assigns — the 3/4-point heuristic is for early exercise only.)
- Close short options before binary events (earnings, FOMC) that could gap through the strike.

## 4. Option-buying rules (the capped side bets)

| Rule | Value |
|---|---|
| Max price for bought calls | **$0.20/share** |
| Engineered max loss | $0.05/share (0.20 cost − 0.10 recouped via covered calls − 0.05 salvage) |
| Sequence | Buy the calls a few days **after** the stock (confirm direction first) |
| Exit deadline | Sell by **2 weeks before expiration** if target unmet; cut immediately if key support breaks |
| Earnings-squeeze calls | Lowest strike costing ≤ $0.20; budget ≈ **10% of ITM-put proceeds**; expiration **1 month past the *next* earnings** |
| Earnings straddle | Stock within **$0.10 of a strike**, volatile name, ≤ 30 days to earnings; size ≤ **2% of account** |
| Channel strangle (MAC) | Both legs ≤ $0.20/share; sell winner at the channel edge |
| Expiration OI fade | If call OI ≥ **2×** put OI at the key strike (or vice versa) days before expiration → buy the low-OI side |

## 5. Sub-$5 / ITM plays

- Sub-$5 stocks: sell ITM $5-strike puts; fund stock purchase from proceeds ("other people's money").
- Screen: **(strike − premium) ÷ stock price ≤ 0.75** (≥ 25% effective discount).
- Beginner exit (**50% rule**): buy the puts back once the stock closes 50% above your stock purchase price.
- ITM premium anatomy: intrinsic + time; time premium typically **5–30% of intrinsic**, by tenor and volatility.
- Directional ITM variants: CMF > +0.1 sustained (~6 months) → sell ITM puts (≈2× the cash of OTM). CMF < −0.1 in confirmed downtrend → sell ITM covered calls; buy back near support as intrinsic → 0.
- Squeeze ladder: sell ITM puts; when stock crosses the strike (intrinsic ≈ 0), buy back for time value only, re-sell next higher ITM strike while strength persists.

## 6. Technical indicator rules

**Moving averages (primary signal):**
- 1030 test: MA(10) × MA(30) cross (periods = days or weeks per horizon).
- 102030 test: MA(10) simple vs. EMA(20) vs. EMA(30). EMA formula: EMA = prior × (1−K) + price × K, K = 2/(N+1).
- Action requires a **steep** MA(10) slope change/cross; flat slope = no action; flat MAs (range) → switch to volume + double top/bottom signals.

**Chaikin Money Flow (secondary/confirming; 20-day):**
| Reading | Meaning |
|---|---|
| > +0.1 | Heavy accumulation; resistance likely breaks, support holds |
| 0 to +0.1 | Weak buying |
| 0 to −0.1 | Weak selling; during a steep drop = **shake-out** (support holds — do not panic) |
| < −0.1 | Heavy distribution; support likely breaks |
| ≤ −0.5 | Extreme distribution — never buy "cheap" against this |
- Duration above/below zero ∝ sustainability. Lower CMF peaks = fading buying; higher CMF lows = fading selling. Near ±0.1, weight higher-volume days.
- Precedence: **MA is primary, CMF confirms.** Act on MA weakness even with positive CMF (sell calls); sell stock only when CMF confirms negative.
- "Price surge point": MA(10) × EMA(20) upcross simultaneous with CMF flipping negative → positive.

**Volume rules:**
- Trade-day volume ≥ 10% above average required before initiating (scan step).
- Tell-tale accumulation spike: volume ≥ 20% above average (> 50% for sub-$5) **and** close 0–20% above open. Close down > 5% on heavy volume = distribution warning.
- Correction vs. reversal: falling volume on the decline + rising MA(10) = temporary (hold); rising volume on down days + flattening MA(10) = reversal (defend/sell).
- Continuation spikes (close above prior day's high) = re-entry points; enter 1–2 days after.

**ADX congestion breakouts:** candidate when ADX < 20 (prefer < 15); direction from MA(10) slope + CMF > 0 (relaxed), timing from stochastics convergence/cross; beginners wait for the actual breakout.

**MACD histogram divergence:** new price extreme without new histogram extreme (same trend only) = impending reversal. Confirmation ladder: histogram slope turn → MA(10) slope turn → MA(10) × EMA(20) cross.

**RSI / stochastics:** secondary only. RSI > 75 / stoch cross above 75 = overbought, < 25 = oversold — never act against CMF/MA on these alone.

**Candlestick reversals (Ch. 17):** trade only when all three hold — clear trend, reversal pattern, **and both** MACD and stochastics agree (oversold: stoch cross near 20, MACD cross near/below zero; overbought: stoch cross near 80). One confirming indicator is not enough.

**CD (convergence/divergence) charts — weekly relative strength:**
- CD = stock close ÷ index close, normalized ×10ⁿ into 1–10; plot weekly (same weekday, Monday preferred) on semi-log scale.
- **Sell/defend tests**: (a) CD falls while price rises; (b) CD at a given price on the way down < CD at that price on the way up.
- **Buy tests (new positions)**: (a) CD rising while price flat/falling in a range; (b) new price low **without** a new CD low — strongest if CD at the low ≥ CD from a price 25%+ higher; (c) price breakout with CD breakout (lower risk, less profit).
- Defensive ladder on CD weakness: sell ITM calls at next support strike; roll down as it falls; sell stock on decisive CD breakdown (lower highs/lows).
- Monthly CD acceptable for quiet stocks; beginners stay weekly.

## 7. Short-term arithmetic (Chapter 18)

- **Five-day oscillator** = (A + B) × 100 ÷ (2 × (5-day high − 5-day low)), where A = 5-day high − open 5 days ago, B = last close − 5-day low. Bands: 0–30 bearish, 30–70 neutral, > 70 bullish. ⚠ denominator garbled in OCR; verified from worked example.
- **Three-day difference** = today's oscillator − oscillator 3 days ago. Large positive = strong move coming; shrinking positive = rally fading.
- **One-day strength index** = (close − low) × 100 ÷ (high − low); same bands.
- Roles: oscillator = trend; difference = how far; strength = which day to enter.
- **Buy-vs-hold reconciliation**: > 70 = bullish for *holding*; for new *buys* want low readings turning up (buy weak-getting-stronger). Except Monday, only buy when oscillator < 40 (Friday exception: buy above 40 anticipating a strong Monday).
- **Buy/sell envelopes** (5-day validity; recalc every ~5 days): pivot A = (H+L+C)/3. Buy number = mean of [2A−H, prior low, low − avg₃(low−prior low), low − avg₃(prior high − low)]. Sell number = mean of [2A−L, prior high, high + avg₃(high − prior high), low + avg₃(high − prior low)]. Tactic: limit sell at the envelope **high**, good 5 days (sell numbers are touched intraday).
- **Five-day management**: exit if no close above sell number in 5 days; exit if intraday break of sell number closes back below; exit next day on any close below the buy number; on a close above the sell number, recalc and hold.
- **Measured move**: target = first-leg size + consolidation price; time target = first-leg days after breakout.
- **Fibonacci 0.618**: retracement entry zone; place stops **below** the 0.618 level (stop clusters sit at it).
- **Rule of threes**: momentum runs ~3 days before pulling back; breakouts succeed by the 3rd attempt or fail; a low that survives 3 tests is a bottom.
- Weekly cycle tendencies: Monday strongest; Tuesday sell-day after strong Monday; Thursday buy-day late; Friday soft open/strong close. Fine-tuning only — never a reason to buy by itself.

## 8. Screening & triage (Chapter 19)

- Scan (see 03-implementation-guide §2 for the 10 conditions); target ≤ ~25 charts to review.
- **Eliminate**: already ran up · volatile on daily *and* weekly · negative CMF divergence · no clear pattern ("if in doubt, opt out").
- **Daily watch**: big one-day jump on heavy volume (pullback likely) · flags/pennants/rectangles/ascending triangles pre-breakout (unless heavy OBV positive divergence) · VPV awaiting re-test.
- **Enter within 2 days**: falling rectangles · falling wedges · breakaway gaps (wait 1 day; enter on pullback to 20-day EMA/support) · MACD-histogram divergences. Trigger = breakout on rising volume. Falling-rectangle pre-breakout entry allowed after a failed heavy-volume attempt + shrinking-volume pullback, on attempt 2–3.
- Buy at next open only if it opens within **2% of prior close**; otherwise limit order.

## 9. Money management & risk

- **Max loss per trade = 2% of account.** Shares = (2% × account) ÷ (entry − stop).
- **15% stop-loss**: any stock closing 15% below purchase is sold.
- Stops: mental (re-evaluate on close-below, act next day) or placed unpredictably — below the 0.618, at envelope numbers, or at the average of the past 5 lows. Never at obvious support/MA/trendline levels (stop-running).
- Use **mental stops when short calls are open** (an auto-stop can leave you naked short calls intraday); if stopped, exit stock *and* buy back the call together.
- Hedges: ITM covered call into an expected dip (breakeven = cost − premium); inverted collar (short ITM call + long OTM put; max risk = (stock + put cost) − (put strike − call premium), risk-free if negative); bull put spread guarding the put program (long put one strike below the short-put support, later month).
- Behavioral: plan every outcome before entry · take losses as system output · sit out when there's no signal · specialize in one pattern type · never convert a short-term trade into a hold.

## 10. Market & calendar overlay

- Trade with the index trend (~2 of 3 stocks follow it). Confirm the index uptrend before stock-level bullish trades.
- Market bottom timing: high days-to-cover (crowd short) **plus** VIX/VXN MACD(12,26,9) upward crossover (plot inverted; absolute VIX levels unreliable).
- Days to cover = shares short ÷ average daily volume; monthly screen on biggest increases.
- Seasonality: November–March strong (January strongest, especially low-priced names); author sells in late Feb/March. Earnings months: Jan/Apr/Jul/Oct; warnings cluster in the last 2 weeks of the pre-earnings month.
- Economy regime: weak economy → sell calls before warning season, buy back into the dip, sell puts, expect post-earnings relief bounce. Strong economy → sell calls into pre-earnings run-ups, expect sell-the-news, then sell puts.
- Analysts as contrarians: upgrade near a high = sell signal; downgrade near a low = buy signal; near the opposite extreme, wait a couple of days.

## 11. Source-quality flags (⚠)

Numbers with OCR or book-internal inconsistencies found during extraction — verify before hard-coding: LSI cumulative cash ($4,050 vs $4,500 in one leg); MCK premium sums (±$10s); JDSU one basis step (−$0.65 printed where −$0.85 computes); inverted-collar max-profit formula sign; KONG one three-day-difference value (26 computed vs 29 printed); five-day-oscillator denominator (2× range, confirmed by worked example); CHK "$7.30" resistance line (likely $7.50). None change the strategy logic.
