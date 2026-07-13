"""App factory. Routers are all plain-def (sync) handlers so FastAPI runs them
on its threadpool — blocking pandas/network calls never stall the event loop."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .services.jobs import JobRegistry
from .settings import UISettings


def create_app(settings: UISettings | None = None, jobs: JobRegistry | None = None) -> FastAPI:
    app = FastAPI(title="optionstrader", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings or UISettings()
    app.state.jobs = jobs or JobRegistry()

    app.mount(
        "/static",
        StaticFiles(directory=str(Path(__file__).parent / "static")),
        name="static",
    )

    from .routers import backtest, daily, discovery, home, jobs as jobs_router, portfolio, record

    app.include_router(home.router)
    app.include_router(portfolio.router)
    app.include_router(record.router)
    app.include_router(daily.router)
    app.include_router(discovery.router)
    app.include_router(backtest.router)
    app.include_router(jobs_router.router)
    return app
