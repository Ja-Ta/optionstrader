"""Record forms: the write path, its gates, and write atomicity."""

import json

import pytest

pytest.importorskip("fastapi")

from optionstrader.portfolio import Portfolio  # noqa: E402
from webapp_stubs import make_client, seed_portfolio  # noqa: E402


def test_buy_shares_persists_lot(tmp_path):
    client = make_client(tmp_path)
    r = client.post("/record/buy-shares", data={
        "ticker": "new", "shares": "100", "price": "42.50",
        "day": "2026-07-10", "account": "short_term",
    })
    assert r.status_code == 200
    assert "bought 100 NEW @ 42.50" in r.text
    pf = Portfolio.load(tmp_path / "pf.json")
    pos = pf.positions["NEW"]
    assert pos.shares == 100 and pos.lots[0].price == 42.50
    assert pos.account == "short_term"


def test_sell_while_short_calls_open_refused_and_file_untouched(tmp_path):
    seed_portfolio(tmp_path / "pf.json")
    before = (tmp_path / "pf.json").read_bytes()
    client = make_client(tmp_path)
    r = client.post("/record/sell-shares", data={
        "ticker": "HLD", "shares": "1000", "price": "21.00",
    })
    assert r.status_code == 422
    assert "REFUSED" in r.text and "buy them back" in r.text
    assert (tmp_path / "pf.json").read_bytes() == before


def test_naked_call_refused(tmp_path):
    client = make_client(tmp_path)  # empty portfolio: any call sale is naked
    r = client.post("/record/option-sale", data={
        "ticker": "HLD", "kind": "call", "strike": "22.5", "expiry": "2026-09-18",
        "contracts": "1", "premium": "1.00",
    })
    assert r.status_code == 422
    assert "NAKED CALL refused" in r.text
    # A refused write on a fresh portfolio must not create the file.
    assert not (tmp_path / "pf.json").exists()


def test_put_sale_beyond_2x_warns_but_records(tmp_path):
    seed_portfolio(tmp_path / "pf.json")  # 1000 shares held
    client = make_client(tmp_path)
    r = client.post("/record/option-sale", data={
        "ticker": "HLD", "kind": "put", "strike": "18", "expiry": "2026-09-18",
        "contracts": "25", "premium": "0.60",   # 2500 put-shares > 2x 1000
    })
    assert r.status_code == 200
    assert "WARNING" in r.text and "2x cap" in r.text
    assert "buy-back trigger" in r.text and "0.15" in r.text  # 25% of 0.60
    pf = Portfolio.load(tmp_path / "pf.json")
    assert pf.positions["HLD"].open_short_shares("put") == 2500


def test_buyback_shows_captured_fraction(tmp_path):
    stub_expiry = seed_portfolio(tmp_path / "pf.json").positions["HLD"].open_shorts[0].expiry
    client = make_client(tmp_path)
    r = client.post("/record/buyback", data={
        "ticker": "HLD", "kind": "call", "strike": "22.5", "expiry": stub_expiry,
        "price": "0.20",   # collected 1.00 → captured 80%, 25% rule met
    })
    assert r.status_code == 200
    assert "captured 80% of premium" in r.text
    assert "early/defensive" not in r.text
    pf = Portfolio.load(tmp_path / "pf.json")
    assert pf.positions["HLD"].open_shorts == []


def test_assigned_put_creates_lot_at_strike(tmp_path):
    seed_portfolio(tmp_path / "pf.json")
    client = make_client(tmp_path)
    client.post("/record/option-sale", data={
        "ticker": "HLD", "kind": "put", "strike": "18", "expiry": "2026-09-18",
        "contracts": "2", "premium": "0.60",
    })
    r = client.post("/record/assigned", data={
        "ticker": "HLD", "kind": "put", "strike": "18", "expiry": "2026-09-18",
    })
    assert r.status_code == 200
    assert "bought 200 HLD @ 18" in r.text and "effective 17.40" in r.text
    pf = Portfolio.load(tmp_path / "pf.json")
    pos = pf.positions["HLD"]
    assert any(l.price == 18.0 and l.shares == 200 for l in pos.lots)


def test_writes_are_atomic_no_orphans(tmp_path):
    client = make_client(tmp_path)
    client.post("/record/buy-shares", data={"ticker": "A", "shares": "10", "price": "5"})
    client.post("/record/buy-shares", data={"ticker": "B", "shares": "10", "price": "5"})
    assert json.loads((tmp_path / "pf.json").read_text())  # parses
    assert list(tmp_path.glob("*.tmp-*")) == []


def test_locked_portfolio_excludes_second_locker(tmp_path):
    import fcntl

    from optionstrader.webapp.services.portfolio_io import locked_portfolio

    path = tmp_path / "pf.json"
    with locked_portfolio(path):
        lf = open(path.with_name("pf.json.lock"), "w")
        with pytest.raises(BlockingIOError):
            fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lf.close()


def test_shorts_picker_lists_open_shorts(tmp_path):
    seed_portfolio(tmp_path / "pf.json")
    client = make_client(tmp_path)
    r = client.get("/record/shorts/HLD", params={"prefix": "bb"})
    assert "10x 22.50 call" in r.text
    r = client.get("/record/shorts/NONE")
    assert "no open shorts" in r.text
