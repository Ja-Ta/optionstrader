"""Record fills — the write path.

Every action goes through Position.record_* / buy_shares / sell_shares inside
locked_portfolio(), so the book's gates (naked-call refusal, no stock sales
while short calls are open, 2x-put warning, assignment mechanics) are enforced
by the same code the CLI uses. A ValueError fires BEFORE any write: the file
is untouched and the refusal renders as a 422 error box.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, Request

from ...portfolio import Portfolio
from ..deps import get_settings
from ..services.portfolio_io import locked_portfolio
from ..settings import UISettings
from ..templating import templates

router = APIRouter(prefix="/record")

REFUSED = 422  # base.html htmx-config lets 422 swap, so refusals render inline


@router.get("")
def record_page(request: Request, settings: UISettings = Depends(get_settings)):
    pf = Portfolio.load(settings.portfolio_path)
    return templates.TemplateResponse(
        request,
        "record/index.html",
        {"tickers": sorted(pf.positions), "today": date.today().isoformat()},
    )


@router.get("/shorts/{ticker}")
def shorts_picker(request: Request, ticker: str, prefix: str = "bb",
                  settings: UISettings = Depends(get_settings)):
    pf = Portfolio.load(settings.portfolio_path)
    pos = pf.positions.get(ticker.upper())
    return templates.TemplateResponse(
        request,
        "record/_shorts_picker.html",
        {"ticker": ticker.upper(), "shorts": pos.open_shorts if pos else [], "prefix": prefix},
    )


def _result(request: Request, *, lines=None, warnings=None, error=None, pos=None,
            status_code: int = 200):
    return templates.TemplateResponse(
        request,
        "record/_form_result.html",
        {"lines": lines or [], "warnings": warnings or [], "error": error, "pos": pos},
        status_code=status_code,
        headers={"HX-Trigger": "portfolio-changed"} if error is None else None,
    )


def _apply(request: Request, settings: UISettings, ticker: str, fn):
    """Run `fn(pos) -> (lines, warnings)` inside the locked ledger; render the outcome."""
    try:
        with locked_portfolio(settings.portfolio_path) as pf:
            pos = pf.get(ticker)
            lines, warnings = fn(pos)
    except ValueError as e:
        return _result(request, error=str(e), status_code=REFUSED)
    return _result(request, lines=lines, warnings=warnings, pos=pos)


@router.post("/buy-shares")
def buy_shares(request: Request, ticker: str = Form(...), shares: int = Form(...),
               price: float = Form(...), day: str = Form(""), note: str = Form(""),
               account: str = Form(""), settings: UISettings = Depends(get_settings)):
    day = day or date.today().isoformat()

    def fn(pos):
        pos.buy_shares(shares, price, day, note)
        if account in ("long_term", "short_term"):
            pos.account = account
        return [f"bought {shares} {pos.ticker} @ {price:.2f} ({pos.account})"], []

    return _apply(request, settings, ticker, fn)


@router.post("/sell-shares")
def sell_shares(request: Request, ticker: str = Form(...), shares: int = Form(...),
                price: float = Form(...), day: str = Form(""), note: str = Form(""),
                settings: UISettings = Depends(get_settings)):
    day = day or date.today().isoformat()

    def fn(pos):
        proceeds = pos.sell_shares(shares, price, day, note)
        return [f"sold {shares} {pos.ticker} @ {price:.2f} — proceeds ${proceeds:,.2f}"], []

    return _apply(request, settings, ticker, fn)


@router.post("/option-sale")
def option_sale(request: Request, ticker: str = Form(...), kind: str = Form(...),
                strike: float = Form(...), expiry: str = Form(...),
                contracts: int = Form(...), premium: float = Form(...),
                day: str = Form(""), note: str = Form(""),
                settings: UISettings = Depends(get_settings)):
    day = day or date.today().isoformat()

    def fn(pos):
        warnings = pos.record_option_sale(kind, strike, expiry, contracts, premium, day, note)
        credit = premium * contracts * 100
        return [
            f"sold {contracts}x {pos.ticker} {expiry} {strike:g} {kind} @ {premium:.2f} "
            f"— ${credit:,.0f} collected",
            f"25% buy-back trigger: repurchase at ≤ {0.25 * premium:.2f}",
        ], warnings

    return _apply(request, settings, ticker, fn)


@router.post("/buyback")
def buyback(request: Request, ticker: str = Form(...), kind: str = Form(...),
            strike: float = Form(...), expiry: str = Form(...), price: float = Form(...),
            contracts: int | None = Form(None), day: str = Form(""), note: str = Form(""),
            settings: UISettings = Depends(get_settings)):
    day = day or date.today().isoformat()

    def fn(pos):
        r = pos.record_buyback(kind, strike, expiry, price, day, contracts, note)
        lines = [
            f"bought back {r['contracts']}x {pos.ticker} {expiry} {strike:g} {kind} "
            f"@ {price:.2f} — captured {r['captured_fraction']:.0%} of premium "
            f"(${r['profit_per_share'] * r['contracts'] * 100:,.0f})"
        ]
        warnings = [] if r["rule_25pct_met"] else [
            "above the 25%-of-premium level — early/defensive close"
        ]
        return lines, warnings

    return _apply(request, settings, ticker, fn)


@router.post("/expired")
def expired(request: Request, ticker: str = Form(...), kind: str = Form(...),
            strike: float = Form(...), expiry: str = Form(...),
            contracts: int | None = Form(None), day: str = Form(""),
            settings: UISettings = Depends(get_settings)):
    day = day or date.today().isoformat()

    def fn(pos):
        r = pos.record_expired(kind, strike, expiry, day, contracts)
        return [
            f"{r['contracts']}x {pos.ticker} {expiry} {strike:g} {kind} expired worthless "
            f"— ${r['premium_kept']:,.0f} premium kept"
        ], []

    return _apply(request, settings, ticker, fn)


@router.post("/assigned")
def assigned(request: Request, ticker: str = Form(...), kind: str = Form(...),
             strike: float = Form(...), expiry: str = Form(...),
             contracts: int | None = Form(None), day: str = Form(""),
             settings: UISettings = Depends(get_settings)):
    day = day or date.today().isoformat()

    def fn(pos):
        r = pos.record_assigned(kind, strike, expiry, day, contracts)
        if "shares_acquired" in r:
            lines = [
                f"assigned: bought {r['shares_acquired']} {pos.ticker} @ {r['cost_per_share']:g} "
                f"(effective {r['effective_cost']:.2f} after premium) — start selling covered calls"
            ]
        else:
            lines = [
                f"assigned: {r['shares_delivered']} {pos.ticker} called away @ {strike:g} "
                f"— proceeds ${r['proceeds']:,.2f}"
            ]
        return lines, []

    return _apply(request, settings, ticker, fn)
