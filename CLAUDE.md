# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

An options trading application implementing the cash-generation strategy from Samir Elias's *Generate Thousands in Cash on Your Stocks Before Buying or Selling Them* (3rd ed., 2007). Core engine: covered calls sold at chart resistance + cash-secured puts at support, harvested at 75% of premium (the "25% buy-back rule"), gated by technical signals (MA(10)/EMA(20)/EMA(30) tests, 20-day Chaikin Money Flow).

## Commands

```bash
.venv/bin/python -m pytest -q                 # run all tests (offline, synthetic data)
.venv/bin/python -m pytest tests/test_engine.py -q          # one file
.venv/bin/python -m pytest tests/test_engine.py::test_shakeout_beats_breakdown -q  # one test
.venv/bin/optionstrader analyze TICKER --shares N --levels  # live analysis (needs network)
.venv/bin/optionstrader status --price TICKER=PX            # portfolio ledger view
.venv/bin/optionstrader backtest TICKER --days 750 --willing-to-add [--trades]  # strategy comparison
.venv/bin/optionstrader screen TICKER [TICKER...] [--verbose]  # 20/20/20 capability screen (live chains)
.venv/bin/optionstrader cd TICKER --index ^GSPC [--table]     # weekly CD relative-strength exit tool
.venv/bin/optionstrader plan TICKER --shares N --cash X       # half/half put-sale entry plan
.venv/bin/optionstrader scan TICKER... [--max-price N] [--verbose]  # Ch-19 10-condition reversal scan + triage
.venv/bin/optionstrader daily --watchlist TICKER... [--portfolio F]  # the whole after-close routine, one report
.venv/bin/optionstrader record ACTION TICKER ...              # log fills; keeps ledger + open_shorts in sync
```

## Scheduled daily run

User crontab runs `scripts/daily_cron.sh` at 16:45 local (ET) weekdays: it executes `daily` with `portfolio.json` + `watchlist.txt`, saves to `reports/daily-YYYY-MM-DD.txt` (+ `latest.txt`), logs to `reports/cron.log`, and emails if `.env.daily` exists (copy `.env.daily.example`; sets SMTP vars + `DAILY_EMAIL_TO`). Never commit `.env.daily`. Email delivery lives in `src/optionstrader/reporting.py`; an email failure still saves the file and exits 1 so cron logs show it.

Setup from scratch: `python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"`

## Sharing constraints

This repo is intended to be shareable: `options-trading-strategy.md` (copyrighted book scan), `.env.daily`, `portfolio.json`, `reports/`, `.cache/`, and `backtests/` must never be committed or distributed — `.gitignore` enforces this; keep it intact. `README.md` is the public-facing doc; no license chosen yet.

## Source documents (read before changing strategy logic)

- `docs/README.md` — index of the strategy working documents; start here.
- `docs/04-key-rules-reference.md` — every numeric rule/formula from the book, with OCR-ambiguous values flagged. **Any constant in `config.py` must trace to a rule here.**
- `docs/03-implementation-guide.md` §4 is the decision-matrix spec that `signals/engine.py` implements; §6 is the build map (Tier 1 done; Tiers 2–4 pending).
- `docs/06-screening-module.md` — the 20/20/20 candidate screen, an extension **not** from the book; keep it upstream of, and separate from, the book's rules.
- `options-trading-strategy.md` — raw OCR of the book (~9,800 lines); use the docs instead unless verifying a flagged number.

## Architecture

`src/optionstrader/`, layered so the engine is testable offline:

- **`config.py`** — all thresholds, split into `BookRules` (explicit in the book) and `Calibrated` (defaults for things the book states only qualitatively, e.g. "steep slope"; must be backtested before trusting). Never blur this distinction.
- **`indicators/`** — pure pandas computations: `moving_averages.py` (1030/102030 tests as `evaluate_1030`/`evaluate_102030` — the strategy's *primary* signal), `cmf.py` (Chaikin Money Flow ±0.1 bands, *secondary/confirming*), `volume.py` (momentum-fade and tell-tale-spike signals), `levels.py` (support/resistance via pivot clustering), `cd.py` (weekly CD relative-strength — the long-term account's exit tool; Monday-anchored stock/index ratio normalized to 1-10, with the book's two sell tests and three buy tests).
- **`signals/`** — `states.py` (Snapshot in → Assessment out types), `engine.py` (the priority-ordered decision state machine). Ordering is load-bearing: premium triggers and event hygiene fire in every state; the shake-out check must run *before* the breakdown check (sharp drop + weak CMF = hold, not sell). `validate_order` enforces standing constraints (no naked calls, put-willingness, 2× put cap).
- **`options/`** — `selector.py` (strike = first strike beyond the anchor level; expiration via the 2×-premium month rule), `tracker.py` (25% buy-back, ¾-point-ITM + ≤2-week assignment watch, event warnings), `planner.py` (half/half put-sale entry plans: tranche strikes below successive supports from live chains, effective/blended costs, cash-secured gate, WAIT-vs-READY proximity trigger).
- **`portfolio/ledger.py`** — premium-adjusted cost basis (the book's scoreboard) alongside honest mark-to-market; JSON persistence; the 2%-risk position sizer.
- **`data/`** — `DataProvider` ABC; ALWAYS obtain providers via `get_provider()` (factory.py — env-selectable via OPTIONSTRADER_PROVIDER), never construct YFinanceProvider directly in commands. `cache.py` wraps every provider (SQLite, per-kind TTLs, retry, serve-stale-on-outage; results always pass the encode/decode round-trip so cached and fresh outputs are identical — never rely on DataFrame index freq). `template_provider.py` is the documented skeleton third parties copy for their broker; register new providers in factory.py's REGISTRY. `finnhub_earnings.py` overrides earnings dates when FINNHUB_API_KEY is set; `short_interest.py` (yfinance-backed, swappable) feeds the future squeeze screen.
- **`screening/`** — the 20/20/20 capability screen (extension, docs/06): `capability.py` runs against live chains (gates on the PUT side only — the call-side joint ROI+delta requirement is mathematically infeasible under lognormal pricing, see docs/06 §6; call side is diagnostic); `proxy.py` approximates it historically with the synthetic pricer (flat vol — understates real put yields 2-4x because it has no skew; do not treat proxy FAILs as definitive).
- **`scanner/`** — the Chapter-19 reversal scan: the book's ten conditions (EMA(20) as the stop line; conditions 9+10 are the below-stop-yesterday/above-stop-today flip) plus eliminate/watch/enter triage. Mechanical triage proxies only (run-up, dual-timeframe volatility, negative CMF divergence → eliminate; MACD-histogram divergence with a required intervening ≥5% bounce between lows, breakaway gaps → enter); freeform patterns stay human-reviewed per the book's "if you can't see the pattern, don't trade it". Zero hits on an arbitrary day is normal — the setup is rare; user supplies the candidate list (no free full-market sweep).
- **`backtest/`** — Tier 4: `pricing.py` (SYNTHETIC option premiums — Black-Scholes on trailing realized vol × an IV-premium multiplier; no free historical chains exist, so results measure timing-rule value, not exact premiums — keep this caveat in any output), `broker.py` (simulated fills/assignment; expiry-only settlement), `strategies.py` (BuyAndHold and NaiveCoveredCall benchmarks vs EliasEngine, which drives the Tier-1 state machine plus roll-up and surge-point re-entry), `engine.py` (daily loop), `metrics.py` (CAGR/Sharpe/drawdown/premium stats + comparison table).
- **`daily.py`** — the after-close routine (docs/03 §3) as one run: per holding, state machine + tracker alerts priced from live chains (buy-back side = ask) + 15% stop check + CD state (long-term accounts only) + earnings countdown; then the Ch-19 scan over the watchlist (holdings excluded); emits one action list ordered by urgency (expired/stop/NOW alerts → SOON alerts/CD deterioration → state-machine actions/scan ENTER hits). Open short options live in `Position.open_shorts` (explicit state, separate from the `premium_events` history). Record fills ONLY via the `record` command / `Position.record_*` methods — they keep both in sync and enforce the book's gates at write time (naked-call refusal counts existing shorts; stock sales refuse while short calls are open; put sales beyond 2x held warn; assignments move stock lots at the strike).
- **`analysis.py`** — glue: OHLCV frame → `Snapshot` → `assess()`. `cli.py` — argparse entry points.

Tests (`tests/`) use synthetic OHLCV from `conftest.py` and never touch the network. Note: functions named `test_*` in library code get collected by pytest when imported into test modules — hence `evaluate_1030`, not `test_1030`.

## Conventions

- Every rule implemented in code cites its docs/04 section in a docstring or comment; keep that traceability when adding rules.
- Prices are per-share floats; option premiums are per-share (×100 per contract only at cash-flow boundaries in the ledger/tracker).
- The book's strategy is the spec: don't "improve" rule values in place — new ideas go in clearly-marked extension modules (like the screening module) or behind `Calibrated` parameters.
