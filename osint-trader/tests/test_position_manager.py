from datetime import datetime, timezone

import pytest

from osint_trader.execution.position_manager import PositionManager
from osint_trader.models import MarketSnapshot, TradeIntent


def _intent(side: str = "yes", edge: float = 0.10) -> TradeIntent:
    return TradeIntent(
        market_id="m1", slug="m1-slug", side=side, token_id="42",
        price=0.40, size_usdc=50.0, edge=edge, confidence=88,
        kelly_fraction_used=0.05, reasoning="r",
        signal_created_at=datetime.now(timezone.utc),
    )


def _snap(yes: float) -> MarketSnapshot:
    return MarketSnapshot(
        market_id="m1", slug="m1-slug", title="t",
        yes_price=yes, no_price=round(1 - yes, 4),
    )


@pytest.mark.asyncio
async def test_take_profit_triggers_close():
    closed: list[tuple[str, float]] = []

    async def on_close(pos, reason, mark):
        closed.append((reason, mark))

    pm = PositionManager(snapshot_provider=lambda mid: _snap(0.55),
                        on_close=on_close, take_profit_pct_of_edge=0.5)
    pm.open(_intent(edge=0.10), fill_price=0.40)
    # entry 0.40, edge 0.10, tp at 0.40 + 0.05 = 0.45 -> 0.55 above => closes.
    await pm._tick()
    assert closed and closed[0][0] == "take_profit"
    assert not pm.has("m1")


@pytest.mark.asyncio
async def test_stop_loss_triggers_close():
    closed: list[tuple[str, float]] = []

    async def on_close(pos, reason, mark):
        closed.append((reason, mark))

    pm = PositionManager(snapshot_provider=lambda mid: _snap(0.30),
                        on_close=on_close, stop_loss_bps=0.20)
    pm.open(_intent(), fill_price=0.40)
    # stop at 0.40 * (1 - 0.20) = 0.32; mark 0.30 below it -> closes.
    await pm._tick()
    assert closed and closed[0][0] == "stop_loss"


@pytest.mark.asyncio
async def test_no_close_when_neutral():
    closed: list[str] = []

    async def on_close(pos, reason, mark):
        closed.append(reason)

    pm = PositionManager(snapshot_provider=lambda mid: _snap(0.41),
                        on_close=on_close)
    pm.open(_intent(), fill_price=0.40)
    await pm._tick()
    assert not closed
    assert pm.has("m1")
