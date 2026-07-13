"""Discovery screens: analyze / cd / plan run inline (1-3 provider calls);
scan / squeeze / screen run as jobs (network-bound over ticker lists)."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Form, Request

from ...analysis import analyze
from ...data.provider import DataProvider
from ...indicators import assess_cd, assess_short_term, cd_series, detect_levels
from ...options import plan_half_half
from ...scanner import ScanParams, run_scan, screen_squeeze
from ...screening import screen_live
from ..deps import get_data_provider, get_jobs, get_settings, get_si_provider
from ..services import charts
from ..services.jobs import JobRegistry
from ..settings import UISettings
from ..templating import templates

router = APIRouter()


def _tickers(raw: str) -> list[str]:
    return [t.upper() for t in re.split(r"[\s,]+", raw) if t]


def _error_box(request: Request, message: str):
    return templates.TemplateResponse(
        request, "_error.html", {"message": message}, status_code=200
    )


# --- analyze (inline) ---

@router.get("/analyze")
def analyze_page(request: Request):
    return templates.TemplateResponse(request, "discovery/analyze.html", {})


@router.get("/analyze/run")
def analyze_run(
    request: Request,
    ticker: str,
    shares: int = 0,
    willing_to_add: bool = False,
    short_term: bool = False,
    provider: DataProvider = Depends(get_data_provider),
):
    try:
        df = provider.daily_ohlcv(ticker)
        snap, result = analyze(ticker, df, shares_held=shares, willing_to_add=willing_to_add)
        levels = detect_levels(df)
    except Exception as e:  # noqa: BLE001 — provider/bad-ticker errors render inline
        return _error_box(request, f"{ticker.upper()}: {e}")
    return templates.TemplateResponse(
        request,
        "discovery/_analyze_result.html",
        {
            "snap": snap,
            "result": result,
            "levels": levels,
            "short_term_lines": assess_short_term(df).lines() if short_term else None,
            "chart": charts.price_with_levels(df, levels),
        },
    )


# --- cd (inline) ---

@router.get("/cd")
def cd_page(request: Request, settings: UISettings = Depends(get_settings)):
    return templates.TemplateResponse(
        request, "discovery/cd.html", {"index_symbol": settings.index_symbol}
    )


@router.get("/cd/run")
def cd_run(
    request: Request,
    ticker: str,
    index_symbol: str = "^GSPC",
    days: int = 420,
    weeks: int = 16,
    provider: DataProvider = Depends(get_data_provider),
):
    try:
        stock = provider.daily_ohlcv(ticker, lookback_days=days)
        index = provider.daily_ohlcv(index_symbol, lookback_days=days)
        result = assess_cd(stock["close"], index["close"])
        frame = cd_series(stock["close"], index["close"])
    except Exception as e:  # noqa: BLE001
        return _error_box(request, f"{ticker.upper()} vs {index_symbol}: {e}")
    return templates.TemplateResponse(
        request,
        "discovery/_cd_result.html",
        {
            "ticker": ticker.upper(),
            "index_symbol": index_symbol,
            "result": result,
            "rows": list(frame.tail(weeks).iterrows()),
            "chart": charts.cd_payload(frame),
        },
    )


# --- plan (inline) ---

@router.get("/plan")
def plan_page(request: Request):
    return templates.TemplateResponse(request, "discovery/plan.html", {})


@router.get("/plan/run")
def plan_run(
    request: Request,
    ticker: str,
    shares: int,
    cash: float | None = None,
    provider: DataProvider = Depends(get_data_provider),
):
    try:
        plan = plan_half_half(ticker, provider, target_shares=shares, cash_available=cash)
    except Exception as e:  # noqa: BLE001
        return _error_box(request, f"{ticker.upper()}: {e}")
    return templates.TemplateResponse(request, "discovery/_plan_result.html", {"plan": plan})


# --- scan (job) ---

@router.get("/scan")
def scan_page(request: Request):
    return templates.TemplateResponse(request, "discovery/scan.html", {})


@router.post("/scan")
def scan_run(
    request: Request,
    tickers: str = Form(...),
    min_price: float = Form(5.0),
    max_price: float = Form(10.0),
    verbose: bool = Form(False),
    provider: DataProvider = Depends(get_data_provider),
    jobs: JobRegistry = Depends(get_jobs),
):
    names = _tickers(tickers)
    params = ScanParams(min_price=min_price, max_price=max_price)

    def work():
        return {"reports": run_scan(names, provider, params), "verbose": verbose}

    job = jobs.get(jobs.submit("scan", f"{len(names)} ticker(s)", work))
    return templates.TemplateResponse(request, "jobs/_poll.html", {"job": job})


# --- squeeze (job) ---

@router.get("/squeeze")
def squeeze_page(request: Request):
    return templates.TemplateResponse(request, "discovery/squeeze.html", {})


@router.post("/squeeze")
def squeeze_run(
    request: Request,
    tickers: str = Form(...),
    verbose: bool = Form(False),
    provider: DataProvider = Depends(get_data_provider),
    si_provider=Depends(get_si_provider),
    jobs: JobRegistry = Depends(get_jobs),
):
    names = _tickers(tickers)

    def work():
        return {"reports": screen_squeeze(names, provider, si_provider=si_provider),
                "verbose": verbose}

    job = jobs.get(jobs.submit("squeeze", f"{len(names)} ticker(s)", work))
    return templates.TemplateResponse(request, "jobs/_poll.html", {"job": job})


# --- 20/20/20 capability screen (job) ---

@router.get("/screen")
def screen_page(request: Request):
    return templates.TemplateResponse(request, "discovery/screen.html", {})


@router.post("/screen")
def screen_run(
    request: Request,
    tickers: str = Form(...),
    provider: DataProvider = Depends(get_data_provider),
    jobs: JobRegistry = Depends(get_jobs),
):
    names = _tickers(tickers)

    def work():
        reports, errors = [], []
        for t in names:
            try:
                reports.append(screen_live(t, provider))
            except Exception as e:  # noqa: BLE001 — mirror the CLI: skip and report
                errors.append(f"{t}: {e}")
        reports.sort(key=lambda r: (not r.passed, -r.score))
        return {"reports": reports, "errors": errors}

    job = jobs.get(jobs.submit("screen", f"{len(names)} ticker(s)", work))
    return templates.TemplateResponse(request, "jobs/_poll.html", {"job": job})
