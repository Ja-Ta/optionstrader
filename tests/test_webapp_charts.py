"""Pure unit tests for the uPlot payload builders (no HTTP client)."""

import pytest

pytest.importorskip("fastapi")  # webapp module; skip alongside the rest without [ui]

from optionstrader.indicators import cd_series, detect_levels  # noqa: E402
from optionstrader.webapp.services import charts  # noqa: E402
from webapp_stubs import range_frame  # noqa: E402


def test_price_with_levels_shapes():
    df = range_frame(20.0)
    levels = detect_levels(df)
    p = charts.price_with_levels(df, levels, tail=100)
    assert len(p["x"]) == len(p["series"][0]["values"]) == 100
    assert all(isinstance(t, int) for t in p["x"])
    assert p["x"] == sorted(p["x"])
    for h in p["hlines"]:
        assert h["role"] in ("support", "resistance", "at price")


def test_cd_payload_dual_scale():
    stock = range_frame(20.0)["close"]
    index = range_frame(4000.0)["close"]
    p = charts.cd_payload(cd_series(stock, index))
    assert [s["label"] for s in p["series"]] == ["price", "cd"]
    assert p["series"][1]["scale"] == "cd"
    assert len(p["x"]) == len(p["series"][0]["values"]) == len(p["series"][1]["values"])


def test_equity_payload_multiple_series():
    from optionstrader.backtest import BuyAndHold, NaiveCoveredCall, run_backtest
    from optionstrader.backtest.pricing import SyntheticPricer

    df = range_frame(20.0)
    pricer = SyntheticPricer()
    results = [run_backtest(df, s(), pricer=pricer) for s in (BuyAndHold, NaiveCoveredCall)]
    p = charts.equity_payload(results)
    assert [s["label"] for s in p["series"]] == ["buy_and_hold", "naive_covered_call"]
    for s in p["series"]:
        assert len(s["values"]) == len(p["x"])


def test_equity_payload_empty():
    assert charts.equity_payload([]) == {"x": [], "series": [], "hlines": []}
