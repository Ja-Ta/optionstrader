from datetime import date

import pytest

from optionstrader.options import (
    ExpiryQuote,
    ShortOption,
    check_short_option,
    choose_expiration,
    select_call_strike,
    select_put_strike,
)
from optionstrader.options.tracker import AlertKind
from optionstrader.portfolio import Portfolio, Position, PremiumEvent, StockLot
from optionstrader.portfolio.ledger import position_size

GRID = [15.0, 17.5, 20.0, 22.5, 25.0, 30.0]


def test_call_strike_one_above_resistance():
    choice = select_call_strike(GRID, resistance=22.5, price=20.0)
    assert choice.strike == 25.0


def test_call_strike_warns_when_capping_below_target():
    choice = select_call_strike(GRID, resistance=19.0, price=19.5)
    assert choice.strike == 20.0
    assert "WARNING" in choice.rationale


def test_put_strike_one_below_support():
    choice = select_put_strike(GRID, support=18.0, price=20.0)
    assert choice.strike == 17.5


def test_expiration_2x_rule():
    near = ExpiryQuote(date(2026, 8, 21), premium=0.60, open_interest=500)
    later = ExpiryQuote(date(2026, 9, 18), premium=1.75, open_interest=800)
    choice, notes = choose_expiration([near, later])
    assert choice.expiry == later.expiry  # 1.75 > 2 x 0.60 -> take later month


def test_expiration_prefers_near_when_ratio_not_met():
    near = ExpiryQuote(date(2026, 8, 21), premium=0.60, open_interest=500)
    later = ExpiryQuote(date(2026, 9, 18), premium=1.00, open_interest=800)
    choice, _ = choose_expiration([near, later])
    assert choice.expiry == near.expiry


def test_illiquid_expiration_dropped():
    only = ExpiryQuote(date(2026, 8, 21), premium=0.60, open_interest=10)
    choice, notes = choose_expiration([only])
    assert choice is None


def test_tracker_buyback_trigger():
    so = ShortOption("TEST", "call", 25.0, date(2026, 9, 18), 10, 1.00, date(2026, 7, 1))
    alerts = check_short_option(so, spot=20.0, option_price=0.25, today=date(2026, 7, 15))
    assert any(a.kind == AlertKind.BUYBACK_TRIGGER for a in alerts)


def test_tracker_assignment_vs_no_panic():
    so = ShortOption("TEST", "call", 19.0, date(2026, 9, 18), 10, 1.00, date(2026, 7, 1))
    # 1.0 ITM but 60+ days out -> informational "don't panic", not assignment risk.
    alerts = check_short_option(so, spot=20.0, option_price=1.60, today=date(2026, 7, 15))
    kinds = [a.kind for a in alerts]
    assert AlertKind.ASSIGNMENT_RISK in kinds
    assert all(a.urgency == 0 for a in alerts if a.kind == AlertKind.ASSIGNMENT_RISK)
    # Same option 7 days from expiry -> act-now assignment risk.
    alerts = check_short_option(so, spot=20.0, option_price=1.20, today=date(2026, 9, 11))
    assert any(a.kind == AlertKind.ASSIGNMENT_RISK and a.urgency == 2 for a in alerts)


def test_ledger_adjusted_basis():
    pos = Position(ticker="TEST")
    pos.lots.append(StockLot("2026-01-05", 1000, 10.0))
    pos.premium_events.append(
        PremiumEvent("2026-02-01", "call", "sell", 12.5, "2026-04-17", 10, 1.00)
    )
    pos.premium_events.append(
        PremiumEvent("2026-03-15", "call", "buyback", 12.5, "2026-04-17", 10, 0.25)
    )
    # 10,000 cost - (1000 - 250) premium = 9250 / 1000 shares
    assert pos.adjusted_basis_per_share == pytest.approx(9.25)
    mtm = pos.mark_to_market(9.0)
    assert mtm["total_pnl"] == pytest.approx(9000 - 10000 + 750)


def test_stop_loss_flag():
    pos = Position(ticker="TEST", lots=[StockLot("2026-01-05", 100, 10.0)])
    assert not pos.stop_loss_breached(8.6)   # -14%
    assert pos.stop_loss_breached(8.5)       # -15%


def test_position_size_2pct_rule():
    # $25,000 account, $7.00 entry, $6.80 stop -> $500 / $0.20 = 2,500 shares.
    assert position_size(25_000, 7.00, 6.80) == 2500
    assert position_size(25_000, 7.00, 6.50) == 1000


def test_portfolio_roundtrip(tmp_path):
    path = tmp_path / "pf.json"
    pf = Portfolio(path=path)
    pos = pf.get("TEST")
    pos.lots.append(StockLot("2026-01-05", 100, 10.0))
    pos.premium_events.append(
        PremiumEvent("2026-02-01", "put", "sell", 9.0, "2026-04-17", 1, 0.50)
    )
    pf.save()
    loaded = Portfolio.load(path)
    assert loaded.get("TEST").shares == 100
    assert loaded.get("TEST").net_premium == pytest.approx(50.0)
