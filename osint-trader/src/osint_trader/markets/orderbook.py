"""CLOB orderbook helpers.

We pull the public order book from Polymarket's CLOB API and compute:
- best ask / bid for the side we want to take
- weighted fill price for a given USDC notional
- max notional we can fill within a slippage budget
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential


@dataclass
class BookLevel:
    price: float
    size_shares: float


@dataclass
class OrderBook:
    bids: list[BookLevel]   # sorted desc by price
    asks: list[BookLevel]   # sorted asc by price

    def best_ask(self) -> float | None:
        return self.asks[0].price if self.asks else None

    def best_bid(self) -> float | None:
        return self.bids[0].price if self.bids else None

    def fill_for_notional(self, side: str, usdc: float) -> tuple[float, float]:
        """Return (filled_usdc, weighted_avg_price) when buying `side`.

        side="yes" walks asks; side="no" requires a separate book on the NO
        token (caller must pass the NO book).
        """
        levels = self.asks if side == "yes" else self.asks  # see note: caller passes the right book
        remaining = usdc
        spent = 0.0
        shares = 0.0
        for lvl in levels:
            level_notional = lvl.price * lvl.size_shares
            if level_notional >= remaining:
                add_shares = remaining / lvl.price
                shares += add_shares
                spent += remaining
                remaining = 0.0
                break
            shares += lvl.size_shares
            spent += level_notional
            remaining -= level_notional
        if shares == 0:
            return 0.0, 0.0
        avg_price = spent / shares
        return spent, avg_price

    def max_notional_within_slippage(self, side: str, max_slippage: float) -> float:
        """How much $ can we deploy while keeping fill ≤ best_price * (1+slip)."""
        if not self.asks:
            return 0.0
        best = self.asks[0].price
        cap = best * (1.0 + max_slippage)
        notional = 0.0
        for lvl in self.asks:
            if lvl.price > cap:
                break
            notional += lvl.price * lvl.size_shares
        return notional


async def fetch_book(client: httpx.AsyncClient, clob_host: str, token_id: str) -> OrderBook | None:
    """Fetch /book?token_id=... from the CLOB. Returns None on failure."""
    if not token_id:
        return None
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(2),
        wait=wait_exponential(min=1, max=3),
        reraise=True,
    ):
        with attempt:
            resp = await client.get(f"{clob_host.rstrip('/')}/book", params={"token_id": token_id})
            resp.raise_for_status()
            data = resp.json()
    bids = sorted(
        (BookLevel(float(b["price"]), float(b["size"])) for b in data.get("bids", [])),
        key=lambda x: -x.price,
    )
    asks = sorted(
        (BookLevel(float(a["price"]), float(a["size"])) for a in data.get("asks", [])),
        key=lambda x: x.price,
    )
    return OrderBook(bids=bids, asks=asks)
