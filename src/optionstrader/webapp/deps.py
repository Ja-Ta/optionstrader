"""FastAPI dependencies.

get_data_provider returns a FRESH provider per request: CachedProvider holds a
single sqlite connection that is not safe to share across threads (cache.py),
so each request/job gets its own instance. Separate connections to the same
cache DB file are fine — SQLite serializes the small writes via file locking.
Tests override this dependency with stub providers.
"""

from __future__ import annotations

from fastapi import Request

from ..data import get_provider
from .services.jobs import JobRegistry
from .settings import UISettings


def get_settings(request: Request) -> UISettings:
    return request.app.state.settings


def get_data_provider():
    return get_provider()


def get_jobs(request: Request) -> JobRegistry:
    return request.app.state.jobs


def get_si_provider():
    """Short-interest source for the squeeze screen. None lets screen_squeeze
    default to YFinanceShortInterest; tests override with an offline stub."""
    return None
