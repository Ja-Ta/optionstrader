"""Shared Jinja2 environment for the webapp routers."""

from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _money(v: float | None) -> str:
    return "—" if v is None else f"${v:,.2f}"


def _px(v: float | None) -> str:
    return "—" if v is None else f"{v:,.2f}"


def _pct(v: float | None) -> str:
    return "—" if v is None else f"{v:.1%}"


templates.env.filters["money"] = _money
templates.env.filters["px"] = _px
templates.env.filters["pct"] = _pct
