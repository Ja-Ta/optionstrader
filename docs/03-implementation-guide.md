# Implementation Guide — Running the Strategy Realistically

How the system operates as a repeatable process, and what an application must automate. Written against the book's procedures, adapted where the 2007-era assumptions no longer hold.

---

## 1. Portfolio structure

```
Total capital
├── 2/3  Long-term "cash generation" account
│        ≤ 8 stocks, held months to a year+
│        Entered via half/half put selling
│        Covered calls sold continuously at resistance
│        Puts sold at support to add on strength
│        Exits driven by weekly CD (relative-strength) charts
│
└── 1/3  Short-term trading account
         Stock trades held days to weeks (technical setups)
         Squeeze / earnings-squeeze / special plays
         Options only as short-term enhancers
         Target: ~10%/month compounded (book's goal; see 05-success-metrics)
```

Regime rule: sideways market → lean on the long-term account's premium engine; trending market → lean on short-term trading.

## 2. Stock selection (the universe)

Long-term account candidates need all of:
- **Optionable, liquid options** — meaningful open interest at several strikes/months; penny-wide markets preferred (the book's rules assume you can trade in and out of premium cheaply).
- **Enough volatility to pay rent** — the strategy is pointless on names whose 2–4-month OTM premium is negligible; the book's stocks were volatile tech/energy names. Practical screen: options at strikes ~10% OTM, 2–4 months out, yielding ≥ 2–3% of stock price.
- **Clear chart structure** — identifiable support/resistance; "if you can't see the pattern, don't trade it."
- **Fundamental acceptability** — you must be willing to own more at the put strike (sector strength, earnings trajectory; the book screens sector first in weak markets, e.g., CHK: P/E 5.6, 40% growth).
- **Price tier vs. account size** — small accounts (< $25k): stocks under $15 (preferably under $10) so the 2%-risk rule still buys meaningful size; larger accounts can hold higher-priced names (bigger absolute premiums).

Short-term scanner (the book's 10-condition reversal screen, directly codable):
1. price > $5, 2. price < $10 (scale to account), 3. %price change < 50, 4. %volume change > 25, 5. avg volume > 250k, 6. close > prior close, 7. volume > prior volume, 8. trailing stop level rising, 9. yesterday price < stop level, 10. today price > stop level. Triage every hit into **eliminate / daily-watch / enter within 2 days** (criteria in 04-key-rules-reference §8). Best candidates: volume spike with only modest price movement. A good scan returns ≤ ~10 names.

## 3. The operating cadence

**Daily (15–30 min after the close)** — the book's stated workload:
1. Update indicators per holding: MA(10)/EMA(20)/EMA(30), 20-day CMF, volume vs. average; short-term: five-day oscillator, three-day difference, strength index, envelope buy/sell numbers.
2. Check news on each holding *and its sector peers* (peer warnings move your stock — and create buy-back opportunities on short calls).
3. Check calendar: earnings dates (own + sector), FOMC meetings, expiration Friday proximity.
4. Evaluate the decision matrix (§4) for each position; queue orders for tomorrow.
5. Review the daily-watch list from the scanner for triggered entries.

**Weekly (Monday close)**: compute CD value (stock ÷ index, normalized) for every long-term holding; update the semi-log trend. This is the long-term exit tripwire.

**Monthly**: short-interest screen (biggest days-to-cover increases → CMF/MA filter → at most one squeeze candidate); review expiration outcomes; re-derive support/resistance maps.

**Quarterly (Jan/Apr/Jul/Oct)**: earnings-season playbook — strong-economy vs. weak-economy sequencing of call/put sales around warnings and reports; earnings-squeeze candidates.

## 4. The per-position decision matrix (the heart of an app)

For each holding, each day, exactly one state applies. This is directly implementable as a state machine:

| State (signal) | Action |
|---|---|
| Uptrend confirmed, momentum strong (steep MA(10) up, CMF > +0.1, volume expanding) | Hold; no new calls yet; buy back short puts if at 25% of premium |
| Uptrend, momentum fading (volume down on rise, MA(10) curling, failed prior high) | **Sell covered calls** one strike above nearest resistance |
| Approaching support, downside momentum fading (1030/102030 upturn beginning) | Buy back calls (profit); **sell puts** one strike below support if willing to add |
| Confirmed breakdown (MA(10) below EMA(20), CMF < −0.1) | Defensive ladder: sell calls at nearest strike, roll down as it falls; stock exit if CD chart also broken |
| Sharp drop, CMF between −0.1 and +0.1 | Shake-out — do NOT panic sell; hold, look for the buy re-entry |
| Range-bound, flat MA(10) | Boxing mode: MA signals invalid; use volume + double top/bottom to time each side |
| Short option at ≤ 25% of collected premium | **Buy it back**, always |
| Short option ≥ 3/4 point ITM with ≤ 2 weeks left | Assignment imminent: roll (buy back, sell next strike out, later month if needed to fund) or accept assignment per plan |
| Binary event ≤ a few days away (earnings, FOMC) | Close threatened short options beforehand |
| CD chart deterioration (lower CD at same price / CD falls as price rises) | Begin exit: ITM call ladder down the strikes, sell stock on decisive CD breakdown |

Standing constraints checked on every order: never short calls beyond share count; never sell stock while short calls remain open against it; close existing calls before selling new ones; put sales require willingness + cash/margin for assignment.

## 5. Order mechanics and modern adaptations

The book is from 2007. Adaptations a realistic implementation should make:

- **Weekly options now exist.** The book's 2–5-month expirations were partly forced (monthly-only listings). The "2× premium for +1 month → take the later month" rule still applies, but the modern menu is richer; 30–60 DTE remains the sweet spot for premium-selling theta/gamma balance, consistent with the book's practice.
- **Commissions are ~zero, spreads are not.** The book's "let far-OTM options expire, don't waste commissions" now converts to "buy back cheap shorts is nearly free — do it." All edge calculations should use mid-to-bid realistic fills; ITM and sub-$5 options can have brutal spreads.
- **The sub-$5 ITM put play and bankruptcy plays need extra caution**: those premiums existed because of 2001–2002 panic-level IV; also many sub-$5 names today have no options or unusable spreads. Treat as opportunistic, not core.
- **Dividends matter** (the book's examples were non-payers): short ITM calls face early exercise ahead of ex-div dates — the app must track ex-div calendars.
- **Assignment is automatic at expiration for ≥$0.01 ITM** (the book's "3/4 point ITM + 2 weeks" heuristic applies to *early* exercise only; at expiration, anything ITM is assigned).
- **Pattern day trader rule**: the short-term account under $25k is constrained; the book's low-priced-stock guidance partially reflects this.
- **Regulation T / portfolio margin** on short puts: cash-secured is the book's assumption for entries; broker margin treatment varies (the LEAP loss-recovery play explicitly leans on marginable holdings).
- **Data**: everything the system needs is computable from daily OHLCV + options chains (bid/ask, OI) + short interest (bi-monthly now, not monthly) + an earnings/FOMC/ex-div calendar. No intraday data is strictly required except for the envelope limit-order tactic and price-rejection signals.

## 6. What an application must automate (build map)

> **Status (2026-07): built.** This section was the original blueprint; the
> application now exists (see docs/08-architecture-decisions.md for what was
> built and why, docs/07-validation-findings.md for the backtest evidence).
> Per-item status is marked below: ✅ built · ⚠ partial · ✗ deliberately not
> built (rationale in docs/08 §4) · ⏳ pending a user decision.

**Tier 1 — the core engine (highest value, fully mechanical):**
- ✅ Indicator pipeline: MA(10)/EMA(20)/EMA(30), 20-day CMF, volume stats, support/resistance detection (`indicators/`).
- ✅ Signal engine implementing §4's state machine per holding (`signals/engine.py`).
- ✅ Strike/expiration selector: resistance/support map → strike one level beyond; month chosen by the 2×-premium rule + open interest + event calendar (`options/selector.py`).
- ✅ Premium tracker: 25%-buy-back trigger, 3/4-ITM+2-week assignment watch, event calendar (`options/tracker.py`).
- ✅ Cost-basis ledger with premium-adjusted basis alongside honest mark-to-market (`portfolio/ledger.py`).

**Tier 2 — entries and portfolio:**
- ✅ Half/half put-sale planner (`options/planner.py`); 2%-risk position sizer; CD-chart calculator with the sell/buy tests (`indicators/cd.py`).
- ✅ Short-term scanner (10 conditions) with eliminate/watch/enter triage (`scanner/scanner.py`), plus the Ch-18 timing toolkit annotating its hits (`indicators/shortterm.py`).
- ⚠ 8-stock long-term portfolio manager: positions carry the long/short-term account split, but the ≤8 cap and portfolio-level notional checks are not yet enforced (roadmap).

**Tier 3 — episodic plays (optional modules):**
- ✅ Short-interest screen + CMF/MA filter with ITM-put-ladder and capped earnings-call suggestions (`scanner/squeeze.py`, `data/short_interest.py`).
- ✗ OI-imbalance expiration monitor — assessed as a decayed edge; deliberately not built.
- ⏳ Earnings-straddle scanner and MAC channel strangles — specified in docs/04 §4, buildable on demand.

**Tier 4 — validation (should come before live sizing):**
- ✅ Backtester with simulated broker, synthetic Black-Scholes pricing, buy-and-hold and naive-covered-call benchmarks, multi-ticker sweeps, and threshold grid search (`backtest/`). Findings and open questions: docs/07.
- ⏳ Validation on REAL historical option chains — pending a paid data feed; the single most important open item before live sizing.

## 7. Realistic guardrails (independent of the book)

- Cap single-name exposure (assignment on 2× puts can concentrate fast); cap total short-put notional at what the account can actually absorb in a crash.
- Treat the 2×-puts averaging-down move as requiring explicit user confirmation, never automatic.
- Log every rule violation the user overrides — the book's own thesis is that the system only works if followed.
- Paper-trade / backtest the timing layer before trusting it: the premium engine has documented edge; the timing overlay is the unproven (but testable) claim.
