from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, Request

from ...portfolio import Portfolio
from ..deps import get_settings
from ..settings import UISettings
from ..templating import templates

router = APIRouter()


def _short_row(o) -> dict:
    try:
        days_left = (datetime.strptime(o.expiry, "%Y-%m-%d").date() - date.today()).days
    except ValueError:
        days_left = 0
    return {"o": o, "days_left": days_left}


@router.get("/")
def home(request: Request, settings: UISettings = Depends(get_settings)):
    pf = Portfolio.load(settings.portfolio_path)
    positions = [
        (t, pos, [_short_row(o) for o in pos.open_shorts])
        for t, pos in sorted(pf.positions.items())
    ]
    latest = None
    if settings.reports_dir.is_dir():
        saved = sorted(p.name for p in settings.reports_dir.glob("daily-*.txt"))
        latest = saved[-1] if saved else None
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "positions": positions,
            "portfolio_path": settings.portfolio_path,
            "reports_dir": settings.reports_dir,
            "latest_report": latest,
        },
    )
