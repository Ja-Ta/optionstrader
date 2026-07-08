"""Cost-basis ledger (docs/05 §2).

Tracks per position:
  - stock lots (shares, cost)
  - premium events (option sales, buybacks, expirations)
  - premium-adjusted cost basis  — the strategy's operational scoreboard
  - honest mark-to-market P&L    — displayed alongside, never instead

Persistence: plain JSON (portfolio.json in the working directory by default).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import date
from pathlib import Path


@dataclass
class StockLot:
    acquired: str          # ISO date
    shares: int
    price: float           # per share
    note: str = ""         # e.g. "assigned from Jan 12.5 put"


@dataclass
class PremiumEvent:
    date: str              # ISO date
    kind: str              # "call" | "put"
    action: str            # "sell" | "buyback" | "expired" | "assigned"
    strike: float
    expiry: str            # ISO date
    contracts: int
    per_share: float       # premium received (sell) or paid (buyback); 0 for expired
    note: str = ""

    @property
    def cash_flow(self) -> float:
        sign = 1.0 if self.action == "sell" else (-1.0 if self.action == "buyback" else 0.0)
        return sign * self.per_share * self.contracts * 100


@dataclass
class OpenShort:
    """A currently-open short option (live state, unlike the event history)."""
    kind: str                # "call" | "put"
    strike: float
    expiry: str              # ISO date
    contracts: int
    premium_collected: float  # per share
    opened: str = ""         # ISO date


@dataclass
class Position:
    ticker: str
    account: str = "long_term"     # "long_term" | "short_term"
    willing_to_add: bool = False
    lots: list[StockLot] = field(default_factory=list)
    premium_events: list[PremiumEvent] = field(default_factory=list)
    open_shorts: list[OpenShort] = field(default_factory=list)

    @property
    def shares(self) -> int:
        return sum(lot.shares for lot in self.lots)

    @property
    def stock_cost(self) -> float:
        return sum(lot.shares * lot.price for lot in self.lots)

    @property
    def net_premium(self) -> float:
        return sum(ev.cash_flow for ev in self.premium_events)

    @property
    def adjusted_basis_per_share(self) -> float | None:
        """The book's scoreboard: (stock cost − net premium) / shares."""
        if self.shares == 0:
            return None
        return (self.stock_cost - self.net_premium) / self.shares

    def mark_to_market(self, price: float) -> dict:
        """Honest P&L at the given price, shown alongside the basis ledger."""
        stock_value = self.shares * price
        return {
            "shares": self.shares,
            "stock_cost": round(self.stock_cost, 2),
            "net_premium": round(self.net_premium, 2),
            "adjusted_basis_per_share": (
                round(self.adjusted_basis_per_share, 4)
                if self.adjusted_basis_per_share is not None
                else None
            ),
            "stock_value": round(stock_value, 2),
            "total_pnl": round(stock_value - self.stock_cost + self.net_premium, 2),
        }

    # --- recording fills (keeps premium_events and open_shorts in sync) ---

    def open_short_shares(self, kind: str) -> int:
        return sum(o.contracts * 100 for o in self.open_shorts if o.kind == kind)

    def find_short(self, kind: str, strike: float, expiry: str) -> OpenShort | None:
        for o in self.open_shorts:
            if o.kind == kind and abs(o.strike - strike) < 1e-6 and o.expiry == expiry:
                return o
        return None

    def buy_shares(self, shares: int, price: float, day: str, note: str = "") -> None:
        if shares <= 0 or price <= 0:
            raise ValueError("shares and price must be positive")
        self.lots.append(StockLot(day, shares, price, note))

    def sell_shares(self, shares: int, price: float, day: str, note: str = "") -> float:
        """FIFO lot reduction. Refuses to strand open short calls uncovered
        (book: never sell stock while short calls remain open — close them first)."""
        if shares > self.shares:
            raise ValueError(f"selling {shares} but only {self.shares} held")
        remaining_after = self.shares - shares
        if remaining_after < self.open_short_shares("call"):
            raise ValueError(
                f"open short calls cover {self.open_short_shares('call')} shares — "
                "buy them back before selling stock (never go naked)"
            )
        left = shares
        for lot in list(self.lots):
            take = min(lot.shares, left)
            lot.shares -= take
            left -= take
            if lot.shares == 0:
                self.lots.remove(lot)
            if left == 0:
                break
        return shares * price

    def record_option_sale(self, kind: str, strike: float, expiry: str, contracts: int,
                           premium: float, day: str, note: str = "") -> list[str]:
        """Record a short-option sale. Enforces the naked-call ban; returns warnings."""
        if contracts <= 0 or premium <= 0:
            raise ValueError("contracts and premium must be positive")
        warnings: list[str] = []
        if kind == "call":
            covered_needed = self.open_short_shares("call") + contracts * 100
            if covered_needed > self.shares:
                raise ValueError(
                    f"NAKED CALL refused: {covered_needed} call-shares vs {self.shares} held "
                    "(docs/04 §1 — never sell calls beyond your share count)"
                )
        if kind == "put" and self.shares > 0:
            total_puts = self.open_short_shares("put") + contracts * 100
            if total_puts > 2 * self.shares:
                warnings.append(
                    f"puts now cover {total_puts} shares vs {self.shares} held — beyond the "
                    "book's 2x cap for owned stock; be sure assignment is affordable"
                )
        self.premium_events.append(PremiumEvent(day, kind, "sell", strike, expiry, contracts, premium, note))
        self.open_shorts.append(OpenShort(kind, strike, expiry, contracts, premium, day))
        return warnings

    def _reduce_short(self, short: OpenShort, contracts: int) -> None:
        if contracts > short.contracts:
            raise ValueError(f"only {short.contracts} contracts open, got {contracts}")
        short.contracts -= contracts
        if short.contracts == 0:
            self.open_shorts.remove(short)

    def record_buyback(self, kind: str, strike: float, expiry: str, price: float,
                       day: str, contracts: int | None = None, note: str = "") -> dict:
        short = self.find_short(kind, strike, expiry)
        if short is None:
            raise ValueError(f"no open short {kind} {strike:g} exp {expiry}")
        n = contracts or short.contracts
        premium = short.premium_collected
        self._reduce_short(short, n)
        self.premium_events.append(PremiumEvent(day, kind, "buyback", strike, expiry, n, price, note))
        captured = 1.0 - price / premium if premium > 0 else 0.0
        return {
            "contracts": n,
            "profit_per_share": premium - price,
            "captured_fraction": captured,
            "rule_25pct_met": price <= 0.25 * premium,
        }

    def record_expired(self, kind: str, strike: float, expiry: str, day: str,
                       contracts: int | None = None) -> dict:
        short = self.find_short(kind, strike, expiry)
        if short is None:
            raise ValueError(f"no open short {kind} {strike:g} exp {expiry}")
        n = contracts or short.contracts
        premium = short.premium_collected
        self._reduce_short(short, n)
        self.premium_events.append(PremiumEvent(day, kind, "expired", strike, expiry, n, 0.0, "expired worthless"))
        return {"contracts": n, "premium_kept": premium * n * 100}

    def record_assigned(self, kind: str, strike: float, expiry: str, day: str,
                        contracts: int | None = None) -> dict:
        """Put assignment: shares put to us at the strike (a planned entry).
        Call assignment: shares called away at the strike (a planned exit)."""
        short = self.find_short(kind, strike, expiry)
        if short is None:
            raise ValueError(f"no open short {kind} {strike:g} exp {expiry}")
        n = contracts or short.contracts
        shares = n * 100
        if kind == "call" and shares > self.shares:
            raise ValueError(f"assignment needs {shares} shares but only {self.shares} held")
        self._reduce_short(short, n)
        self.premium_events.append(PremiumEvent(day, kind, "assigned", strike, expiry, n, 0.0, "assigned"))
        if kind == "put":
            self.buy_shares(shares, strike, day, f"assigned from {expiry} {strike:g} put")
            return {"contracts": n, "shares_acquired": shares, "cost_per_share": strike,
                    "effective_cost": strike - short.premium_collected}
        proceeds = self.sell_shares(shares, strike, day, f"called away ({expiry} {strike:g})")
        return {"contracts": n, "shares_delivered": shares, "proceeds": proceeds}

    def stop_loss_breached(self, close_price: float, stop_pct: float = 0.15) -> bool:
        """Book rule: sell any stock CLOSING 15% below purchase (per-lot check
        against the weighted average raw cost — premium does not rescue a stop)."""
        if self.shares == 0:
            return False
        avg_cost = self.stock_cost / self.shares
        return close_price <= avg_cost * (1 - stop_pct)


@dataclass
class Portfolio:
    positions: dict[str, Position] = field(default_factory=dict)
    path: Path = field(default=Path("portfolio.json"), repr=False)

    def get(self, ticker: str) -> Position:
        t = ticker.upper()
        if t not in self.positions:
            self.positions[t] = Position(ticker=t)
        return self.positions[t]

    # --- persistence ---

    def save(self) -> None:
        data = {
            t: {
                "ticker": p.ticker,
                "account": p.account,
                "willing_to_add": p.willing_to_add,
                "lots": [asdict(l) for l in p.lots],
                "premium_events": [asdict(e) for e in p.premium_events],
                "open_shorts": [asdict(o) for o in p.open_shorts],
            }
            for t, p in self.positions.items()
        }
        self.path.write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls, path: Path = Path("portfolio.json")) -> "Portfolio":
        pf = cls(path=path)
        if not path.exists():
            return pf
        raw = json.loads(path.read_text())
        for t, pdata in raw.items():
            pf.positions[t] = Position(
                ticker=pdata["ticker"],
                account=pdata.get("account", "long_term"),
                willing_to_add=pdata.get("willing_to_add", False),
                lots=[StockLot(**l) for l in pdata.get("lots", [])],
                premium_events=[PremiumEvent(**e) for e in pdata.get("premium_events", [])],
                open_shorts=[OpenShort(**o) for o in pdata.get("open_shorts", [])],
            )
        return pf


def position_size(account_value: float, entry: float, stop: float, risk_pct: float = 0.02) -> int:
    """Book money-management rule (docs/04 §9): shares = (2% of account) / per-share risk."""
    per_share_risk = round(entry - stop, 4)  # cents precision; avoids float-division drift
    if per_share_risk <= 0:
        raise ValueError("stop must be below entry for a long position")
    return int(account_value * risk_pct / per_share_risk + 1e-9)
