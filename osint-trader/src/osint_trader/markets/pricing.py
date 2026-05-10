"""Pricing math: edge, EV, Kelly fraction.

For binary YES/NO markets where you pay `p` per share that pays $1 if right:
- True probability of winning: q.
- Edge = q - p (for YES); for NO it's (1-q) - (1-p) = p - q, same magnitude.
- Decimal odds for a YES bet at price p: 1/p; payoff per $1 staked = 1/p - 1.
- Kelly optimal fraction: f* = (bq - (1-q)) / b, where b = 1/p - 1.
"""
from __future__ import annotations


def implied_edge(prob_true: float, market_price_yes: float, side: str) -> float:
    if side == "yes":
        return prob_true - market_price_yes
    if side == "no":
        return (1.0 - prob_true) - (1.0 - market_price_yes)
    raise ValueError(f"side must be 'yes' or 'no', got {side}")


def expected_value(prob_true: float, market_price_yes: float, side: str) -> float:
    """EV per $1 staked at the given side's price."""
    if side == "yes":
        p = market_price_yes
        return prob_true * (1.0 / max(p, 1e-6)) - 1.0
    p = 1.0 - market_price_yes
    return (1.0 - prob_true) * (1.0 / max(p, 1e-6)) - 1.0


def kelly_fraction_for(prob_true: float, market_price_yes: float, side: str) -> float:
    """Full Kelly fraction; clamp at 0 (never bet against your edge)."""
    if side == "yes":
        q, p = prob_true, market_price_yes
    else:
        q, p = 1.0 - prob_true, 1.0 - market_price_yes
    p = max(min(p, 0.99), 0.01)
    b = 1.0 / p - 1.0
    if b <= 0:
        return 0.0
    f = (b * q - (1.0 - q)) / b
    # Tiny floating-point residue ("no edge") gets snapped to 0 so callers can
    # treat 0 as an unambiguous "don't bet" signal.
    if abs(f) < 1e-9:
        return 0.0
    return max(0.0, min(f, 1.0))
