from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from ..deps import get_jobs
from ..services.jobs import JobRegistry
from ..templating import templates

router = APIRouter(prefix="/jobs")

# Result partial per job kind — rendered (with status 286: htmx "stop polling")
# once the job completes. Registered here; the submitting routers own the templates.
RESULT_TEMPLATES = {
    "daily": "daily/_report.html",
    "scan": "discovery/_scan_result.html",
    "squeeze": "discovery/_squeeze_result.html",
    "screen": "discovery/_screen_result.html",
    "backtest": "backtest/_result.html",
}

STOP_POLLING = 286  # htmx: swap the response, then stop the every-Ns trigger


@router.get("")
def jobs_page(request: Request, jobs: JobRegistry = Depends(get_jobs)):
    return templates.TemplateResponse(request, "jobs/index.html", {"jobs": jobs.list()})


@router.get("/box")
def jobs_box(request: Request, jobs: JobRegistry = Depends(get_jobs)):
    return templates.TemplateResponse(request, "jobs/_box.html", {"jobs": jobs.list()[:8]})


@router.get("/{job_id}")
def job_status(request: Request, job_id: str, jobs: JobRegistry = Depends(get_jobs)):
    job = jobs.get(job_id)
    if job is None:
        return HTMLResponse('<div class="box error">job not found (server restarted?)</div>',
                            status_code=STOP_POLLING)
    if job.status == "running":
        return templates.TemplateResponse(request, "jobs/_status.html", {"job": job})
    if job.status == "error":
        return templates.TemplateResponse(
            request, "jobs/_status.html", {"job": job}, status_code=STOP_POLLING
        )
    template = RESULT_TEMPLATES.get(job.kind, "jobs/_status.html")
    return templates.TemplateResponse(
        request, template, {"job": job, "result": job.result}, status_code=STOP_POLLING
    )
