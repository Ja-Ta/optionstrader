"""Performance metrics and strategy comparison."""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_metrics(result) -> dict:
    eq = result.equity
    if len(eq) < 2 or eq.iloc[0] <= 0:
        return {}
    rets = eq.pct_change().dropna()
    years = max((eq.index[-1] - eq.index[0]).days / 365.25, 1e-9)
    total_return = eq.iloc[-1] / eq.iloc[0] - 1.0
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / years) - 1.0
    ann_vol = float(rets.std(ddof=1) * np.sqrt(252)) if len(rets) > 2 else 0.0
    sharpe = float((rets.mean() * 252 - 0.03) / (ann_vol + 1e-12)) if ann_vol else 0.0
    running_max = eq.cummax()
    max_dd = float(((eq - running_max) / running_max).min())

    b = result.broker
    win_rate = b.option_trades_won / b.option_trades_closed if b.option_trades_closed else None
    return {
        "total_return": round(total_return, 4),
        "cagr": round(cagr, 4),
        "ann_vol": round(ann_vol, 4),
        "sharpe": round(sharpe, 2),
        "max_drawdown": round(max_dd, 4),
        "final_equity": round(float(eq.iloc[-1]), 2),
        "net_premium": round(b.net_premium, 2),
        "premium_collected": round(b.premium_collected, 2),
        "option_trades_closed": b.option_trades_closed,
        "option_win_rate": round(win_rate, 3) if win_rate is not None else None,
        "n_trades": len(b.log),
    }


def comparison_table(results: list) -> str:
    """Plain-text comparison across strategies."""
    rows = [
        "total_return", "cagr", "ann_vol", "sharpe", "max_drawdown",
        "net_premium", "option_trades_closed", "option_win_rate", "n_trades",
    ]
    names = [r.strategy for r in results]
    width = max(len(n) for n in names) + 2
    header = f"{'metric':<22}" + "".join(f"{n:>{width}}" for n in names)
    lines = [header, "-" * len(header)]
    for row in rows:
        vals = []
        for r in results:
            v = r.metrics.get(row)
            if v is None:
                vals.append("—")
            elif row in ("total_return", "cagr", "ann_vol", "max_drawdown"):
                vals.append(f"{v:.1%}")
            elif isinstance(v, float):
                vals.append(f"{v:,.2f}")
            else:
                vals.append(str(v))
        lines.append(f"{row:<22}" + "".join(f"{v:>{width}}" for v in vals))
    return "\n".join(lines)
