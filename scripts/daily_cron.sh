#!/usr/bin/env bash
# Scheduled daily report — invoked by cron 45 minutes after the market close.
# Edit watchlist.txt to change what gets scanned; edit .env.daily to enable email.
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

# Optional email + settings (never committed): defines the SMTP env vars and
# may set DAILY_EMAIL_TO to enable email delivery.
if [ -f .env.daily ]; then
    set -a
    # shellcheck disable=SC1091
    . ./.env.daily
    set +a
fi

ARGS=(daily --portfolio portfolio.json --save-dir reports --quiet)
[ -f watchlist.txt ] && ARGS+=(--watchlist-file watchlist.txt)
[ -n "${DAILY_EMAIL_TO:-}" ] && ARGS+=(--email "$DAILY_EMAIL_TO")

mkdir -p reports
echo "=== $(date '+%F %T') daily run ===" >> reports/cron.log
"$REPO/.venv/bin/optionstrader" "${ARGS[@]}" >> reports/cron.log 2>&1
echo "exit=$?" >> reports/cron.log
