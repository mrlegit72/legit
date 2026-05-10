"""Open-order watchdog.

Tracks unfilled limit orders and cancel-replaces them when the live ask drifts
past `repricing_bps` from the order price, or when `timeout_minutes` elapses.

In dry_run/paper modes this is a no-op tracker (still useful for tests).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from ..models import TradeIntent
from ..observability import get_logger

logger = get_logger(__name__)


@dataclass
class TrackedOrder:
    intent: TradeIntent
    order_id: str
    placed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class OrderMonitor:
    def __init__(
        self,
        client,                     # PolymarketClient
        snapshot_provider,          # Callable[[str], MarketSnapshot|None]
        *,
        repricing_bps: float = 0.02,
        timeout_minutes: int = 5,
        poll_seconds: int = 30,
    ) -> None:
        self._client = client
        self._snapshot_provider = snapshot_provider
        self.repricing_bps = repricing_bps
        self.timeout_minutes = timeout_minutes
        self.poll_seconds = poll_seconds
        self._open: dict[str, TrackedOrder] = {}

    def track(self, intent: TradeIntent, order_id: str) -> None:
        self._open[order_id] = TrackedOrder(intent=intent, order_id=order_id)

    def forget(self, order_id: str) -> None:
        self._open.pop(order_id, None)

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            await self._tick()
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self.poll_seconds)
            except asyncio.TimeoutError:
                pass

    async def _tick(self) -> None:
        now = datetime.now(timezone.utc)
        for order_id, tracked in list(self._open.items()):
            if now - tracked.placed_at > timedelta(minutes=self.timeout_minutes):
                logger.info("order_timeout_cancel", order=order_id, market=tracked.intent.market_id)
                await self._client.cancel_order(order_id)
                self.forget(order_id)
                continue
            snap = self._snapshot_provider(tracked.intent.market_id)
            if snap is None:
                continue
            mark = snap.yes_price if tracked.intent.side == "yes" else snap.no_price
            drift = abs(mark - tracked.intent.price) / max(tracked.intent.price, 0.01)
            if drift >= self.repricing_bps:
                logger.info("order_drift_cancel", order=order_id, drift=round(drift, 4))
                await self._client.cancel_order(order_id)
                self.forget(order_id)
