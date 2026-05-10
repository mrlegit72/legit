"""Convert an analyst Signal into a sized TradeIntent (or a reasoned skip).

Filters in order:
  1. Circuit breaker (daily loss / error cooldown)
  2. Per-market signal cooldown (no churning the same trade)
  3. Confidence floor (corroboration-adjusted)
  4. Live edge floor recomputed against the snapshot
  5. Liquidity floor (need depth or it's a wishlist not a trade)
  6. Kelly sizing × KELLY_FRACTION × confidence_scalar capped at MAX_POSITION_PCT
  7. Free-bankroll cap
  8. Scenario bucket cap (correlated markets share a budget)
  9. Slippage gate using the live order book (worst-case avg fill ≤ price*(1+slip))
"""
from __future__ import annotations

from dataclasses import dataclass

from ..config import Settings
from ..markets.orderbook import OrderBook
from ..markets.pricing import implied_edge, kelly_fraction_for
from ..models import MarketSnapshot, Signal, TradeIntent
from ..observability import get_logger
from .bankroll import Bankroll
from .circuit_breaker import CircuitBreaker
from .cooldown import CooldownTracker
from .scenarios import ScenarioRegistry

logger = get_logger(__name__)


@dataclass
class RiskDecision:
    intent: TradeIntent | None
    skip_reason: str | None


def size_trade(
    signal: Signal,
    snapshot: MarketSnapshot,
    *,
    settings: Settings,
    bankroll: Bankroll,
    breaker: CircuitBreaker,
    cooldown: CooldownTracker | None = None,
    scenarios: ScenarioRegistry | None = None,
    book: OrderBook | None = None,
    corroboration_multiplier: float = 1.0,
    min_liquidity_usdc: float = 200.0,
    max_slippage: float = 0.03,
) -> RiskDecision:
    # 1) circuit breaker
    ok, why = breaker.allow_trade(bankroll.equity)
    if not ok:
        return RiskDecision(None, f"breaker:{why}")

    # 2) per-market cooldown
    live_edge = implied_edge(signal.prob_yes, snapshot.yes_price, signal.side)
    if cooldown is not None:
        ok, why = cooldown.allow(signal.market_id, signal.side, live_edge)
        if not ok:
            return RiskDecision(None, why)

    # 3) confidence floor (corroboration-adjusted)
    effective_conf = int(signal.confidence * corroboration_multiplier)
    if effective_conf < settings.min_confidence:
        return RiskDecision(None, f"low_confidence:{effective_conf}<{settings.min_confidence}")

    # 4) live edge floor
    if live_edge < settings.min_edge:
        return RiskDecision(None, f"low_edge:{live_edge:.3f}<{settings.min_edge}")

    # 5) liquidity floor
    if snapshot.liquidity_usdc < min_liquidity_usdc:
        return RiskDecision(None, f"low_liquidity:${snapshot.liquidity_usdc:.0f}<${min_liquidity_usdc:.0f}")

    # 6) Kelly sizing
    kelly = kelly_fraction_for(signal.prob_yes, snapshot.yes_price, signal.side)
    conf_scalar = effective_conf / 100.0
    fraction = kelly * settings.kelly_fraction * conf_scalar
    fraction = min(fraction, settings.max_position_pct)
    desired = round(fraction * bankroll.equity, 2)

    # 7) free bankroll
    free = max(0.0, bankroll.equity - bankroll.total_exposure)
    size_usdc = min(desired, free)

    # 8) scenario cap
    if scenarios is not None:
        scenario_cap = scenarios.remaining_capacity_usdc(signal.market_id, bankroll)
        if scenario_cap < 1.0:
            return RiskDecision(None, "scenario_cap_full")
        size_usdc = min(size_usdc, scenario_cap)

    # 9) slippage gate (only if we have a book)
    if book is not None:
        max_book_notional = book.max_notional_within_slippage(signal.side, max_slippage)
        if max_book_notional < 1.0:
            return RiskDecision(None, "no_book_depth")
        size_usdc = min(size_usdc, max_book_notional)

    if size_usdc < 1.0:
        return RiskDecision(None, f"size_too_small:{size_usdc:.2f}")

    # Fill price: use book best ask if we have it; else snapshot side price.
    if book is not None and book.asks:
        price = book.asks[0].price
    else:
        price = snapshot.yes_price if signal.side == "yes" else snapshot.no_price
    token_id = snapshot.yes_token_id if signal.side == "yes" else snapshot.no_token_id

    intent = TradeIntent(
        market_id=signal.market_id,
        slug=snapshot.slug,
        side=signal.side,
        token_id=token_id,
        price=round(price, 4),
        size_usdc=round(size_usdc, 2),
        edge=round(live_edge, 4),
        confidence=effective_conf,
        kelly_fraction_used=round(fraction, 4),
        reasoning=signal.reasoning,
        signal_created_at=signal.created_at,
    )
    if cooldown is not None:
        cooldown.record(signal.market_id, signal.side, live_edge)
    logger.info(
        "trade_sized",
        market=intent.market_id, side=intent.side, size=intent.size_usdc,
        edge=intent.edge, kelly=intent.kelly_fraction_used,
    )
    return RiskDecision(intent, None)
