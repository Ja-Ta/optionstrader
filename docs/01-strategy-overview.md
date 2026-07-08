# Strategy Overview — What the System Actually Is

The book presents one coherent system with a core engine and five supporting layers. Everything in its 20 chapters serves one of these six roles.

---

## The core engine: continuous premium harvesting on stocks you own

**Mental model:** a stock is a rental property. Option buyers are tenants paying for the *right* to buy your shares (calls) or the *right* to sell you shares (puts). The owner's job is to keep the property rented — continuously selling time value and keeping the rent when the options expire worthless or get cheap.

The engine has four moving parts:

### 1. Sell covered calls at resistance
- Identify the chart's nearest strong **resistance** to a price 10–20% above market. Sell calls at the strike **one level above that resistance**, so the stock is unlikely to reach it before expiration.
- **Timing**: sell into strength, but only *fading* strength. Never sell calls immediately after a crash (wait until the stock is at least 20% above its 20-day closing low) and never into fresh news-driven momentum. The three momentum-fade signals that trigger the sale:
  1. Volume declining while price still rises
  2. The 10-day MA beginning to curl over (102030 test)
  3. Failure to take out the prior day's high (short-term double top)

### 2. Sell cash-secured puts at support
- Only on stocks you're genuinely willing to buy (more of) at the strike. Strike = one level **below** the nearest strong support (targeting ~10% below market).
- Prerequisite before averaging down: the **1030 test** (10-period MA crossing above the 30-period MA) or the fuller **102030 test** — never sell puts into a stock still making new lows.

### 3. Harvest early and recycle — the 25% buy-back rule
The single most repeated rule in the book: **buy back any short option once it trades at 25% of the premium you collected** (locking in 75%), then re-sell on the next swing. Don't hold to expiration for the last dime — velocity of premium capture beats maximum capture per trade. Close positions ahead of binary events (Fed meetings, earnings) that could move against a short option.

### 4. The "cat and mouse" / boxing cycle
On a range-bound stock this becomes a repeating loop:
- Price approaches resistance → sell calls; buy back previously sold puts at a profit.
- Price approaches support → sell puts; buy back the calls at a profit.
- Both sides short simultaneously = the stock is "boxed"; you profit whichever way it moves.
- **Ratio rule**: sell more of whichever side you expect to expire worthless — more calls if you lean bearish into expiration, more puts if bullish. Selling puts on **2× your share count** is endorsed (you own the underlying and would accept assignment); selling calls on more shares than you own is forbidden.
- **Breakout handling**: if the range breaks, buy back the losing side at a loss and *finance the buyback* by selling the next strike out (calls one strike up on an upside break; puts one strike down on a downside break), while taking profit on the other side. If support breaks and becomes new resistance, the call strike moves down with it.

The effect over months is a relentless reduction of cost basis. The book's case histories (LSI: $10 → $5.10 basis in 4 months; QCOM: $45 → under $30 in 3 months; JDSU: $12.50 → $2.85) all demonstrate the same arithmetic: premium in, basis down, until the stock is owned "at zero cost."

---

## Layer 1: Entries — get paid before you buy ("half/half put selling")

The author states he rarely buys stock outright. To open a position:
1. Pick the target buy price at chart support; wait until the stock trades near the strike (fattest premium).
2. Sell puts on **half** the intended position at that strike.
3. If the stock falls further, sell puts on the second half at the next lower support strike and let the first lot be assigned — the blended cost lands well below the original support.
4. If the stock rises instead, keep the premium and repeat on the next dip.
5. The moment shares are assigned, the core engine starts: sell covered calls at resistance.

**Sub-$5 stocks** (where $5 is the lowest strike): sell deep in-the-money $5 puts and use part of the proceeds to buy the stock — "other people's money." Beginner exit: buy the puts back once the stock closes 50% above your stock purchase price. Screen: only take it when (strike − premium) / stock price ≤ 0.75 (a ≥25% effective discount).

## Layer 2: Defense — repairing losers without new cash

- **Rolling covered-call ladder on a falling stock**: as soon as the downtrend is confirmed (MA(10) crosses below EMA(20)), sell calls at the nearest strike; buy back at 25% of premium as the stock falls; re-sell at the next lower strike; repeat. The MCK case history recovered a 79% loser to break-even this way; the Enron chapter shows the same ladder recovering losses on a stock headed to zero.
- **Averaging down with premium, not cash**: only after the 1030 test confirms a bottom, sell puts at support and let assignment double the position — funded entirely by accumulated premium (MCK: share count doubled with no out-of-pocket cash).
- **Directional ITM variants** (experienced users): with CMF persistently below −0.1 in a downtrend, sell *in-the-money* covered calls (capturing intrinsic + time as the stock falls); with CMF persistently above +0.1 for ~6 months, sell *in-the-money* puts (roughly double the cash of OTM puts).
- **Hedging a temporary pullback you expect**: sell ITM covered calls into the dip and buy them back at the reversal signal; or an "inverted collar" (ITM call sold + cheap OTM put bought); or protect the put-selling program with a bull put spread (buy the strike below your short-put support).

## Layer 3: Timing — the technical system that drives every decision

The book is emphatic that the option mechanics are worthless without timing. The hierarchy:

1. **Primary signal — moving averages**: the 102030 test. Uptrend = MA(10) above EMA(20) above EMA(30); action triggers are *steep* MA(10) slope changes and crossovers. A flat MA(10) means *no action* — switch to volume/double-top signals in ranges.
2. **Secondary/confirming signal — Chaikin Money Flow (20-day)**: ±0.1 bands. CMF > +0.1 = institutional accumulation (resistance likely breaks, support holds); CMF < −0.1 = distribution. Its killer application is distinguishing a **shake-out** (sharp price drop with CMF between −0.1 and +0.1 → buying opportunity) from a real breakdown.
3. **Long-term exit signal — CD charts** (the book's own invention): weekly, plot stock price ÷ index value on semi-log paper. Sell/defend when the CD value is lower at the same price than it was on the way up, or falls while price rises. Buy only on exceptional strength (new price low *without* a new CD low). This is the designated exit tool for the long-term account.
4. **Setup identification — chart patterns**: falling wedges and falling rectangles are the most bullish patterns in the book (claimed >95% breakout rate for falling rectangles); PVP/VPV trendline-retest reversals; breakaway gaps (enter on the pullback to the 20-day EMA, not the gap itself).
5. **Short-term precision — Chapter 18 arithmetic**: five-day oscillator, three-day difference, one-day strength index, buy/sell envelopes (pivot-style computed targets), Fibonacci 0.618 retracements, the "rule of threes," and day-of-week tendencies. These decide *which day and price* to act, never *whether*.
6. **Market overlay**: only trade with the index trend; time market bottoms with VIX/VXN MACD crossovers plus days-to-cover extremes; seasonality (November–March strong, January strongest — used to pick expiration months for short puts).

## Layer 4: Episodic special plays (bounded, occasional)

- **Short squeeze** (target: one per month): monthly screen for the largest short-interest increases, keep only names where CMF/MA show genuine accumulation, then sell ITM puts and ladder the strike up as the squeeze runs.
- **Earnings squeeze** (up to four per year): a squeeze candidate into earnings — sell ITM puts, plus OTM calls capped at $0.20/share funded by ~10% of the put proceeds, expiration one month past the *next* earnings report.
- **Distressed/bankruptcy bounce** (1–2 per year): after a bankruptcy panic with heavy short interest, sell the panic-inflated ITM puts and buy stock with the proceeds; exit into the short-covering pop (Enron: $67k in 4 days, no own cash).
- **Earnings straddle**: volatile stock within $0.10 of a strike, <30 days to earnings — buy the straddle, sized at 2% of account.
- **Expiration open-interest fade**: days before monthly expiration, if call OI ≥ 2× put OI at the near strike (or vice versa), buy the low-OI side.
- **Loss-recovery LEAP play**: deep-ITM long-dated puts sold after a confirmed reversal, sized to recover ≥50% of a prior loss (the Lucent case: $38k of a $39k loss recovered).

## Layer 5: Portfolio architecture (the Epilogue's final plan)

- Split capital **1/3 short-term trading account / 2/3 long-term holding account**.
- **Long-term account**: no more than 8 stocks, entered via put selling, exited on CD-chart weakness, with covered calls sold continuously and puts sold to add on strength. This account produces the baseline "20%+ per year cash" even in flat markets.
- **Short-term account**: technical trades held days to weeks, target ≥10%/month compounded, options only as short-term enhancers; feed on squeeze and earnings-squeeze candidates.
- **Regime switch**: sideways market → emphasize premium selling in the long-term account; trending market → emphasize short-term trading.
- Money management: max loss per trade = 2% of account (position size = 2% ÷ per-share risk to stop); 15% hard stop on any stock position; mental stops or stops placed at unpredictable levels.

---

## What the strategy is NOT

Worth stating for implementation scope:
- It is **not** a pure options strategy — every core position is anchored in stock ownership (or intent to own). Naked calls are explicitly forbidden; the only "naked" puts are cash-secured ones on stocks the trader wants.
- It is **not** buy-and-hold with income sprinkled on — the timing system overrides fundamentals everywhere, and the book repeatedly sells or defends positions the moment technicals break, regardless of story.
- It is **not** high-frequency — the stated workload is 15–30 minutes after each close, one weekly CD calculation per holding, and one monthly short-interest screen.
