from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Form, HTTPException, Request

from ...daily import run_daily
from ...data.provider import DataProvider
from ...portfolio import Portfolio
from ...scanner import ScanParams
from ..deps import get_data_provider, get_jobs, get_settings
from ..services.jobs import JobRegistry
from ..settings import UISettings, parse_watchlist
from ..templating import templates

router = APIRouter(prefix="/daily")

# Only cron-style report names may be served from the reports dir.
_REPORT_NAME = re.compile(r"^(daily-\d{4}-\d{2}-\d{2}\.txt|latest\.txt)$")


@router.get("")
def daily_page(request: Request, settings: UISettings = Depends(get_settings)):
    watchlist = ""
    if settings.watchlist_path and settings.watchlist_path.exists():
        watchlist = " ".join(parse_watchlist(settings.watchlist_path))
    return templates.TemplateResponse(
        request,
        "daily/index.html",
        {"watchlist": watchlist, "index_symbol": settings.index_symbol},
    )


@router.post("")
def daily_run(
    request: Request,
    watchlist: str = Form(""),
    index_symbol: str = Form("^GSPC"),
    scan_max_price: float = Form(10.0),
    settings: UISettings = Depends(get_settings),
    provider: DataProvider = Depends(get_data_provider),
    jobs: JobRegistry = Depends(get_jobs),
):
    tickers = [t.upper() for t in re.split(r"[\s,]+", watchlist) if t]
    portfolio_path = settings.portfolio_path

    def work():
        pf = Portfolio.load(portfolio_path)
        return run_daily(
            pf, provider, watchlist=tickers, index_symbol=index_symbol,
            scan_params=ScanParams(max_price=scan_max_price),
        )

    job_id = jobs.submit("daily", f"{len(tickers)} watchlist ticker(s)", work)
    job = jobs.get(job_id)
    return templates.TemplateResponse(request, "jobs/_poll.html", {"job": job})


@router.get("/archive")
def archive(request: Request, settings: UISettings = Depends(get_settings)):
    names: list[str] = []
    if settings.reports_dir.is_dir():
        names = sorted(
            (p.name for p in settings.reports_dir.glob("*.txt") if _REPORT_NAME.match(p.name)),
            reverse=True,
        )
    return templates.TemplateResponse(request, "daily/archive.html", {"names": names})


@router.get("/archive/{name}")
def archived_report(request: Request, name: str, settings: UISettings = Depends(get_settings)):
    if not _REPORT_NAME.match(name):
        raise HTTPException(404)
    path = settings.reports_dir / name
    if not path.is_file():
        raise HTTPException(404)
    return templates.TemplateResponse(
        request, "daily/archive.html", {"names": [], "selected": name, "text": path.read_text()}
    )
