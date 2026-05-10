from osint_trader.analysis import is_relevant_to_any_market
from osint_trader.config import load_markets


def test_filter_keeps_relevant_news():
    markets = load_markets()
    assert is_relevant_to_any_market("Reports of strike on Kharg oil terminal", markets)
    assert is_relevant_to_any_market("Iran's supreme leader speaks", markets)
    assert is_relevant_to_any_market("Naval traffic returns through Hormuz", markets)


def test_filter_drops_unrelated_news():
    markets = load_markets()
    assert not is_relevant_to_any_market("New iPhone announced at WWDC", markets)
    assert not is_relevant_to_any_market("Federer wins Wimbledon final", markets)
