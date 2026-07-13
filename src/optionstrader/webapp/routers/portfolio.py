from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from ...portfolio import Portfolio
from ..deps import get_settings
from ..settings import UISettings
from ..templating import templates

router = APIRouter(prefix="/portfolio")


@router.get("")
def portfolio_page(request: Request, settings: UISettings = Depends(get_settings)):
    pf = Portfolio.load(settings.portfolio_path)
    return templates.TemplateResponse(
        request,
        "portfolio/status.html",
        {"positions": sorted(pf.positions.items()), "portfolio_path": settings.portfolio_path},
    )


@router.get("/mtm/{ticker}")
def mark_to_market(request: Request, ticker: str, price: float,
                   settings: UISettings = Depends(get_settings)):
    pf = Portfolio.load(settings.portfolio_path)
    t = ticker.upper()
    if t not in pf.positions:
        raise HTTPException(404, f"no position {t}")
    pos = pf.positions[t]
    return templates.TemplateResponse(
        request,
        "portfolio/_mtm.html",
        {
            "ticker": t,
            "price": price,
            "mtm": pos.mark_to_market(price),
            "stop_breached": pos.stop_loss_breached(price),
        },
    )
