# Book-to-Code Traceability Map

## Executive summary

This document maps every critical strategy point from the reference book
(Samir Elias, *Generate Thousands in Cash on Your Stocks Before Buying or
Selling Them*, 3rd ed., 2007) to the place in the `optionstrader` application
where it is implemented — or records, explicitly, that it was omitted and why.
It is the audit trail between the strategy spec (docs/01–05, distilled from
the book in our own words) and the code.

**Coverage at a glance:** the book's core cash-generation engine (covered
calls at resistance, puts at support, the 25% buy-back cycle), its timing
system (1030/102030, CMF, momentum-fade), its entry method (half/half put
selling), its exit tools (CD charts, 15% stop), its money management
(2% sizing, naked-call ban), its two-account architecture, its Chapter-18/19
short-term toolkit and scans, and its short-squeeze play are **implemented
and tested** (160 offline tests). A handful of episodic plays and
chart-reading techniques are **deliberately omitted** (§4) — each with a
recorded reason — and two book behaviors are **partially implemented** with
the gap noted. Nothing from the book was silently dropped: every known rule
is either in the map below or in the omissions table.

**How to read the map:** each row gives the strategy point (paraphrased),
its rulebook reference (docs/04 section — the numeric source of truth), the
implementation location, and status: ✅ implemented · ⚠ partial · ✗ omitted
(see §4) · ◇ extension beyond the book (see §5). File paths are relative to
`src/optionstrader/`.

**Note on the web UI:** `webapp/` (docs/08 D10) contains **no strategy
logic** — it renders the outputs of, and records through, the modules mapped
below. No row in this map points into `webapp/`, and that invariant should
hold for any future UI work.

---

## 1. The core engine

| Strategy point (book) | Rulebook | Implementation | Status |
|---|---|---|---|
| Covered-call strike: one level above nearest resistance (10–20% target zone) | 04 §1 | `options/selector.py::select_call_strike`; resistance from `indicators/levels.py` (pivot clustering) | ✅ |
| Sell calls only into *fading* momentum (volume fade, MA(10) curl, failed prior high) | 04 §1, §6 | `indicators/volume.py::analyze_volume` (fade signals) + `signals/engine.py` `UPTREND_FADING` state | ✅ |
| Post-crash gate: stock ≥ 20% above its 20-day low before selling calls | 04 §1 | `config.py::BookRules.post_crash_bounce`; enforced in `signals/engine.py::_call_sale_gates` | ✅ |
| **25% buy-back rule** (repurchase short options at 25% of premium; keep 75%) | 04 §1 | `config.py::BookRules.buyback_fraction`; fires in `options/tracker.py`, `signals/engine.py::_premium_triggers`, and backtests; `record buyback` reports capture % | ✅ |
| Put strike: one level below nearest support; only if willing to own | 04 §2 | `options/selector.py::select_put_strike`; willingness gate in `signals/engine.py::validate_order` and `record` | ✅ |
| 1030 / 102030 trend tests (MA(10) × MA(30); MA(10)/EMA(20)/EMA(30) alignment, steep-slope requirement) | 04 §2, §6 | `indicators/moving_averages.py::evaluate_1030 / evaluate_102030`; slope classes in `classify_slope` | ✅ |
| Expiration month: take the later month only if it pays > 2× the nearer | 04 §3 | `options/selector.py::choose_expiration` (with open-interest floor) | ✅ |
| Early-exercise heuristic: ≥ ¾-point ITM **and** ≤ 2 weeks to expiry | 04 §3 | `config.py::BookRules.itm_exercise_points / exercise_window_days`; `options/tracker.py::check_short_option` (incl. the "don't panic-close" informational case and the modern expiry auto-assignment note) | ✅ |
| Close short options before binary events (earnings/FOMC) | 04 §3 | `options/tracker.py` event warnings; `signals/engine.py` `CLOSE_SHORTS_BEFORE_EVENT`; earnings dates via the provider (FOMC calendar not tracked — see §4) | ⚠ |
| Boxing / cat-and-mouse in a range (calls at resistance, puts at support, flat-MA mode) | 01 layer-0 | `signals/engine.py` `RANGE_BOUND` state (volume + double-top signals replace MA when flat) | ✅ |
| Roll-up on breakout: buy the threatened call back, finance with the next strike up | 04 §1 | `backtest/strategies.py::EliasEngine` (roll-up handler); surfaced live as the tracker's roll-or-accept alert | ✅ |
| Defensive call ladder down a falling stock | 01 layer-2 | `signals/engine.py` `BREAKDOWN` → `DEFENSIVE_CALL_LADDER`; ladder execution in the backtest engine | ✅ |
| Shake-out vs. breakdown: sharp drop with CMF inside ±0.1 = hold, never panic | 04 §6 | `indicators/cmf.py::is_shakeout_flow`; `signals/engine.py` `SHAKEOUT` state checked **before** `BREAKDOWN` (ordering is load-bearing — docs/08 D6) | ✅ |

## 2. Entries, exits, accounts, and money management

| Strategy point (book) | Rulebook | Implementation | Status |
|---|---|---|---|
| Half/half put-sale entry (tranche 1 at support, tranche 2 at the next support down; blended cost math) | 04 §2 | `options/planner.py::plan_half_half`; `plan` CLI (READY/WAIT proximity trigger, cash-secured gate) | ✅ |
| CD (convergence/divergence) weekly relative-strength charts — the long-term exit tool (two sell tests, three buy tests, Monday anchoring, 1–10 normalization) | 04 §6 | `indicators/cd.py`; `cd` CLI; long-term positions' block in `daily.py`; backtest re-entry gate in `backtest/strategies.py` | ✅ |
| 15% stop-loss: sell any stock closing 15% below cost | 04 §9 | `config.py::BookRules.stock_stop_loss`; `portfolio/ledger.py::stop_loss_breached`; checked in `daily.py` and the backtest engine | ✅ |
| 2%-of-account position sizing (shares = risk budget ÷ per-share stop distance) | 04 §9 | `portfolio/ledger.py::position_size` (reproduces the book's 2,500-share worked example in tests) | ✅ |
| Naked-call ban; never sell stock while short calls are open; 2× put cap on owned stock | 04 §1–2 | `signals/engine.py::validate_order` + write-time enforcement in `portfolio/ledger.py::record_option_sale / sell_shares` (the `record` command refuses) | ✅ |
| Premium-adjusted cost basis as the scoreboard ("basis marching to zero") — alongside honest mark-to-market | 05 §2 | `portfolio/ledger.py::Position.adjusted_basis_per_share / mark_to_market`; `status` CLI | ✅ |
| Assignment as a *planned* event (puts = entry at strike − premium; calls = exit at target) | 04 §2 | `portfolio/ledger.py::record_assigned` (put assignment adds the lot at the strike and prompts "start selling covered calls") | ✅ |
| Two-account architecture (2/3 long-term ≤8 stocks; 1/3 short-term trading) | 01 layer-5 | `Position.account` routes tooling in `daily.py` (CD for long-term, Ch-18 for short-term); ≤8-stock cap and portfolio-level notional checks **not yet enforced** (roadmap, docs/08 §7) | ⚠ |
| Daily 15–30 min after-close routine; weekly CD; monthly squeeze screen | 03 §3 | `daily.py` + `daily` CLI + cron (`scripts/daily_cron.sh`, 16:45 ET weekdays, file + email delivery via `reporting.py`) | ✅ |

## 3. Screens, scans, and the short-term toolkit

| Strategy point (book) | Rulebook | Implementation | Status |
|---|---|---|---|
| Ch-19 ten-condition reversal scan ($5–$10 band, volume/price/stop-flip conditions; EMA(20) as the stop line) | 04 §8 | `scanner/scanner.py::ten_conditions` | ✅ |
| Scan triage: eliminate (ran-up / dual-frame volatility / negative CMF divergence) · watch · enter (MACD-histogram divergence, breakaway gaps) | 04 §8 | `scanner/scanner.py::triage`, `_bullish_macd_divergence` (with the distinct-lows validity rule), `_breakaway_gap` | ✅ |
| Entry rule: buy next open only if within 2% of prior close | 04 §8 | Emitted in triage output text | ✅ |
| Monthly short-squeeze screen: SI building + days-to-cover, then CMF/MA accumulation ("the shorts are right" and shake-out cases distinguished) | 04 §5 | `scanner/squeeze.py::assess_squeeze / screen_squeeze`; SI data via `data/short_interest.py`; `squeeze` CLI | ✅ |
| Squeeze play: ITM-put ladder (roll up as the stock crosses each strike) | 04 §5 | `scanner/squeeze.py::_attach_plays` (nearest ITM strike, intrinsic/time split, ladder instruction) | ✅ |
| Earnings-squeeze add-on: calls ≤ $0.20/share, ~10% of put proceeds, expiry one month past the *next* report | 04 §4–5 | `scanner/squeeze.py` (`SqueezeParams.max_call_price / call_budget_frac`; expiry targeting) | ✅ |
| Tell-tale volume spike (volume ≥ 20% above average with close 0–20% above open) | 04 §6 | `indicators/volume.py` (`telltale_spike`) | ✅ |
| Ch-18 five-day oscillator, three-day difference, one-day strength index (trend / how far / which day) | 04 §7 | `indicators/shortterm.py` — pinned to the book's worked-example numbers in `tests/test_shortterm.py` | ✅ |
| Ch-18 buy/sell envelopes + the five-day management rules (exit on close below buy number, failed intraday break, recalc on close above sell number; limit sells at the envelope high) | 04 §7 | `indicators/shortterm.py::compute_envelope / manage_five_day`; surfaces on scan hits (`ScanReport.timing`), short-term holdings in `daily.py`, and `analyze --short-term` | ✅ |
| Oscillator band reconciliation (>70 = hold-bullish, but new *buys* want low-and-turning readings) | 04 §7 | `indicators/shortterm.py::band` docstring encodes the distinction; buying logic remains human | ✅ |

## 4. Relevant omissions — book material *not* implemented, and why

Every omission is deliberate and recorded (rationale detail: docs/08 §4).

| Book topic | Why omitted | Where discussed |
|---|---|---|
| Freeform chart patterns (falling wedges/rectangles, H&S, cup-and-handle, PVP/VPV re-tests) | Book's own rule: "if you can't see the pattern, don't trade it." Mechanical detection has high false-positive rates; the scanner surfaces candidates and defers to human chart review | docs/08 D-boundaries; scanner docstring |
| Candlestick reversals + stochastics/MACD triple confirmation (Ch-17) | Computable but deferred; swing-trade tool outside the current accounts' workflow. Buildable on request | docs/03 §6 (⏳) |
| Day-of-week weekly cycles (Monday strong, etc.) | Assessed as a decayed 2007-era edge; encoding would add false authority | docs/08 §4 |
| Expiration open-interest fade ("bet against the majority near D-day") | Assessed as largely arbitraged away in modern market structure | docs/02 §2 |
| Sub-$5 ITM put program (50% rule, 25%-discount screen) and bankruptcy-bounce play | Era-specific: relied on 2001-02 panic-level premiums; many sub-$5 names today have unusable option markets. Treated as opportunistic manual plays, not modules | docs/02 §2 |
| Earnings straddle and MAC channel strangle scanners | Specified in the rulebook (04 §4) and cheap to build; awaiting demand | docs/03 §6 (⏳) |
| LEAP loss-recovery play (deep-ITM long-dated put sale) | Situational rescue tactic, not a recurring workflow; the rulebook documents it for manual use | 04 §4 |
| FOMC calendar in event hygiene | Only earnings dates are tracked via the data provider; FOMC dates are 8 known dates/year the user can respect manually | this doc §1 (⚠ row) |
| Fibonacci 0.618 / measured-move price-and-time targets / rule of threes | Documented in the rulebook; not coded — the envelope numbers cover the same "where/when to exit" need with stronger book support | 04 §7 |
| Mental-stop vs. unpredictable-stop placement craft | Human execution guidance; the app enforces the *close-below* evaluation style by checking closes, not intraday prints | 04 §9 |
| Hedge structures: inverted collar, bull put spread protection | Documented for manual use; not automated | 04 §9 |

## 5. Extensions — in the app but *not* from the book

Fenced per design decision D1 (never blended with book rules).

| Extension | Where | Notes |
|---|---|---|
| 20/20/20 capability screen (owner's rule, put-side gated) | `screening/` + `screen` CLI | Feasibility analysis reshaped it: docs/06 §6 |
| CD re-entry gate in backtests | `backtest/strategies.py` (default when index supplied) | Validation: docs/07 §3 |
| CD-triggered exits | same, `cd_exits=True` | **Experimental, default-off** — failed validation as designed |
| Synthetic option pricing, simulated broker, benchmarks | `backtest/` | Known biases documented in every output |
| Provider factory / SQLite cache / stale-grace / template provider | `data/` | Operational resilience + shareability |
| Calibrated thresholds (quantifying the book's qualitative words) | `config.py::Calibrated` | Grid-search evidence: docs/07 §2 |

## Appendix A — CLI ↔ workflow ↔ book map

| Stage | Command | Book source |
|---|---|---|
| FIND | `screen` | extension (docs/06) |
| FIND | `scan` | Ch-19 scan + triage; Ch-18 timing annotations |
| FIND | `squeeze` | Ch-12 squeeze routine |
| ENTER | `plan` | Ch-6 half/half put selling |
| ENTER/EXIT | `record` | Ch-9/10 worksheet discipline + rule enforcement |
| MANAGE | `daily` | Ch-7 daily routine; Ch-14 weekly CD; two-account epilogue plan |
| MANAGE | `analyze` | Ch-8/13 chart-timing assessment on demand |
| EXIT | `cd` | Ch-14 CD charts |
| VERIFY | `backtest` | not in the book — the honesty layer |

## Appendix B — worked examples pinned as test vectors

The book's arithmetic examples (as extracted into docs/04) anchor the test
suite, so a regression in any formula breaks a named test:

- 2%-risk sizing: $25,000 account / $0.20 risk → 2,500 shares (`tests/test_options_and_ledger.py`)
- Five-day oscillator ≈ 82; strength index 80 (`tests/test_shortterm.py`)
- Envelope buy 7.70 / sell 8.49 / envelope high 8.73 (`tests/test_shortterm.py`)
- 2×-premium month rule: $0.60 near vs $1.75 later → take the later month (`tests/test_options_and_ledger.py`)
- 25% buy-back capture = 75% (`tests/test_record.py`)
- Half/half blended-cost arithmetic (`tests/test_cd_and_planner.py`)

## Appendix C — where the numbers live

Every book constant is a named field in `config.py::BookRules` (traceable to
docs/04 by section reference in the comment); every quantified-judgment
threshold is in `config.py::Calibrated` with its validation status. If a
number appears anywhere else in the code without a config reference, that is
a bug — report or fix it.
