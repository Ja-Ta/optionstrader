"""Discovery screens: analyze/cd/plan inline fragments; scan/squeeze/screen jobs."""

import json
import re

import pytest

pytest.importorskip("fastapi")

from optionstrader.data.short_interest import ShortInterest, ShortInterestProvider  # noqa: E402
from webapp_stubs import StubProvider, make_client  # noqa: E402


def chart_payload(text: str) -> dict:
    m = re.search(r'<script type="application/json">(.*?)</script>', text, re.S)
    assert m, "no chart payload in fragment"
    return json.loads(m.group(1))


def follow_job(client, response) -> str:
    job_id = re.search(r'data-job-id="(\w+)"', response.text).group(1)
    r = client.get(f"/jobs/{job_id}")
    assert r.status_code == 286
    return r.text


def test_analyze_pages_render(tmp_path):
    client = make_client(tmp_path)
    assert client.get("/analyze").status_code == 200
    r = client.get("/analyze/run", params={"ticker": "HLD", "shares": 1000,
                                           "short_term": "true"})
    assert r.status_code == 200
    assert "Snapshot" in r.text and "Assessment" in r.text
    # A known PositionState value string must appear as the state badge.
    assert re.search(r"(uptrend|downtrend|range|breakdown|shake|insufficient)", r.text)
    assert "short-term" in r.text.lower()
    payload = chart_payload(r.text)
    assert len(payload["x"]) == len(payload["series"][0]["values"])
    assert len(payload["hlines"]) >= 1  # range-bound frame has clustered levels


def test_analyze_bad_ticker_renders_error_box(tmp_path):
    client = make_client(tmp_path)
    r = client.get("/analyze/run", params={"ticker": "NOPE"})
    assert r.status_code == 200
    assert "box error" in r.text


def test_cd_fragment_state_and_chart(tmp_path):
    client = make_client(tmp_path)
    r = client.get("/cd/run", params={"ticker": "HLD", "index_symbol": "^GSPC"})
    assert r.status_code == 200
    assert re.search(r"(neutral|sell_defend|buy_strength)", r.text)
    payload = chart_payload(r.text)
    assert [s["label"] for s in payload["series"]] == ["price", "cd"]
    assert payload["series"][1].get("scale") == "cd"
    # CD is normalized 1-10.
    cds = payload["series"][1]["values"]
    assert all(0 <= v <= 11 for v in cds)


def test_plan_fragment_ready_or_wait(tmp_path):
    client = make_client(tmp_path)
    r = client.get("/plan/run", params={"ticker": "HLD", "shares": 200, "cash": 10000})
    assert r.status_code == 200
    assert ("READY" in r.text) or ("WAIT" in r.text)


def test_scan_job_renders_result(tmp_path):
    client = make_client(tmp_path)
    r = client.post("/scan", data={"tickers": "WCH", "min_price": "5", "max_price": "10",
                                   "verbose": "true"})
    text = follow_job(client, r)
    assert "passed the 10 conditions" in text


class StubSI(ShortInterestProvider):
    def get(self, ticker):
        return ShortInterest(ticker=ticker, shares_short=2_000_000,
                             shares_short_prior_month=1_500_000, days_to_cover=4.0,
                             pct_of_float=0.15, as_of=None)


def test_squeeze_job_renders_verdicts(tmp_path):
    from optionstrader.webapp.deps import get_si_provider

    client = make_client(tmp_path)
    client.app.dependency_overrides[get_si_provider] = lambda: StubSI()
    r = client.post("/squeeze", data={"tickers": "HLD", "verbose": "true"})
    text = follow_job(client, r)
    assert re.search(r"(candidate|watch|eliminate)", text)
    assert "ONE squeeze candidate per month" in text


def test_screen_job_renders_legs(tmp_path):
    client = make_client(tmp_path)
    r = client.post("/screen", data={"tickers": "HLD"})
    text = follow_job(client, r)
    assert re.search(r"(PASS|FAIL)", text)
    assert "diagnostic" in text
