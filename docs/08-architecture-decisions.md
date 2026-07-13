# Application Architecture & Design Decisions

What was built, how the pieces relate, and — most importantly — *why* each
significant decision went the way it did. Docs 01–05 describe the strategy;
this document describes the software. Companion: docs/07 is the evidence
record behind every claim of "validated" below.

---

## 1. System map

```
                        ┌─────────────────────────────────────────────┐
  FIND                  │  screen   20/20/20 capability screen (ext.) │
                        │  scan     Ch-19 reversal scan + triage      │
                        │  squeeze  monthly SI-build + accumulation   │
                        └──────────────────┬──────────────────────────┘
                                           ▼
  ENTER                 plan     half/half put-sale tranches at support
                        record   fills → ledger + open_shorts (gated)
                                           ▼
  MANAGE (daily cron)   daily    per-holding state machine + tracker
                        │        alerts + 15% stop + CD (long-term) /
                        │        Ch-18 envelopes (short-term) + scan
                        ▼
  EXIT                  cd       relative-strength deterioration
                        record   buybacks / expiry / assignment / sale
                                           ▼
  VERIFY                backtest 3-strategy comparison, sweeps, findings

  Underneath everything: data/ (provider factory → cache/retry → yfinance
  or your broker), config.py (BookRules vs Calibrated), portfolio/ ledger.
```

Package layout and per-module detail: CLAUDE.md "Architecture" section and
the README. This document explains the *decisions*.

## 2. Foundational decisions

**D1 — The book is the spec; extensions are fenced.** Every trading rule in
the code traces to docs/04 (the extracted rulebook), cited in docstrings.
Ideas that are NOT from the book — the 20/20/20 screen, the CD re-entry
gate — live in clearly-marked extension modules or default-off flags, never
blended into book rules. *Why:* the owner's explicit principle ("don't mix
strategies"), and it keeps the system falsifiable — when a backtest fails,
we know whether the book or an extension failed.

**D2 — `BookRules` vs `Calibrated` split in config.py.** Numbers the book
states explicitly (25% buy-back, ±0.1 CMF bands, 15% stop) are structurally
separated from thresholds the book states only qualitatively ("steep slope",
"sharp drop") that we had to quantify. *Why:* the second kind must be earned
by backtest, not asserted; the split makes the epistemic status of every
constant visible. The grid search (docs/07 §2) tunes ONLY Calibrated values.

**D3 — Advisory-only; no order execution.** The system recommends and
records; it never trades. `record` logs fills the user made at their broker,
and enforcement happens at recording time (naked-call refusal, stock-sale
block while calls are open, 2× put warning). *Why:* execution is a large
risk step that should follow — not precede — validation on real option
prices (docs/07 §4), and an advisory system is safe to share publicly.

**D4 — All engine logic is offline-testable.** Indicators, the state
machine, selectors, the ledger, the backtester, and every screen verdict
run on plain DataFrames; network access exists only behind the provider
interface. The test suite (125 tests) needs no keys and no market data,
which is also why CI is trivial. *Why:* determinism and testability were
prerequisites for trusting any of the rule enforcement.

**D5 — One data interface, factory-selected, cache-wrapped.**
`DataProvider` is the only door to market data; `get_provider()` picks the
implementation from config/env; `CachedProvider` wraps whatever is chosen
with SQLite caching, retry, and serve-stale-on-outage. A documented
`template_provider.py` is the third-party integration point. *Why:* yfinance
is a scraper that periodically breaks — a cron-driven system needs to
degrade, not go dark — and shareability required that "plug in your broker"
be a copy-one-file task. The cache round-trips even fresh fetches through
its serializer so cached and fresh results are always identical.

## 3. Engine decisions

**D6 — The decision state machine is priority-ordered, and the order is
load-bearing.** Premium triggers (25% buy-back, assignment watch) and event
hygiene evaluate in *every* state; the shake-out check runs *before* the
breakdown check. *Why:* the book's most valuable behavioral rule is not
panic-selling a sharp drop whose money flow shows no real selling — an
engine that checked breakdown first would do exactly the panic-selling the
book exists to prevent.

**D7 — Strikes come from chart structure, never from premium.** The
selector takes the support/resistance map (pivot clustering) and returns
the first listed strike beyond the anchor level; premium size never picks
the strike. *Why:* book principle; it also survived validation better than
any fixed-distance rule (see the 20/20/20 feasibility finding, docs/06 §6).

**D8 — Two accounts, symmetric tooling.** `Position.account` routes each
holding to its toolkit in the daily report: long-term positions get CD
relative strength (the book's designated exit tool); short-term positions
get the Ch-18 oscillator/envelope block with the five-day management rules.
*Why:* mirrors the book's 1/3–2/3 architecture without duplicating the
report pipeline — one loop, one action list, per-account signal sets.

**D9 — The ledger keeps two truths side by side.** Premium-adjusted cost
basis (the book's scoreboard) is always shown next to honest mark-to-market
P&L. *Why:* the book's own JDSU case shows the gap — 107% "cash return"
alongside a stock down 56%; hiding either number misleads.

**D10 — The web UI is a second consumer of the library, never a layer the
core knows about.** `webapp/` (FastAPI + Jinja2 + htmx, vendored assets, no
CDN) imports core modules; nothing in the core imports it, and the `[ui]`
extra is optional — `import optionstrader` and the CLI work without it.
Every screen calls the same functions the CLI commands call; the record
forms go through the same gated `Position.record_*` methods, so refusals
and warnings are identical in both interfaces. Concurrency is handled
entirely in the webapp layer: writes go through
`webapp/services/portfolio_io.locked_portfolio()` (flock + save-to-temp +
atomic `os.replace`; `ledger.py` untouched — its mutable `path` field makes
the temp-file trick possible), and each request/job constructs a fresh
provider because the cache's sqlite connection is single-thread-only.
Long-running commands (backtest, daily, scan, squeeze, screen) run in an
in-memory thread registry — results are lost on restart, by design.
Localhost-only (binds 127.0.0.1), single user, no auth. Non-features: no
websockets, no SPA framework, no database, no multi-user, no order entry.
*Why:* the UI must never be able to disagree with the CLI about rules or
state — one library, one ledger file, two front ends. A possible future
core improvement: atomic save inside `Portfolio.save()` itself, which would
also cover concurrent CLI runs.

## 4. Boundaries drawn on purpose (not built, and why)

- **Freeform chart-pattern detection** (falling wedges, H&S, cup-and-handle):
  surfaced as "needs chart review" instead. The book's own rule — "if you
  can't see the pattern, don't trade it" — plus high false-positive rates
  make mechanical detection worse than honest deferral to human eyes.
- **Day-of-week cycle rules** (Ch-18): assessed as a decayed 2007-era edge;
  encoding them would add false authority. Omitted entirely.
- **Expiration OI-fade play**: assessed as mostly arbitraged away
  (docs/02); left unbuilt rather than built and disclaimed.
- **Full-market scanning**: free APIs cannot sweep the market; the scanner
  and squeeze screen take user-supplied candidate lists and say so, rather
  than pretending coverage they don't have.
- **A standalone short-term command**: the Ch-18 numbers annotate outputs
  where they're used (scan hits, daily report, `analyze --short-term`)
  instead of growing the CLI. Numbers decide when/where, never whether.
- **Automatic recording of expirations/assignments in `daily`**: the report
  *tells* the user to record the outcome instead of mutating the ledger.
  The ledger is the source of truth; only explicit `record` actions write it.

## 5. Validation posture (summary; evidence in docs/07)

- Backtests price options **synthetically** (Black-Scholes on realized vol ×
  1.2) because no free historical chains exist. Every output says so. The
  known biases: flatters frequent sellers (naive-cc benchmark), understates
  real put yields (no skew — live AMD 20%-OTM put paid 4× the synthetic).
- What survived validation: the fade-volume threshold at 0.30 (adopted);
  the CD re-entry gate (default-on when an index is supplied — repaired the
  whipsaw names, roughly neutral in aggregate).
- What failed validation: CD-triggered exits as first designed (default-off,
  flagged experimental, redesign path documented); threshold tuning as a
  route to beating naive writing (the leaks are structural, not parametric).
- The record covers ONE bull-market window on an arbitrary universe. The
  book prescribes ≤8 selected stocks; the honest test on real premiums and
  a second regime is still open (docs/07 §4).

## 6. Operational architecture

- **Scheduled routine:** cron → `scripts/daily_cron.sh` (16:45 ET weekdays)
  → `daily --save-dir reports [--email]`. Delivery channels are independent:
  an email failure still writes the file and flags exit 1 in `reports/cron.log`.
  Credentials live only in `.env.daily` (never committed; mode 600).
- **Sharing hygiene:** `.gitignore` hard-excludes the copyrighted book scan,
  credentials, personal portfolio, reports, cache, and sweep outputs. The
  repo is MIT-licensed and public; CI runs the offline suite on 3.10–3.12.
  (Lesson learned the near-miss way: git ignores do not support trailing
  comments on pattern lines.)
- **Memory across sessions:** CLAUDE.md is the contributor/agent onboarding
  doc; docs/ carries strategy analysis (01–05), extension specs (06),
  evidence (07), and this decision record (08).

## 7. Roadmap (decision-blocked, not design-blocked)

1. Broker provider (awaiting broker choice) → unlocks vendor greeks, clean
   after-hours chains, and later, order placement.
2. Real-data validation month (ThetaData or similar) → settles docs/07 §4.
3. Portfolio-level guardrails in `daily` (≤8-stock cap, total short-put
   notional vs cash, 1/3–2/3 split check).
4. Remaining Tier-3 plays if wanted: earnings-straddle scanner (trivial),
   MAC channel strangles, LEAP loss-recovery planner.
