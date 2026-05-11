from osint_trader.execution.pricing_strategy import quote_for
from osint_trader.markets.orderbook import BookLevel, OrderBook


def _book(best_bid=0.39, best_ask=0.41) -> OrderBook:
    return OrderBook(
        bids=[BookLevel(best_bid, 100), BookLevel(best_bid - 0.01, 200)],
        asks=[BookLevel(best_ask, 100), BookLevel(best_ask + 0.01, 200)],
    )


def test_taker_returns_best_ask():
    assert quote_for("yes", _book(), snapshot_price=0.40, strategy="taker") == 0.41


def test_join_bid_pays_one_tick_above_bid():
    assert quote_for("yes", _book(), snapshot_price=0.40, strategy="join_bid") == 0.391


def test_mid_minus_bp_pays_below_mid():
    quote = quote_for("yes", _book(), snapshot_price=0.40,
                      strategy="mid_minus_bp", basis_points_off_mid=10.0)
    # mid = 0.40, spread = 0.02; offset = 10% * 0.02 = 0.002 → 0.398
    assert quote == 0.398


def test_no_book_falls_back_to_snapshot_price():
    assert quote_for("yes", None, 0.42, strategy="join_bid") == 0.42
