from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request

from ...backtest import BuyAndHold, EliasEngine, NaiveCoveredCall, run_backtest
from ...backtest.pricing import SyntheticPricer
from ...data.provider import DataProvider
from ..deps import get_data_provider, get_jobs
from ..services import charts
from ..services.jobs import JobRegistry
from ..templating import templates

router = APIRouter(prefix="/backtest")

STRATEGIES = {
    "buyhold": lambda willing: BuyAndHold(),
    "naive-cc": lambda willing: NaiveCoveredCall(),
    "elias": lambda willing: EliasEngine(willing_to_add=willing),
}


@router.get("")
def backtest_page(request: Request):
    return templates.TemplateResponse(request, "backtest/index.html", {})


@router.post("")
def backtest_run(
    request: Request,
    ticker: str = Form(...),
    strategy: str = Form("all"),
    days: int = Form(750),
    cash: float = Form(100_000.0),
    iv_premium: float = Form(1.20),
    friction: float = Form(0.05),
    willing_to_add: bool = Form(False),
    trades: bool = Form(False),
    provider: DataProvider = Depends(get_data_provider),
    jobs: JobRegistry = Depends(get_jobs),
):
    picked = list(STRATEGIES) if strategy == "all" else [strategy]

    def work():
        df = provider.daily_ohlcv(ticker, lookback_days=days)
        pricer = SyntheticPricer(iv_premium=iv_premium, friction=friction)
        results = [
            run_backtest(df, STRATEGIES[name](willing_to_add), initial_cash=cash, pricer=pricer)
            for name in picked
        ]
        return {
            "ticker": ticker.upper(),
            "start": df.index[0].date(),
            "end": df.index[-1].date(),
            "bars": len(df),
            "cash": cash,
            "iv_premium": iv_premium,
            "friction": friction,
            "results": results,
            "show_trades": trades,
            "chart": charts.equity_payload(results),
        }

    label = f"{ticker.upper()} {days}d {strategy}"
    job = jobs.get(jobs.submit("backtest", label, work))
    return templates.TemplateResponse(request, "jobs/_poll.html", {"job": job})
