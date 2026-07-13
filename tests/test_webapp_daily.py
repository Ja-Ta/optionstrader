"""Daily run (as a job) + saved-report archive."""

import re

import pytest

pytest.importorskip("fastapi")

from webapp_stubs import StubProvider, make_client, seed_portfolio  # noqa: E402


def run_daily_via_ui(client, watchlist="WCH"):
    r = client.post("/daily", data={"watchlist": watchlist, "index_symbol": "^GSPC",
                                    "scan_max_price": "10.0"})
    assert r.status_code == 200
    job_id = re.search(r'data-job-id="(\w+)"', r.text).group(1)
    return client.get(f"/jobs/{job_id}")


def test_daily_job_renders_report(tmp_path):
    stub = StubProvider()
    seed_portfolio(tmp_path / "pf.json")
    client = make_client(tmp_path, provider=stub)
    r = run_daily_via_ui(client)
    assert r.status_code == 286                      # htmx stop-polling
    assert "Daily report" in r.text
    assert "HLD" in r.text
    # The stub prices the short call at 0.20 <= 25% of 1.00 → buy-back action item.
    assert "buy back" in r.text


def test_daily_job_error_surfaces(tmp_path):
    class Broken(StubProvider):
        def daily_ohlcv(self, ticker, lookback_days=300):
            raise RuntimeError("provider down")

    seed_portfolio(tmp_path / "pf.json")
    client = make_client(tmp_path, provider=Broken())
    r = run_daily_via_ui(client)
    assert r.status_code == 286
    # Per-holding fetch failures degrade to inline errors, not a failed job.
    assert "ERROR" in r.text and "provider down" in r.text


def test_archive_lists_and_serves_reports(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "daily-2026-07-10.txt").write_text("=== DAILY REPORT 2026-07-10 ===")
    client = make_client(tmp_path)
    r = client.get("/daily/archive")
    assert "daily-2026-07-10.txt" in r.text
    r = client.get("/daily/archive/daily-2026-07-10.txt")
    assert r.status_code == 200
    assert "DAILY REPORT 2026-07-10" in r.text


def test_archive_rejects_traversal_and_odd_names(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "secrets.txt").write_text("nope")
    client = make_client(tmp_path)
    assert client.get("/daily/archive/..%2F..%2Fetc%2Fpasswd").status_code == 404
    assert client.get("/daily/archive/secrets.txt").status_code == 404


def test_jobs_page_and_box(tmp_path):
    client = make_client(tmp_path)
    assert client.get("/jobs").status_code == 200
    assert "No jobs yet" in client.get("/jobs/box").text
    run_daily_via_ui(client)
    assert "daily" in client.get("/jobs/box").text
