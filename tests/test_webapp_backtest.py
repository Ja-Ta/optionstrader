"""Backtest job route + equity chart payload."""

import json
import re

import pytest

pytest.importorskip("fastapi")

from webapp_stubs import make_client  # noqa: E402


def test_backtest_job_renders_metrics_and_chart(tmp_path):
    client = make_client(tmp_path)
    r = client.post("/backtest", data={
        "ticker": "HLD", "strategy": "buyhold", "days": "280",
        "cash": "100000", "iv_premium": "1.2", "friction": "0.05",
    })
    job_id = re.search(r'data-job-id="(\w+)"', r.text).group(1)
    r = client.get(f"/jobs/{job_id}")
    assert r.status_code == 286
    assert "SYNTHETIC" in r.text                    # the mandatory caveat banner
    assert "total_return" in r.text and "sharpe" in r.text
    payload = json.loads(
        re.search(r'<script type="application/json">(.*?)</script>', r.text, re.S).group(1)
    )
    assert payload["series"][0]["label"] == "buy_and_hold"
    assert len(payload["x"]) == len(payload["series"][0]["values"]) > 100


def test_backtest_all_strategies_with_trades(tmp_path):
    client = make_client(tmp_path)
    r = client.post("/backtest", data={
        "ticker": "HLD", "strategy": "all", "days": "280", "cash": "100000",
        "iv_premium": "1.2", "friction": "0.05", "trades": "true",
        "willing_to_add": "true",
    })
    job_id = re.search(r'data-job-id="(\w+)"', r.text).group(1)
    r = client.get(f"/jobs/{job_id}")
    assert r.status_code == 286
    for name in ("buy_and_hold", "naive_covered_call", "elias_engine"):
        assert name in r.text
    assert "trades (" in r.text                     # trade-log details present
