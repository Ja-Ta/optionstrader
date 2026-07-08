# Why the Strategy Works — Author's Rationale and Critical Assessment

## Part 1: The author's case for why it's successful

### 1. The seller has the house edge
The book's foundational statistic: **over 75% of all options expire worthless**. Most option literature cites this as the *risk* of options; the book inverts it into the edge — be the casino, not the gambler. The system is overwhelmingly a *premium-selling* system; the few option-buying plays are tightly capped ($0.20/share, 2% of account) side bets.

### 2. Selling into crowd demand ("thinking outside the box")
Crowd psychology systematically overprices the option the crowd wants:
- When a stock rallies, the crowd bids up **calls** → that's exactly when the system sells calls (into fading momentum near resistance).
- When it falls, the crowd bids up **puts** → the system buys back its cheap calls and sells the now-expensive puts near support.

This is a sentiment-harvesting loop: the trader is always short the option the crowd is paying up for. The special plays (expiration OI fades, squeeze plays, bankruptcy bounces) are the same principle in concentrated form — "the majority is always wrong" at extremes.

### 3. Strikes anchored to structure, not to premium size
Strikes are chosen one level beyond real chart support/resistance, so the sold option needs the stock to do something it has repeatedly failed to do before expiration. Premium size never drives strike choice; structure does. This is why the book claims the calls "almost never" get exercised — and when they do (SFA called at $60), it was the planned exit at target anyway.

### 4. Velocity beats maximum capture
The 25% buy-back rule means each swing of the stock is monetized and the capital re-armed. A range-bound stock can be harvested several times per expiration cycle instead of once. The case histories consistently show 3–6 premium events per quarter on a single holding — this compounding of small captures is where the headline percentages come from.

### 5. Timing removes the classic covered-call failure modes
Naive covered-call writing fails two ways: selling calls on a stock that then collapses (premium is no cushion), and capping a stock that then rockets. The book's timing layer addresses both:
- The 1030/102030 tests and CMF keep the trader from selling puts into genuine breakdowns and from holding stocks in confirmed downtrends without defense.
- The momentum-fade rules stop the trader from selling calls into the *start* of a run (only into exhaustion near resistance), and the roll-up procedure (finance the buyback by selling the next strike up) preserves upside when a breakout is real.

### 6. Mechanical rules defeat fear and greed
A recurring theme: every dilemma (sell the loser? sell the winner? average down?) is answered by an indicator test, not judgment in the moment. Exits are planned *at entry* for every scenario (each case history writes the full contingency playbook before acting). The author attributes his results less to any single indicator than to never overriding the system.

### 7. It profits in all three market states
- Range-bound: boxing harvests both sides — this is actually the strategy's best regime.
- Downtrend: rolling call ladders + put selling at capitulation recover losses and accumulate shares cheaply.
- Uptrend: puts expire, calls are rolled up, stock appreciates.
The Epilogue's two-account structure institutionalizes this: premium selling carries flat markets, short-term trading carries trending ones.

---

## Part 2: Independent critical assessment

An application built on this book should encode the mechanics *and* respect the following reality checks.

### What genuinely holds up

- **The variance risk premium is real.** Implied volatility persistently exceeds realized volatility; systematic option sellers get paid for it. This is documented far beyond this book (CBOE's BXM buy-write and PUT put-write benchmark indices have decades of history showing equity-like returns with lower volatility). The core engine sits on a real, persistent edge.
- **"Most options expire worthless" is directionally right for OTM options**, and selling OTM strikes beyond support/resistance stacks a structural filter on top of the statistical one.
- **The early buy-back discipline is sound.** Short-option P&L is convex against you near the strike; captured premium at 75% has terrible remaining risk/reward. Modern practitioners converge on the same rule (typical guidance: close at 50–80% of max profit).
- **Selling puts only at prices you'd genuinely pay, on stocks you want**, is the correct way to run cash-secured puts — assignment becomes a planned entry, not a loss event.
- **The risk framework is legitimate**: 2% max loss per trade, no naked calls, position plans written before entry, event-risk avoidance (close before earnings/Fed), and stop placement away from obvious levels are all defensible practice.
- **The relative-strength idea behind CD charts is sound** — it's a hand-computed relative-strength (RS) line, a standard institutional tool. A stock underperforming its index at the same price on the way down *is* a meaningful distribution signal.

### What needs heavy discounting

1. **The headline returns are not realistic expectations.** "20%+ per month," "12%/month average," 100–170% annualized case histories — these come from (a) simple linear annualization of short windows, (b) hand-picked case histories written with hindsight, and (c) the 2001–2003 environment, when implied volatilities on beaten-down tech names were extraordinary (30%+ premiums on LEAPs, $2.35 premium on a $2.50 strike). In modern, low-IV markets on liquid names, systematic covered-call/put-write returns are single-digit to low-teens *annually* (the BXM/PUT indices are the honest benchmark). The *structure* of the strategy survives; the *magnitude* of the claims does not.

2. **Survivorship and selection bias in the case histories.** Every worked example ends well — including averaging down on McKesson through an 80% collapse and selling puts on Enron days before delisting worked out *in the example*. The same mechanics applied to a stock that keeps falling (or a bankruptcy that doesn't bounce) produce severe losses. Selling puts on 2× your share count is leverage, full stop: it doubles downside exposure below the strike. The book's own tests (1030, CMF) mitigate but cannot eliminate this; an app must treat "average down with 2× puts" as the highest-risk action in the system, not a routine one.

3. **Cost-basis accounting flatters the results.** "Driving cost basis to zero" counts collected premium against the stock's book cost while ignoring that the stock itself may be down. It's a useful discipline metric but not a substitute for mark-to-market P&L. (The JDSU history is honest about this: 107% cash return alongside a stock that fell from $12.50 to $5.50 — mark-to-market, the win came from the premium, not the shares.)

4. **The exotic edges have decayed.** The expiration open-interest fade ("the specialist pins the price"), day-of-week tendencies, and last-minute-markdown lore reflect a floor-specialist, pre-decimalization, pre-algorithmic market. Max-pain/pinning effects still exist but are far weaker and heavily arbitraged; weekday seasonality is not a dependable edge in 2026. These should be low-weight or omitted in an implementation.

5. **Some claimed probabilities are unverifiable.** ">95% of falling rectangles break out bullishly" has no cited sample. Pattern win-rates should be treated as hypotheses to backtest, not constants to hard-code.

6. **Frictions are excluded.** All book math ignores commissions (less of an issue now), bid/ask spreads (a big issue on ITM and low-priced options), assignment mechanics, early exercise around dividends (never mentioned — the examples are non-dividend tech stocks), margin requirements on short puts, and taxes (premium income is short-term ordinary gains in the US). A realistic implementation must model spreads and assignment explicitly.

### Net assessment

The durable core — **systematic covered calls at resistance + cash-secured puts at support on a small portfolio of quality volatile stocks, harvested at 75% of premium, with technical gates on when each side may be sold, hard position-size limits, and pre-planned exits** — is a legitimate, backtestable income strategy with a real (if modest) structural edge. The realistic ambition is meaningfully enhanced income and lower volatility versus buy-and-hold, roughly in the 1–2%/month gross premium range on suitable stocks in normal IV regimes, more when IV is elevated — not the book's 20%/month. The timing layer's value (CMF/MA gates, CD-chart exits) is plausible but must be validated by backtest rather than assumed.
