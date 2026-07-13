"""DataFrame/Series → uPlot payloads.

Payloads are embedded in the rendered fragments as
<script type="application/json"> next to a div[data-chart]; static/app.js
draws them. One mechanism for every chart — no separate JSON endpoints,
since the data is already in hand when the fragment renders.
"""

from __future__ import annotations

import pandas as pd


def _ts(index) -> list[int]:
    return [int(pd.Timestamp(ts).timestamp()) for ts in index]


def _vals(series) -> list[float]:
    return [round(float(v), 4) for v in series]


def price_with_levels(df: pd.DataFrame, levels, tail: int = 180) -> dict:
    """Daily closes with dashed horizontal support/resistance lines."""
    frame = df.tail(tail)
    price = float(frame["close"].iloc[-1])
    return {
        "x": _ts(frame.index),
        "series": [{"label": "close", "values": _vals(frame["close"])}],
        "hlines": [{"y": round(lv.price, 4), "role": lv.role(price)} for lv in levels],
    }


def cd_payload(cd_df: pd.DataFrame) -> dict:
    """Weekly price + CD (1-10, second axis) from indicators.cd.cd_series()."""
    return {
        "x": _ts(cd_df.index),
        "series": [
            {"label": "price", "values": _vals(cd_df["price"])},
            {"label": "cd", "values": _vals(cd_df["cd"]), "scale": "cd"},
        ],
        "hlines": [],
    }


def equity_payload(results) -> dict:
    """One equity-curve series per BacktestResult (shared x from the first)."""
    if not results:
        return {"x": [], "series": [], "hlines": []}
    base = results[0].equity.index
    return {
        "x": _ts(base),
        "series": [
            {
                "label": r.strategy,
                "values": [
                    round(float(v), 2) if pd.notna(v) else None
                    for v in r.equity.reindex(base)
                ],
            }
            for r in results
        ],
        "hlines": [],
    }
