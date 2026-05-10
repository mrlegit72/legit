from datetime import datetime, timezone

from osint_trader.config import Settings, TradeMode
from osint_trader.models import MarketSnapshot, Signal
from osint_trader.risk import Bankroll, CircuitBreaker, size_trade


def _settings() -> Settings:
    return Settings(
        anthropic_api_key="x",
        trade_mode=TradeMode.DRY_RUN,
        bankroll_usdc=1000,
        max_position_pct=0.05,
        min_edge=0.05,
        min_confidence=80,
        kelly_fraction=0.25,
        daily_loss_limit_pct=0.15,
    )


def _snapshot(yes: float = 0.4) -> MarketSnapshot:
    return MarketSnapshot(
        market_id="iranian-regime-fall",
        slug="will-the-iranian-regime-fall",
        title="Will the Iranian regime fall",
        yes_price=yes, no_price=round(1 - yes, 4),
        liquidity_usdc=10_000.0,
        yes_token_id="100", no_token_id="200",
    )


def _signal(prob: float = 0.6, conf: int = 90, side: str = "yes") -> Signal:
    return Signal(
        market_id="iranian-regime-fall",
        side=side, prob_yes=prob, edge=prob - 0.4, confidence=conf,
        reasoning="test", triggered_by_event_id="evt-1",
        created_at=datetime.now(timezone.utc),
    )


def test_size_trade_emits_intent_when_inputs_clear():
    s = _settings()
    bankroll = Bankroll(starting_usdc=1000)
    breaker = CircuitBreaker(daily_loss_limit_pct=0.15, starting_equity=1000)
    decision = size_trade(_signal(), _snapshot(), settings=s, bankroll=bankroll, breaker=breaker)
    assert decision.intent is not None
    assert decision.intent.side == "yes"
    assert 1.0 <= decision.intent.size_usdc <= s.max_position_pct * bankroll.equity + 1e-6


def test_size_trade_skips_low_confidence():
    s = _settings()
    bankroll = Bankroll(starting_usdc=1000)
    breaker = CircuitBreaker(daily_loss_limit_pct=0.15, starting_equity=1000)
    decision = size_trade(_signal(conf=70), _snapshot(), settings=s, bankroll=bankroll, breaker=breaker)
    assert decision.intent is None
    assert decision.skip_reason and decision.skip_reason.startswith("low_confidence")


def test_size_trade_skips_low_edge():
    s = _settings()
    bankroll = Bankroll(starting_usdc=1000)
    breaker = CircuitBreaker(daily_loss_limit_pct=0.15, starting_equity=1000)
    decision = size_trade(_signal(prob=0.42), _snapshot(), settings=s, bankroll=bankroll, breaker=breaker)
    assert decision.intent is None
    assert decision.skip_reason and decision.skip_reason.startswith("low_edge")


def test_size_trade_blocked_by_breaker():
    s = _settings()
    bankroll = Bankroll(starting_usdc=1000)
    bankroll.realized_pnl = -200  # -20% drawdown
    breaker = CircuitBreaker(daily_loss_limit_pct=0.15, starting_equity=1000)
    decision = size_trade(_signal(), _snapshot(), settings=s, bankroll=bankroll, breaker=breaker)
    assert decision.intent is None
    assert decision.skip_reason and "breaker" in decision.skip_reason
