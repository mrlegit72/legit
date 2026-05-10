from osint_trader.markets.orderbook import BookLevel, OrderBook


def test_max_notional_within_slippage_walks_levels():
    book = OrderBook(
        bids=[],
        asks=[
            BookLevel(price=0.40, size_shares=100),   # $40
            BookLevel(price=0.41, size_shares=200),   # $82
            BookLevel(price=0.45, size_shares=500),   # $225 (above 3% slip)
        ],
    )
    # 3% slippage above 0.40 = max price 0.412 -> first two levels qualify.
    assert book.max_notional_within_slippage("yes", 0.03) == 100 * 0.40 + 200 * 0.41


def test_max_notional_zero_when_book_empty():
    book = OrderBook(bids=[], asks=[])
    assert book.max_notional_within_slippage("yes", 0.05) == 0.0


def test_best_ask_and_bid():
    book = OrderBook(
        bids=[BookLevel(0.39, 100), BookLevel(0.38, 200)],
        asks=[BookLevel(0.41, 100), BookLevel(0.42, 100)],
    )
    assert book.best_ask() == 0.41
    assert book.best_bid() == 0.39
