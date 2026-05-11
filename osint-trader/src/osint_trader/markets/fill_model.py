"""Probabilistic fill model for backtests.

Real CLOB fills only happen when the *other* side is willing to take. During
news flashes, that other side often knows what we know — adverse selection.

Model: fill probability is a function of order-book imbalance and our
aggressiveness vs the spread.

  imbalance = bid_depth / (bid_depth + ask_depth)        # 0..1
  aggression = 1 - (our_price - best_ask) / spread       # >=1 if at/above ask
  p_fill = clip(0.10 + 0.5 * imbalance + 0.4 * aggression, 0, 1)

Returns (filled_size_usdc, avg_fill_price). filled_size is *up to* the
requested notional, with the unfilled portion left as a paper "missed" trade.
"""
from __future__ import annotations

import random

from .orderbook import OrderBook


def estimate_fill(
    side: str,
    notional_usdc: float,
    our_price: float,
    book: OrderBook | None,
    *,
    rng: random.Random | None = None,
) -> tuple[float, float]:
    rng = rng or random.Random()
    if book is None or not book.asks:
        # No book → 100% fill at our_price (the optimistic legacy behaviour).
        return notional_usdc, our_price
    best_ask = book.asks[0].price
    best_bid = book.bids[0].price if book.bids else best_ask * 0.95
    spread = max(1e-6, best_ask - best_bid)

    bid_depth = sum(b.size_shares * b.price for b in book.bids[:5])
    ask_depth = sum(a.size_shares * a.price for a in book.asks[:5])
    total = bid_depth + ask_depth
    imbalance = bid_depth / total if total else 0.5

    aggression = 1.0 - (our_price - best_ask) / spread if our_price < best_ask else 1.2
    aggression = max(0.0, min(aggression, 1.5))
    p_fill = max(0.0, min(1.0, 0.10 + 0.5 * imbalance + 0.4 * aggression))

    # Walk the book; for each level, fill its size with prob p_fill.
    remaining = notional_usdc
    spent = 0.0
    shares = 0.0
    for level in book.asks:
        if level.price > our_price:
            break
        if remaining <= 0:
            break
        if rng.random() > p_fill:
            continue
        level_notional = min(remaining, level.price * level.size_shares)
        level_shares = level_notional / level.price
        shares += level_shares
        spent += level_notional
        remaining -= level_notional
    if shares == 0:
        return 0.0, our_price
    return spent, spent / shares
