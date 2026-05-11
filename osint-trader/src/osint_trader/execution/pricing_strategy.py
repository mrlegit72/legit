"""Order-pricing strategies that reduce adverse selection.

The naive thing is to take the best ask. During news flashes that gets you
filled by faster bots that already know the headline. Two safer choices:

  - join_best_bid: post YES at best_bid + tick (a maker order). Fills slower
    but at a better price.
  - mid_minus_bp: split the spread at mid - basis_points*spread. Aggressive
    enough to fill in normal markets but won't pay the full taker tax.

Both fall back to taker (best_ask) if the book is too thin.
"""
from __future__ import annotations

from typing import Literal

from ..markets.orderbook import OrderBook

Strategy = Literal["taker", "join_bid", "mid_minus_bp"]
TICK = 0.001  # Polymarket CLOB tick size


def quote_for(
    side: str,
    book: OrderBook | None,
    snapshot_price: float,
    *,
    strategy: Strategy = "taker",
    basis_points_off_mid: float = 5.0,
) -> float:
    if book is None or not book.asks or not book.bids:
        return snapshot_price

    best_ask = book.asks[0].price
    best_bid = book.bids[0].price
    spread = max(0.0, best_ask - best_bid)
    mid = (best_ask + best_bid) / 2.0

    if strategy == "taker":
        return best_ask
    if strategy == "join_bid":
        # Join the bid one tick behind for queue priority.
        return round(min(best_bid + TICK, best_ask - TICK), 4)
    if strategy == "mid_minus_bp":
        # bp here is fraction of spread, not 1/100; e.g. 5 → mid - 5%*spread
        offset = (basis_points_off_mid / 100.0) * spread
        if side == "yes":
            return round(min(mid - offset, best_ask), 4)
        return round(min(mid - offset, best_ask), 4)
    return best_ask
