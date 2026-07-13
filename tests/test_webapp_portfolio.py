"""Portfolio status page + mark-to-market fragment."""

import pytest

pytest.importorskip("fastapi")

from webapp_stubs import make_client, seed_portfolio  # noqa: E402


def test_status_shows_position_details(tmp_path):
    seed_portfolio(tmp_path / "pf.json")
    client = make_client(tmp_path)
    r = client.get("/portfolio")
    assert r.status_code == 200
    assert "HLD" in r.text
    assert "22.50" in r.text            # short call strike
    assert "0.25" in r.text             # 25% buy-back trigger (0.25 * 1.00 premium)
    assert "willing to add" in r.text


def test_mtm_fragment_shows_pnl(tmp_path):
    seed_portfolio(tmp_path / "pf.json")
    client = make_client(tmp_path)
    r = client.get("/portfolio/mtm/HLD", params={"price": 21.0})
    assert r.status_code == 200
    # 1000 sh @ 19 cost, price 21 → stock value 21,000, pnl 2,000
    assert "21,000.00" in r.text
    assert "2,000.00" in r.text
    assert "STOP-LOSS" not in r.text


def test_mtm_fragment_stop_breach_banner(tmp_path):
    seed_portfolio(tmp_path / "pf.json")
    client = make_client(tmp_path)
    r = client.get("/portfolio/mtm/HLD", params={"price": 15.0})  # -21% vs 19 cost
    assert "STOP-LOSS BREACHED" in r.text


def test_mtm_unknown_ticker_404(tmp_path):
    seed_portfolio(tmp_path / "pf.json")
    client = make_client(tmp_path)
    assert client.get("/portfolio/mtm/NOPE", params={"price": 10.0}).status_code == 404
