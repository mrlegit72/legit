from osint_trader.markets.pricing import expected_value, implied_edge, kelly_fraction_for


def test_implied_edge_yes_and_no_are_symmetric():
    # If your true prob is 0.6 and market YES is 0.4, YES edge is +0.2.
    # The same scenario from NO perspective: market NO is 0.6, your prob NO is 0.4 -> -0.2.
    assert abs(implied_edge(0.6, 0.4, "yes") - 0.2) < 1e-9
    assert abs(implied_edge(0.6, 0.4, "no") + 0.2) < 1e-9


def test_expected_value_positive_when_underpriced():
    # YES at 0.4 with true prob 0.6 -> EV = 0.6 * (1/0.4) - 1 = 0.5
    assert abs(expected_value(0.6, 0.4, "yes") - 0.5) < 1e-9


def test_kelly_fraction_zero_when_no_edge():
    # No edge -> Kelly should be ~0
    assert kelly_fraction_for(0.4, 0.4, "yes") == 0.0


def test_kelly_fraction_positive_when_edge():
    f = kelly_fraction_for(0.6, 0.4, "yes")
    # Kelly = (b*q - (1-q)) / b ; b = 1/0.4 - 1 = 1.5 ; (1.5*0.6 - 0.4)/1.5 = 0.333...
    assert abs(f - 1 / 3) < 1e-6


def test_kelly_clamped_to_zero_for_negative_edge():
    f = kelly_fraction_for(0.3, 0.5, "yes")
    assert f == 0.0
