import random

from osint_trader.markets.fill_model import estimate_fill
from osint_trader.markets.orderbook import BookLevel, OrderBook


def _book(ask=0.41) -> OrderBook:
    return OrderBook(
        bids=[BookLevel(ask - 0.02, 200), BookLevel(ask - 0.03, 400)],
        asks=[BookLevel(ask, 100), BookLevel(ask + 0.01, 200)],
    )


def test_no_book_full_fill():
    filled, price = estimate_fill("yes", 50.0, 0.40, None)
    assert filled == 50.0
    assert price == 0.40


def test_aggressive_taker_eventually_fills_some():
    rng = random.Random(0)
    fills = []
    for _ in range(20):
        f, _ = estimate_fill("yes", 30.0, 0.45, _book(), rng=rng)
        fills.append(f)
    assert sum(1 for f in fills if f > 0) >= 15  # mostly fills at aggressive price


def test_passive_quote_below_ask_misses():
    # Our price (0.39) is below best ask (0.41) → no eligible levels.
    rng = random.Random(0)
    f, _ = estimate_fill("yes", 30.0, 0.39, _book(ask=0.41), rng=rng)
    assert f == 0.0
