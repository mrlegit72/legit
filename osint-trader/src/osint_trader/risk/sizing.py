"""Convert an analyst Signal into a sized TradeIntent (or a reasoned skip)."""
from __future__ import annotations

from dataclasses import dataclass

from ..config import Settings
from ..markets.pricing import implied_edge, kelly_fraction_for
from ..models import MarketSnapshot, Signal, TradeIntent
from ..observability import get_logger
from .bankroll import Bankroll
from .circuit_breaker import CircuitBreaker

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
    corroboration_multiplier: float = 1.0,
) -> RiskDecision:
    # 1) circuit breaker
    ok, why = breaker.allow_trade(bankroll.equity)
    if not ok:
        return RiskDecision(None, f"breaker:{why}")

    # 2) confidence floor (corroboration-adjusted)
    effective_conf = int(signal.confidence * corroboration_multiplier)
    if effective_conf < settings.min_confidence:
        return RiskDecision(None, f"low_confidence:{effective_conf}<{settings.min_confidence}")

    # 3) live edge floor (recompute from snapshot in case price moved)
    live_edge = implied_edge(signal.prob_yes, snapshot.yes_price, signal.side)
    if live_edge < settings.min_edge:
        return RiskDecision(None, f"low_edge:{live_edge:.3f}<{settings.min_edge}")

    # 4) Kelly sizing, scaled by configured fraction & confidence
    kelly = kelly_fraction_for(signal.prob_yes, snapshot.yes_price, signal.side)
    conf_scalar = effective_conf / 100.0
    fraction = kelly * settings.kelly_fraction * conf_scalar
    fraction = min(fraction, settings.max_position_pct)

    # 5) Cap by free bankroll
    free = max(0.0, bankroll.equity - bankroll.total_exposure)
    size_usdc = round(fraction * bankroll.equity, 2)
    size_usdc = min(size_usdc, free)
    if size_usdc < 1.0:
        return RiskDecision(None, f"size_too_small:{size_usdc}")

    price = snapshot.yes_price if signal.side == "yes" else snapshot.no_price
    token_id = snapshot.yes_token_id if signal.side == "yes" else snapshot.no_token_id

    intent = TradeIntent(
        market_id=signal.market_id,
        slug=snapshot.slug,
        side=signal.side,
        token_id=token_id,
        price=round(price, 4),
        size_usdc=size_usdc,
        edge=round(live_edge, 4),
        confidence=effective_conf,
        kelly_fraction_used=round(fraction, 4),
        reasoning=signal.reasoning,
        signal_created_at=signal.created_at,
    )
    logger.info(
        "trade_sized",
        market=intent.market_id,
        side=intent.side,
        size=intent.size_usdc,
        edge=intent.edge,
        kelly=intent.kelly_fraction_used,
    )
    return RiskDecision(intent, None)
