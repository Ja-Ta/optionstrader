import pytest

from optionstrader.portfolio import Position


def held_position(shares=1000, cost=10.0) -> Position:
    pos = Position(ticker="TEST")
    pos.buy_shares(shares, cost, "2026-01-05")
    return pos


# --- stock ---

def test_fifo_sell_reduces_lots():
    pos = Position(ticker="TEST")
    pos.buy_shares(300, 10.0, "2026-01-05")
    pos.buy_shares(200, 12.0, "2026-02-05")
    pos.sell_shares(400, 15.0, "2026-03-05")
    assert pos.shares == 100
    assert pos.lots[0].price == 12.0  # first lot fully consumed


def test_sell_stock_blocked_by_open_calls():
    pos = held_position()
    pos.record_option_sale("call", 12.5, "2026-09-18", 10, 0.80, "2026-07-01")
    with pytest.raises(ValueError, match="buy them back"):
        pos.sell_shares(500, 11.0, "2026-07-02")


# --- option sale gates ---

def test_naked_call_refused():
    pos = held_position(shares=500)
    with pytest.raises(ValueError, match="NAKED CALL"):
        pos.record_option_sale("call", 12.5, "2026-09-18", 6, 0.80, "2026-07-01")


def test_second_call_tranche_counts_existing_shorts():
    pos = held_position(shares=1000)
    pos.record_option_sale("call", 12.5, "2026-09-18", 6, 0.80, "2026-07-01")
    with pytest.raises(ValueError, match="NAKED CALL"):
        pos.record_option_sale("call", 15.0, "2026-09-18", 5, 0.40, "2026-07-02")


def test_put_2x_warning():
    pos = held_position(shares=1000)
    warnings = pos.record_option_sale("put", 9.0, "2026-09-18", 25, 0.50, "2026-07-01")
    assert warnings and "2x cap" in warnings[0]


# --- lifecycle: sale -> buyback / expiry / assignment ---

def test_buyback_at_25pct_rule():
    pos = held_position()
    pos.record_option_sale("call", 12.5, "2026-09-18", 10, 1.00, "2026-07-01")
    r = pos.record_buyback("call", 12.5, "2026-09-18", 0.25, "2026-08-01")
    assert r["rule_25pct_met"] and r["captured_fraction"] == pytest.approx(0.75)
    assert not pos.open_shorts
    assert pos.net_premium == pytest.approx((1.00 - 0.25) * 10 * 100)


def test_partial_buyback_reduces_contracts():
    pos = held_position()
    pos.record_option_sale("call", 12.5, "2026-09-18", 10, 1.00, "2026-07-01")
    pos.record_buyback("call", 12.5, "2026-09-18", 0.20, "2026-08-01", contracts=4)
    assert pos.open_shorts[0].contracts == 6


def test_expired_keeps_full_premium():
    pos = held_position()
    pos.record_option_sale("put", 9.0, "2026-09-18", 5, 0.60, "2026-07-01")
    r = pos.record_expired("put", 9.0, "2026-09-18", "2026-09-18")
    assert r["premium_kept"] == pytest.approx(300.0)
    assert not pos.open_shorts
    assert pos.net_premium == pytest.approx(300.0)


def test_put_assignment_adds_lot_at_strike():
    pos = held_position(shares=1000, cost=10.0)
    pos.record_option_sale("put", 9.0, "2026-09-18", 5, 0.60, "2026-07-01")
    r = pos.record_assigned("put", 9.0, "2026-09-18", "2026-09-18")
    assert r["shares_acquired"] == 500 and r["effective_cost"] == pytest.approx(8.40)
    assert pos.shares == 1500
    # Basis: (1000*10 + 500*9 - 300 premium) / 1500
    assert pos.adjusted_basis_per_share == pytest.approx((10000 + 4500 - 300) / 1500)


def test_call_assignment_delivers_shares():
    pos = held_position(shares=1000, cost=10.0)
    pos.record_option_sale("call", 12.5, "2026-09-18", 10, 1.00, "2026-07-01")
    r = pos.record_assigned("call", 12.5, "2026-09-18", "2026-09-18")
    assert r["shares_delivered"] == 1000 and r["proceeds"] == pytest.approx(12500.0)
    assert pos.shares == 0 and not pos.open_shorts


def test_buyback_requires_matching_short():
    pos = held_position()
    with pytest.raises(ValueError, match="no open short"):
        pos.record_buyback("call", 12.5, "2026-09-18", 0.20, "2026-08-01")
