# Getting Started — A First Month with optionstrader

A practical, beginner-friendly walkthrough: what the app does, how to set it
up, and a realistic "first month" of commands showing one full turn of the
strategy's engine. Written for someone with a *basic* understanding of
options (you know what a call and a put are; you've maybe never sold one).

**Three framing rules before anything else:**

1. **The app never trades.** It screens, plans, checks, and records. *You*
   place every order at your own broker, then log the fill with `record`.
   Think of it as a disciplined co-pilot enforcing the strategy's rules.
2. **Paper-trade your first month.** Run everything below against a paper
   (simulated) account at your broker, or simply on paper. The app can't
   tell the difference and neither will your learning.
3. **Educational software, not financial advice.** All tickers and prices in
   this guide are illustrative. Realistic expectations are in docs/05 —
   think "meaningfully enhanced income on stocks you'd own anyway," not the
   spectacular figures the source book advertises (docs/02 explains why).

---

## 1. The ideas in plain language (5 minutes)

**Selling a covered call.** You own 100 shares. You sell someone the right
to buy them from you at a higher price (the *strike*) by a certain date
(*expiration*). They pay you cash now (the *premium*), yours to keep no
matter what. If the stock never reaches the strike, the option expires
worthless — you keep the shares AND the premium, and you can sell another.
That repeated collection is the engine of this whole strategy: the book's
metaphor is renting out a property you own.

**Selling a cash-secured put.** You promise to buy 100 shares at a lower
price (the strike) if the stock falls there by expiration, and you're paid
a premium for that promise. You set aside the cash to honor it. If the
stock stays up, you keep the premium. If it falls and you're *assigned*,
you buy shares you wanted anyway — at a discount, since the premium reduces
your effective cost. The strategy uses this as its standard way to ENTER
positions: get paid to buy.

**The one rule to internalize first: the 25% buy-back.** After selling any
option, the app will tell you the price at which to buy it back — 25% of
what you collected. Closing there locks in 75% of the premium and frees you
to sell again on the next swing. Velocity beats squeezing out the last dime.

**What the timing signals do.** The app reads price/volume behavior (moving
averages, money flow, support/resistance) to answer: is momentum fading
(time to sell a call)? is the stock at support with sellers exhausted (time
to sell a put)? is a sharp drop a fake-out or a real breakdown? You don't
need to compute any of it — the daily report does — but docs/01 explains
each signal when you're curious.

## 2. Setup (15 minutes, one time)

```bash
git clone https://github.com/Ja-Ta/optionstrader && cd optionstrader
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -q        # 125 tests should pass — no keys needed
```

Create your watchlist (tickers you'd genuinely consider owning):

```bash
printf "SOFI\nRIG\nF\nPLUG\n" > watchlist.txt
```

Optional but recommended — the automated daily report (file always; email if
you configure it):

```bash
cp .env.daily.example .env.daily     # fill in SMTP details, or skip email
crontab -e                           # add:  45 16 * * 1-5 /path/to/optionstrader/scripts/daily_cron.sh
```

Everything below uses `.venv/bin/optionstrader ...`; alias it to save typing:
`alias ot=$PWD/.venv/bin/optionstrader`

## 3. Week 1 — find candidates and wait for your pitch

**Day 1: can these stocks even pay rent?**

```bash
ot screen SOFI RIG F PLUG AMD MARA --verbose
```

The screen checks whether each stock's options are *capable* of meaningful
income (yield, liquidity, chart structure, not-in-freefall). Expect most
names to FAIL — an empty or short list is information ("the rent isn't
worth it here right now"), not a bug. Suppose `SOFI` passes with a healthy
put yield. That makes it a *candidate*, not a buy: the final call — "would
I be happy owning 500 shares of this at a lower price?" — is always yours.

**Day 1, continued: what does the chart engine think?**

```bash
ot analyze SOFI --levels
```

You'll see the trend state, money flow, and the detected support/resistance
levels. Say support shows near $16 with SOFI trading at $17.20. The
assessment might read `state: approaching_support` — that's the setup the
entry method wants.

**Day 2: plan the entry (nothing is bought yet).**

```bash
ot plan SOFI --shares 1000 --cash 20000
```

The planner proposes the book's two-tranche entry, something like:

```
tranche 1 (half): sell 5x 15.5 put exp <~2 months out> @ ~0.55
    → effective cost 14.95 if assigned, cash to secure $7,475
tranche 2 (half): sell 5x 14 put ONLY if the stock keeps falling
status: WAIT — price 17.20 is far above the strike; premium too thin
```

**WAIT is a verdict, not an error.** The plan tells you the trigger price.
You check the report each afternoon and do nothing until the market comes
to you. (If your cash can't secure the puts, the planner refuses — never
sell a put you can't take delivery on.)

**Day 4: the pitch arrives.** SOFI dips to $16.10. The daily report's
holding/watch sections flag it; re-running `plan` now shows READY. You sell
5 puts at your broker for $0.60, then log it:

```bash
ot record sell-put SOFI --strike 15.5 --expiry 2026-09-18 --contracts 5 --premium 0.60
#   → "$300 collected. 25% buy-back trigger: repurchase at ≤ 0.15"
```

That buy-back line is your standing order for the trade. From this moment
the daily report watches the position for you.

## 4. The daily rhythm (10 minutes after each close)

The cron job (or `ot daily --watchlist-file watchlist.txt`) delivers one
report. Read it top-down:

```
ACTION ITEMS (most urgent first):   ← if empty, you're done for the day
HOLDINGS:                            ← one block per position:
  SOFI @ 16.40 — state approaching_support, CD neutral, earnings in 33d
      ALERT [INFO] ... 45d remain — don't panic-close
WATCHLIST SCAN: 0 of 4 passed        ← zero hits most days is NORMAL
```

Plain-language translations of the states you'll see most:

| Report says | It means | You typically do |
|---|---|---|
| `uptrend_strong` | momentum intact | nothing — let it run |
| `uptrend_fading` | rally tiring near resistance | sell covered calls (it names the strike zone) |
| `approaching_support` | dip toward the floor | buy back calls cheap; sell puts if you want more shares |
| `shakeout` | scary drop, but no real selling | **hold — do not panic** (the strategy's most valuable rule) |
| `breakdown` | confirmed real weakness | defensive calls / exit path; read the notes |
| `range_bound` | sideways | the both-sides income cycle |

Action items are already sorted by urgency: expired options and stop-loss
breaches first, then buy-back triggers and assignment warnings, then
routine actions. Anything you execute at the broker, you `record`.

## 5. Weeks 2–4 — one full turn of the engine

**Scenario A: the puts expire (SOFI stays above $15.50).** The report says
so on expiration weekend; you log it and the premium is fully yours:

```bash
ot record expired SOFI --kind put --strike 15.5 --expiry 2026-09-18
#   → "$300 premium kept"
```

You're back at step "plan" — sell puts again on the next dip. This loop —
paid repeatedly for promises you never had to keep — is the quiet base case.

**Scenario B: assigned (SOFI closes at $15.10 at expiration).** You now own
500 shares at an effective $14.90 (strike minus premium) — the outcome you
*planned* for:

```bash
ot record assigned SOFI --kind put --strike 15.5 --expiry 2026-09-18
#   → "bought 500 @ 15.5 (effective 14.90) — start selling covered calls"
```

The engine's covered-call phase begins. A week later the report flags
`uptrend_fading` with resistance near $18 — you sell calls at the strike it
suggests (one level above resistance), say 5x $18.50 calls at $0.70:

```bash
ot record sell-call SOFI --strike 18.5 --expiry 2026-10-16 --contracts 5 --premium 0.70
#   → "25% buy-back trigger: repurchase at ≤ 0.18"
```

Two weeks on, SOFI drifts back to $16.60 and the calls trade at $0.15. The
report shouts it as an action item; you buy them back and bank 75%:

```bash
ot record buyback SOFI --kind call --strike 18.5 --expiry 2026-10-16 --price 0.15
#   → "captured 79% of premium ($275)"
ot status --price SOFI=16.60
#   → adjusted basis now ≈ 14.35 and falling — the book's scoreboard
```

Then you wait for the next fade signal and sell calls again. That
sell → 25% buy-back → re-sell loop, plus put sales at support, is the whole
core strategy. Everything else in the app protects it.

**The weekly check (Mondays, 2 minutes):**

```bash
ot cd SOFI --index ^GSPC
```

CD compares your stock's strength against the market. `neutral` — carry on.
`sell_defend` — read its reason; persistent relative weakness is the
strategy's long-term exit signal (treat it as a prompt for judgment, not an
automatic exit — see docs/07).

**The monthly screen (first weekend, 5 minutes):**

```bash
ot squeeze MARA COIN RIG BBAI F      # feed it a published high-short-interest list
```

Zero candidates most months is the correct outcome. When one appears, the
output explains the whole play. Skip this entirely until the core loop
feels routine.

## 6. When the app refuses you — that's it working

```bash
ot record sell-call SOFI --strike 18.5 --contracts 25 ...
# REFUSED: NAKED CALL refused: 2500 call-shares vs 500 held
```

Refusals and warnings (naked calls, selling stock while calls are open,
puts beyond your cash, oversized puts) are the book's survival rules
enforced at the moment of recording. If you're refused, the strategy — not
the software — is telling you no.

## 7. Beginner FAQ

- **The screen/scan/squeeze returned nothing. Broken?** No — selective by
  design. The book's scans routinely reduce twenty names to one or zero.
  Patience is a position.
- **Option quotes look odd after market close.** Free data shows zero bids
  after hours; the app falls back to last-trade prices and labels them.
  Re-check during market hours before acting on borderline numbers.
- **The daily email is in my junk folder.** Mark it "not junk" once.
- **How much should I trade?** The sizing rule is built in: risk no more
  than 2% of your account per trade, and never sell puts beyond cash you
  can deliver. Start with one position, one contract per tranche.
- **Do the backtest numbers predict my returns?** No. `backtest` uses
  synthetic option prices and says so on every run — it validates the
  *logic*, not the payout. Read docs/07 before believing any number.
- **When am I ready for real money?** After a full paper month you've
  recorded honestly: an entry, at least one 25% buy-back, one
  expiration-or-assignment, and no overridden refusals.

## 8. Where to go deeper

| Question | Read |
|---|---|
| What is this strategy, really? | docs/01 |
| Is it actually a good strategy? (honest assessment) | docs/02, docs/05 |
| Every rule and number the app enforces | docs/04 |
| Where a book rule lives in the code | docs/09 |
| What's proven vs. assumed | docs/07 |
