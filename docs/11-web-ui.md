# The Web UI — Optional Browser Front End

*Added 2026-07-12. Design decision: docs/08 D10. This document is the user
and operator guide; the one-line rule for contributors is in docs/09 — the
UI contains **no strategy logic**.*

---

## 1. What it is (and is not)

A local, single-user web interface covering everything the CLI does: the
portfolio dashboard, the daily after-close report, all six discovery
commands, the backtester, and the fill-recording forms. It is a **second
consumer of the same library** — every screen calls the same functions the
CLI commands call, and every write goes through the same gated
`Position.record_*` methods, so the browser can never disagree with the
command line about a rule or a number. Both front ends read and write the
same `portfolio.json`.

It is **not**: a trading terminal (no orders, same as the CLI — docs/08 D3),
a hosted service (no auth, localhost by default), or a place where strategy
rules live (docs/09 invariant).

Stack: FastAPI + Jinja2 server-rendered pages with htmx for interactivity;
charts drawn by uPlot. All assets are vendored into the package (htmx,
uPlot — see `webapp/static/vendor/LICENSES.txt`), so the UI works with no
CDN and no internet beyond market-data fetches themselves.

## 2. Install and run

```bash
.venv/bin/pip install -e ".[ui]"     # or ".[dev,ui]" for the test suite too
.venv/bin/optionstrader-ui           # → http://127.0.0.1:8747
```

Flags (all optional):

| Flag | Default | Meaning |
|---|---|---|
| `--host` | `127.0.0.1` | Bind address. Use `0.0.0.0` for LAN access — read §6 first |
| `--port` | `8747` | Port |
| `--portfolio` | `portfolio.json` | Ledger file (same one the CLI uses) |
| `--watchlist-file` | none | Prefills the Daily page's watchlist (JSON list or whitespace-separated) |
| `--reports-dir` | `reports` | Where the saved daily reports live (the archive page reads these) |
| `--index` | `^GSPC` | Benchmark index default for CD/daily |

Without the `[ui]` extra installed, the core package, CLI, cron, and test
suite are unaffected (the seven webapp test files skip); `optionstrader-ui`
prints the install hint and exits.

## 3. The screens

| Screen | CLI equivalent | Notes |
|---|---|---|
| Dashboard `/` | — | Positions summary, open-short expiry countdowns, latest saved report, running jobs |
| Portfolio `/portfolio` | `status` | Lots, open shorts with per-short 25% buy-back triggers, premium history, on-demand mark-to-market with the 15%-stop banner |
| Record `/record` | `record` | Six forms (buy/sell shares, option sale, buyback, expired, assigned). An open-shorts picker fills strike/expiry from the ledger. Refusals render exactly as the CLI prints them |
| Daily `/daily` | `daily` | Runs the after-close routine on demand; `/daily/archive` serves the cron-saved reports read-only |
| Analyze `/analyze` | `analyze` | Snapshot + assessment panels, price chart with detected support/resistance lines, optional Ch-18 block |
| Scan `/scan` | `scan` | Ten-condition checklist per hit, triage badges |
| Squeeze `/squeeze` | `squeeze` | Verdict cards; candidates show the ITM-put ladder and ≤$0.20 earnings-call suggestions |
| Screen `/screen` | `screen` | Per-leg pass/fail with the call-side-diagnostic caveat |
| CD `/cd` | `cd` | Dual-axis weekly price + CD(1–10) chart, sell/buy tests |
| Plan `/plan` | `plan` | READY/WAIT banner, tranche table, blended cost |
| Backtest `/backtest` | `backtest` | Equity-curve chart per strategy, metrics table, the mandatory SYNTHETIC-premiums caveat |
| Jobs `/jobs` | — | Status of background runs |

Long-running commands (backtest, daily, scan, squeeze, screen) execute as
**background jobs** with a polling status box. Results are held in memory
and are **lost when the server restarts** — by design; re-run if needed.
Analyze, CD, and plan run inline (a few seconds).

## 4. How writes stay safe

The record forms call the same gate-enforcing ledger methods as the CLI —
naked-call refusal, no stock sales while short calls are open, the 2×-put
warning, assignment mechanics. Around them the webapp adds what a
long-running server needs and a one-shot CLI doesn't
(`webapp/services/portfolio_io.py`):

- an exclusive **flock** on `portfolio.json.lock` serializes concurrent UI
  writes (double-submits, two tabs);
- the save goes to a temp file and is **atomically renamed** over the real
  one, so a crash mid-write can never truncate your ledger;
- gate refusals raise **before** anything is written — a refused action
  leaves the file byte-identical.

`ledger.py` itself is untouched. A CLI `record` racing a UI write remains
the same exposure as two concurrent CLI runs always had; the cron job only
reads. Rule for contributors: **UI routes never call `Portfolio.save()`
directly — always `locked_portfolio()`.**

## 5. Run it as a service (survives reboots)

A systemd *user* service keeps it running (this is deliberately not in the
repo — it's per-machine). `~/.config/systemd/user/optionstrader-ui.service`:

```ini
[Unit]
Description=optionstrader local web UI
After=network-online.target

[Service]
WorkingDirectory=/path/to/optionstrader
ExecStart=/path/to/optionstrader/.venv/bin/optionstrader-ui --host 0.0.0.0 --port 8747
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now optionstrader-ui
loginctl enable-linger $USER        # start at boot without a login session
journalctl --user -u optionstrader-ui -f    # logs
```

`WorkingDirectory` matters: relative defaults (`portfolio.json`, `reports/`,
`.cache/`) resolve against it, and it should be the repo root so the UI,
CLI, and cron share state.

## 6. Security posture

- **No authentication, by design** (docs/08 D10: single local user). On the
  default `127.0.0.1` bind, only the machine itself can reach it.
- `--host 0.0.0.0` exposes it to every device on your network — acceptable
  on a trusted home LAN, **never port-forward it to the internet**. Your
  positions and the ability to edit the ledger are behind that port.
- The safer remote-access alternative is an SSH tunnel against the default
  localhost bind: `ssh -L 8747:localhost:8747 user@host`, then browse
  `http://localhost:8747`.
- The daily-report archive route serves only files matching the cron's
  naming pattern (`daily-YYYY-MM-DD.txt` / `latest.txt`) from the reports
  directory — nothing else on disk is reachable.

## 7. Architecture notes for contributors

```
webapp/
├── __main__.py      optionstrader-ui entry point (only place a server starts)
├── settings.py      UISettings (paths/defaults the server was launched with)
├── app.py           create_app() factory
├── deps.py          per-request dependencies — incl. a FRESH provider per
│                    request/job (the cache's sqlite connection is
│                    single-thread-only; fresh instances sidestep it)
├── services/        webapp-only policy: portfolio_io (locked atomic writes),
│                    jobs (in-memory thread registry), charts (uPlot payloads)
├── routers/         one module per screen; ALL handlers are sync `def`, so
│                    FastAPI runs them on its threadpool and blocking
│                    pandas/network calls never stall the event loop
├── templates/       Jinja2; `_`-prefixed files are htmx fragments
└── static/          app.css, app.js (chart bootstrapping), vendored assets
```

Import discipline: `webapp/` imports core; **nothing in core imports
webapp** — enforced by a guard test (`tests/test_webapp_app.py`) that
asserts importing `optionstrader`/`optionstrader.cli` never pulls in
fastapi. Tests live in `tests/test_webapp_*.py`, use stub providers from
`tests/webapp_stubs.py` (no network), and skip cleanly when fastapi is not
installed.

## 8. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `optionstrader-ui` prints "missing dependency" | Install the extra: `pip install -e ".[ui]"` |
| Page loads but a run shows "job not found (server restarted?)" | Jobs are in-memory; the server restarted mid-run — re-run |
| Can't reach it from another machine | It's bound to 127.0.0.1; use `--host 0.0.0.0` (§6) or an SSH tunnel |
| A record form says REFUSED | That's the book's gates working (docs/10 §6) — nothing was written |
| Charts don't render | The browser needs JavaScript enabled; assets are local, so no network/CDN issue applies |
