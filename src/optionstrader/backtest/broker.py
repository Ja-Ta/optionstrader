"""Simulated broker for backtests: cash, one underlying, short options.

Settlement policy (v1, documented):
  - Fills at the daily close, option fills via SyntheticPricer (friction-adjusted).
  - Short options settle on the first trading day >= expiry at that day's close:
    ITM -> assignment (call: shares delivered at strike; put: shares put at
    strike), OTM -> expires, premium kept. Early assignment is not simulated;
    the Elias strategy avoids most of it anyway via the tracker rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd


@dataclass
class ShortPos:
    kind: str            # "call" | "put"
    strike: float
    expiry: date
    contracts: int
    premium_collected: float  # per share
    opened: date


@dataclass
class TradeRecord:
    date: date
    what: str
    detail: str
    cash_flow: float


@dataclass
class SimBroker:
    cash: float
    shares: int = 0
    avg_cost: float = 0.0
    shorts: list[ShortPos] = field(default_factory=list)
    log: list[TradeRecord] = field(default_factory=list)
    premium_collected: float = 0.0
    premium_paid_back: float = 0.0
    option_trades_closed: int = 0
    option_trades_won: int = 0

    # --- stock ---

    def buy_stock(self, n: int, price: float, today: date, note: str = "") -> None:
        cost = n * price
        if n <= 0 or cost > self.cash + 1e-9:
            return
        new_total = self.shares + n
        self.avg_cost = (self.avg_cost * self.shares + cost) / new_total if new_total else 0.0
        self.shares = new_total
        self.cash -= cost
        self.log.append(TradeRecord(today, "buy_stock", f"{n} @ {price:.2f} {note}", -cost))

    def sell_stock(self, n: int, price: float, today: date, note: str = "") -> None:
        n = min(n, self.shares)
        if n <= 0:
            return
        self.shares -= n
        self.cash += n * price
        if self.shares == 0:
            self.avg_cost = 0.0
        self.log.append(TradeRecord(today, "sell_stock", f"{n} @ {price:.2f} {note}", n * price))

    # --- options ---

    def open_calls(self) -> list[ShortPos]:
        return [s for s in self.shorts if s.kind == "call"]

    def open_puts(self) -> list[ShortPos]:
        return [s for s in self.shorts if s.kind == "put"]

    def sell_option(self, kind: str, strike: float, expiry: date, contracts: int,
                    premium: float, today: date, note: str = "") -> ShortPos | None:
        if contracts <= 0 or premium <= 0:
            return None
        pos = ShortPos(kind, strike, expiry, contracts, premium, today)
        self.shorts.append(pos)
        credit = premium * contracts * 100
        self.cash += credit
        self.premium_collected += credit
        self.log.append(
            TradeRecord(today, f"sell_{kind}", f"{contracts}x {strike:g} {expiry} @ {premium:.2f} {note}", credit)
        )
        return pos

    def buy_back(self, pos: ShortPos, price: float, today: date, note: str = "") -> None:
        if pos not in self.shorts:
            return
        self.shorts.remove(pos)
        debit = price * pos.contracts * 100
        self.cash -= debit
        self.premium_paid_back += debit
        self.option_trades_closed += 1
        if price < pos.premium_collected:
            self.option_trades_won += 1
        self.log.append(
            TradeRecord(today, f"buyback_{pos.kind}", f"{pos.contracts}x {pos.strike:g} @ {price:.2f} {note}", -debit)
        )

    def settle_expirations(self, today: date, close: float) -> None:
        for pos in list(self.shorts):
            if pos.expiry > today:
                continue
            self.shorts.remove(pos)
            self.option_trades_closed += 1
            n = pos.contracts * 100
            if pos.kind == "call" and close > pos.strike:
                # Assigned: deliver shares at strike (assume covered; excess ignored by strategies).
                delivered = min(n, self.shares)
                self.shares -= delivered
                self.cash += delivered * pos.strike
                if self.shares == 0:
                    self.avg_cost = 0.0
                self.log.append(
                    TradeRecord(today, "call_assigned", f"{delivered} called away @ {pos.strike:g}", delivered * pos.strike)
                )
            elif pos.kind == "put" and close < pos.strike:
                cost = n * pos.strike
                new_total = self.shares + n
                self.avg_cost = (self.avg_cost * self.shares + cost) / new_total
                self.shares = new_total
                self.cash -= cost
                self.log.append(TradeRecord(today, "put_assigned", f"{n} put to us @ {pos.strike:g}", -cost))
            else:
                self.option_trades_won += 1
                self.log.append(TradeRecord(today, f"{pos.kind}_expired", f"{pos.contracts}x {pos.strike:g} worthless", 0.0))

    # --- valuation ---

    def short_liability(self, spot: float, today: date, closes: pd.Series, pricer) -> float:
        return sum(
            pricer.fair(p.kind, spot, p.strike, today, p.expiry, closes) * p.contracts * 100
            for p in self.shorts
        )

    def equity(self, spot: float, today: date, closes: pd.Series, pricer) -> float:
        return self.cash + self.shares * spot - self.short_liability(spot, today, closes, pricer)

    @property
    def net_premium(self) -> float:
        return self.premium_collected - self.premium_paid_back
