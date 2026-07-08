"""Backtest strategies.

  BuyAndHold       — benchmark 1: what doing nothing earns.
  NaiveCoveredCall — benchmark 2: BXM-style systematic writing, no timing —
                     sell the nearest OTM monthly call every cycle, hold to
                     expiration, rebuy shares if assigned.
  EliasEngine      — the Tier-1 decision state machine driving trades: calls
                     sold only on fading momentum above resistance, puts at
                     support (optional), 25% buy-back harvesting, shake-out
                     holds, 15% stop-loss.

The value the book's timing rules add = EliasEngine vs NaiveCoveredCall.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from ..analysis import build_snapshot
from ..config import Config, DEFAULT
from ..signals import Action, assess
from ..signals.states import ShortOptionView
from ..indicators import detect_levels, nearest_resistance, nearest_support
from ..options.selector import select_call_strike, select_put_strike
from .broker import SimBroker
from .pricing import SyntheticPricer, pick_expiry, strike_grid


class Strategy:
    name = "base"

    def on_bar(self, history: pd.DataFrame, today: date, broker: SimBroker, pricer: SyntheticPricer) -> None:
        raise NotImplementedError


class BuyAndHold(Strategy):
    name = "buy_and_hold"

    def on_bar(self, history, today, broker, pricer):
        close = float(history["close"].iloc[-1])
        if broker.shares == 0 and not broker.log:
            broker.buy_stock(int(broker.cash // close), close, today, "initial")


class NaiveCoveredCall(Strategy):
    """Sell the nearest OTM strike, nearest monthly expiry (>= 21 DTE), every
    time no call is open. No timing, no buy-backs. Rebuy after assignment."""

    name = "naive_covered_call"

    def on_bar(self, history, today, broker, pricer):
        close = float(history["close"].iloc[-1])
        closes = history["close"]
        if broker.shares < 100:
            lots = int(broker.cash // (close * 100))
            if lots > 0:
                broker.buy_stock(lots * 100, close, today, "(re)establish")
        if broker.shares >= 100 and not broker.open_calls():
            grid = [s for s in strike_grid(close) if s > close]
            expiry = pick_expiry(today, min_dte=21, max_dte=45)
            if grid and expiry:
                strike = grid[0]
                prem = pricer.sell_fill("call", close, strike, today, expiry, closes)
                if prem >= 0.05:
                    broker.sell_option("call", strike, expiry, broker.shares // 100, prem, today, "naive")


class EliasEngine(Strategy):
    """Drives the Tier-1 state machine each bar and executes its actions."""

    name = "elias_engine"

    def __init__(self, willing_to_add: bool = False, cfg: Config = DEFAULT):
        self.willing_to_add = willing_to_add
        self.cfg = cfg

    def _short_views(self, broker: SimBroker, close: float, today: date, closes: pd.Series, pricer) -> list[ShortOptionView]:
        return [
            ShortOptionView(
                kind=p.kind, strike=p.strike, expiry=p.expiry, contracts=p.contracts,
                premium_collected=p.premium_collected,
                current_price=pricer.fair(p.kind, close, p.strike, today, p.expiry, closes),
            )
            for p in broker.shorts
        ]

    def on_bar(self, history, today, broker, pricer):
        close = float(history["close"].iloc[-1])
        closes = history["close"]
        b = self.cfg.book

        # Establish the initial position (round lots so calls are writable).
        if broker.shares == 0 and not broker.log:
            lots = int(broker.cash // (close * 100))
            if lots > 0:
                broker.buy_stock(lots * 100, close, today, "initial")
            return

        # Re-entry after assignment/stop: the book's "price surge point" —
        # MA(10) crossing up through EMA(20) with non-negative money flow.
        if broker.shares == 0:
            snap = build_snapshot("BT", history, cfg=self.cfg)
            if snap.ma10_crossed_up_ema20 and snap.cmf >= 0:
                lots = int(broker.cash // (close * 100))
                if lots > 0:
                    broker.buy_stock(lots * 100, close, today, "re-entry@surge-point")
            return

        # 15% stop-loss: close short calls, then exit (book rule, docs/04 §9).
        if broker.shares > 0 and broker.avg_cost > 0 and close <= broker.avg_cost * (1 - b.stock_stop_loss):
            for p in list(broker.open_calls()):
                broker.buy_back(p, pricer.buy_fill(p.kind, close, p.strike, today, p.expiry, closes), today, "stop-loss")
            broker.sell_stock(broker.shares, close, today, "15% stop-loss")
            return

        snap = build_snapshot(
            "BT", history,
            shares_held=broker.shares,
            willing_to_add=self.willing_to_add,
            short_options=self._short_views(broker, close, today, closes, pricer),
            cfg=self.cfg,
        )
        result = assess(snap, self.cfg)

        for action in result.actions:
            if action == Action.ROLL_OR_ACCEPT_ASSIGNMENT:
                # Book's roll-up (docs/04 §1): buy back the threatened call,
                # finance with the next strike up at a later expiry. Threatened
                # puts are left to assignment (a planned entry, book behavior).
                for p in list(broker.open_calls()):
                    if close <= p.strike:
                        continue
                    grid_up = [s for s in strike_grid(close) if s > p.strike]
                    new_expiry = pick_expiry(today)
                    if not grid_up or new_expiry is None:
                        continue
                    new_strike = grid_up[0]
                    cost = pricer.buy_fill("call", close, p.strike, today, p.expiry, closes)
                    credit = pricer.sell_fill("call", close, new_strike, today, new_expiry, closes)
                    if credit >= cost:  # roll only when the later month funds the buyback
                        broker.buy_back(p, cost, today, "roll-up")
                        broker.sell_option("call", new_strike, new_expiry, p.contracts, credit, today, "roll-up")

            elif action in (Action.BUY_BACK_CALLS, Action.BUY_BACK_PUTS):
                kind = "call" if action == Action.BUY_BACK_CALLS else "put"
                for p in list(broker.shorts):
                    if p.kind != kind:
                        continue
                    px = pricer.buy_fill(kind, close, p.strike, today, p.expiry, closes)
                    if px <= b.buyback_fraction * p.premium_collected:
                        broker.buy_back(p, px, today, "25% rule")

            elif action == Action.SELL_COVERED_CALLS and not broker.open_calls() and broker.shares >= 100:
                anchor = snap.nearest_resistance or close * (1 + b.call_target_min)
                choice = select_call_strike(strike_grid(close), anchor, close)
                expiry = pick_expiry(today)
                if choice and expiry:
                    prem = pricer.sell_fill("call", close, choice.strike, today, expiry, closes)
                    if prem >= 0.05:
                        broker.sell_option("call", choice.strike, expiry, broker.shares // 100, prem, today, "fade@resistance")

            elif action == Action.SELL_PUTS and self.willing_to_add and not broker.open_puts():
                anchor = snap.nearest_support or close * (1 - b.put_target)
                choice = select_put_strike(strike_grid(close), anchor, close)
                expiry = pick_expiry(today)
                if choice and expiry:
                    contracts = min(
                        broker.shares // 100,                                 # 1x held (conservative; book allows 2x)
                        int(broker.cash // (choice.strike * 100)),            # cash-secured
                    )
                    prem = pricer.sell_fill("put", close, choice.strike, today, expiry, closes)
                    if contracts > 0 and prem >= 0.05:
                        broker.sell_option("put", choice.strike, expiry, contracts, prem, today, "support")

            elif action == Action.DEFENSIVE_CALL_LADDER and broker.shares >= 100 and not broker.open_calls():
                # Breakdown defense: sell the nearest strike at/above price.
                grid = [s for s in strike_grid(close) if s >= close]
                expiry = pick_expiry(today)
                if grid and expiry:
                    prem = pricer.sell_fill("call", close, grid[0], today, expiry, closes)
                    if prem >= 0.05:
                        broker.sell_option("call", grid[0], expiry, broker.shares // 100, prem, today, "defense")
