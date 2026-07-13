"""UI runtime settings — paths and defaults the server is launched with.

Stdlib-only so it stays importable (and unit-testable) without the [ui] extra.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class UISettings:
    portfolio_path: Path = Path("portfolio.json")
    watchlist_path: Path | None = None
    reports_dir: Path = Path("reports")
    index_symbol: str = "^GSPC"
    host: str = "127.0.0.1"
    port: int = 8747
    extra: dict = field(default_factory=dict)


def parse_watchlist(path: Path) -> list[str]:
    """Same format the CLI accepts: JSON list or whitespace-separated tickers."""
    raw = path.read_text().strip()
    if not raw:
        return []
    return json.loads(raw) if raw.startswith("[") else raw.split()
