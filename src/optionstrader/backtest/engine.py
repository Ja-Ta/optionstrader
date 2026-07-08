"""Backtest loop: daily bars -> settle expirations -> strategy -> record equity."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .broker import SimBroker, TradeRecord
from .pricing import SyntheticPricer
from .strategies import Strategy


@dataclass
class BacktestResult:
    strategy: str
    equity: pd.Series                      # daily equity curve
    broker: SimBroker
    metrics: dict = field(default_factory=dict)

    @property
    def trades(self) -> list[TradeRecord]:
        return self.broker.log


def run_backtest(
    df: pd.DataFrame,
    strategy: Strategy,
    initial_cash: float = 100_000.0,
    pricer: SyntheticPricer | None = None,
    warmup: int = 60,
) -> BacktestResult:
    """df: daily OHLCV, ascending DatetimeIndex, length > warmup."""
    if len(df) <= warmup:
        raise ValueError(f"need more than {warmup} bars, got {len(df)}")
    pricer = pricer or SyntheticPricer()
    broker = SimBroker(cash=initial_cash)
    dates, equities = [], []

    for i in range(warmup, len(df)):
        history = df.iloc[: i + 1]
        today = history.index[-1].date()
        close = float(history["close"].iloc[-1])
        closes = history["close"]

        broker.settle_expirations(today, close)
        strategy.on_bar(history, today, broker, pricer)

        dates.append(history.index[-1])
        equities.append(broker.equity(close, today, closes, pricer))

    from .metrics import compute_metrics

    result = BacktestResult(
        strategy=strategy.name,
        equity=pd.Series(equities, index=pd.DatetimeIndex(dates)),
        broker=broker,
    )
    result.metrics = compute_metrics(result)
    return result
