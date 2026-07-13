"""`optionstrader-ui` entry point — the only place that starts a server.

Local, single-user tool: binds 127.0.0.1 by default and has no auth.
Do not expose it beyond localhost.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="optionstrader-ui",
        description="Optional local web UI for optionstrader (needs the [ui] extra).",
    )
    parser.add_argument("--host", default="127.0.0.1", help="bind address (default 127.0.0.1; no auth — keep it local)")
    parser.add_argument("--port", type=int, default=8747)
    parser.add_argument("--portfolio", default="portfolio.json", help="portfolio ledger file (same as the CLI)")
    parser.add_argument("--watchlist-file", default=None, help="tickers file (JSON list or whitespace-separated)")
    parser.add_argument("--reports-dir", default="reports", help="saved daily reports directory")
    parser.add_argument("--index", default="^GSPC", help="benchmark index for CD/daily")
    args = parser.parse_args(argv)

    try:
        import uvicorn

        from .app import create_app
    except ImportError as e:
        print(f"missing dependency ({e.name}) — the web UI needs the [ui] extra:")
        print('  pip install -e ".[ui]"')
        return 1

    from .settings import UISettings

    settings = UISettings(
        portfolio_path=Path(args.portfolio),
        watchlist_path=Path(args.watchlist_file) if args.watchlist_file else None,
        reports_dir=Path(args.reports_dir),
        index_symbol=args.index,
        host=args.host,
        port=args.port,
    )
    app = create_app(settings)
    print(f"optionstrader UI on http://{args.host}:{args.port}  (portfolio: {args.portfolio})")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
