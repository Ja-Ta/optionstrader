# optionstrader

A systematic options cash-generation engine: covered calls sold at chart
resistance, cash-secured puts sold at support, harvested early (buy back any
short option at 25% of the premium collected) and gated by technical signals
(moving-average tests, Chaikin Money Flow, weekly relative strength). Includes
a candidate screener, a reversal scanner, an entry planner, a fill ledger, a
backtesting harness, and a scheduled daily report.

**Educational software. Not financial advice.** Options involve substantial
risk, including assignment and total loss of premium-secured capital.
Backtests here price options *synthetically* (Black-Scholes on realized
volatility) unless you supply real historical chains — treat all backtest
output as an evaluation of the timing logic, not a forecast of returns.

## Quickstart

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -q          # 125 offline tests, no network needed
.venv/bin/optionstrader analyze AAPL --levels
```

## Commands

| Command | Purpose |
|---|---|
| `screen TICKER...` | Capability screen: can this stock's options pay ≥20%/yr at 20% OTM? |
| `scan TICKER...` | 10-condition heavy-volume reversal scan + triage, with entry-timing numbers on hits |
| `squeeze TICKER...` | Monthly short-squeeze screen: short-interest build + accumulation filter, ITM-put ladder |
| `plan TICKER --shares N` | Half/half put-sale entry plan from live chains and support levels |
| `analyze TICKER` | Decision state machine on one ticker (trend, money flow, levels); `--short-term` adds the oscillator/envelope block |
| `cd TICKER --index ^GSPC` | Weekly relative-strength chart — the long-term exit tripwire |
| `record ACTION TICKER ...` | Log fills; enforces no-naked-calls and keeps the ledger consistent |
| `status` | Premium-adjusted cost basis and mark-to-market per position |
| `daily --watchlist ...` | The whole after-close routine in one report (file/email delivery) |
| `backtest TICKER` | Compare buy-and-hold vs naive covered calls vs the full engine |

## Data providers (pluggable)

All market data flows through one interface (`src/optionstrader/data/provider.py`).
The default is **yfinance** (free, no key) wrapped in a SQLite **cache** with
retry and serve-stale-on-outage behavior.

To plug in your broker or data vendor (Schwab, Tradier, IBKR, Alpaca, Polygon…):

1. Copy `src/optionstrader/data/template_provider.py` and implement its four
   methods (the file documents the exact return-shape contract and where each
   piece of data lives on common broker APIs).
2. Register your class in `src/optionstrader/data/factory.py`.
3. Select it: `export OPTIONSTRADER_PROVIDER=yourname`.

Optional environment variables:

| Variable | Effect |
|---|---|
| `OPTIONSTRADER_PROVIDER` | Provider name (default `yfinance`) |
| `FINNHUB_API_KEY` | Use Finnhub's free earnings calendar (more reliable than Yahoo's) |
| `OPTIONSTRADER_CACHE_DB` | Cache location (default `.cache/optionstrader.db`) |
| `OPTIONSTRADER_NO_CACHE` | Disable the cache layer |

Short-interest data (for squeeze screening) is in
`src/optionstrader/data/short_interest.py`, likewise swappable.

## Scheduled daily report

`scripts/daily_cron.sh` runs the `daily` command, saves the report to
`reports/daily-YYYY-MM-DD.txt`, and emails it if `.env.daily` exists (copy
`.env.daily.example` and fill in SMTP credentials — use an app password).
Install with cron, e.g. 45 minutes after the US close:

```
45 16 * * 1-5 /path/to/optionstrader/scripts/daily_cron.sh
```

## Architecture

```
config.py        thresholds: BookRules (the strategy spec) vs Calibrated (backtest-tunable)
indicators/      MA tests, CMF, volume signals, support/resistance, CD relative strength,
                 short-term toolkit (oscillator / buy-sell envelopes)
signals/         the per-position decision state machine + order constraint validation
options/         strike/expiration selection, short-premium tracker, entry planner
portfolio/       fill ledger: premium-adjusted basis + mark-to-market, open-shorts state
scanner/         10-condition reversal scan + triage; short-squeeze screen
data/            provider interface, yfinance default, cache/retry, factory, template
backtest/        simulated broker, synthetic pricing, strategy comparison, metrics
daily.py         the after-close routine; reporting.py — file/email delivery
```

The strategy rules implemented here are distilled in `docs/` — start with
`docs/README.md` (reading order) and `docs/08-architecture-decisions.md` (what
was built and why). Constants in `config.py` cite their source in the rulebook
(`docs/04`); `Calibrated` values are defaults validated (or awaiting validation)
per the evidence record in `docs/07`.

## Sharing / licensing notes

- `options-trading-strategy.md` (if present in your copy) is a scan of a
  copyrighted book and **must not be redistributed**. It is not needed to run
  anything — the code and `docs/` stand alone.
- Never commit or share `.env.daily` (credentials), `portfolio.json` (your
  positions), `reports/`, or `.cache/`. The included `.gitignore` covers these.
- Licensed under the MIT License (see `LICENSE`).
