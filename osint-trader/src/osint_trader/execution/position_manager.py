"""Position lifecycle: take-profit, stop-loss, max-hold flush.

A position is opened when a TradeIntent fills. The manager polls live snapshots
and decides whether to close based on:
  * take-profit: market price now reflects most of the original edge.
  * stop-loss:   adverse move > stop_loss_bps from entry.
  * max-hold:    elapsed > max_hold_hours.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable

from ..models import MarketSnapshot, TradeIntent
from ..observability import get_logger

logger = get_logger(__name__)


@dataclass
class OpenPosition:
    intent: TradeIntent
    entry_price: float
    opened_at: datetime
    target_price: float       # close on take-profit at this price
    stop_price: float         # close on stop-loss at this price
    max_hold_until: datetime


class PositionManager:
    def __init__(
        self,
        snapshot_provider: Callable[[str], MarketSnapshot | None],
        on_close: Callable[[OpenPosition, str, float], Awaitable[None]],
        *,
        take_profit_pct_of_edge: float = 0.7,
        stop_loss_bps: float = 0.20,
        max_hold_hours: float = 24.0,
        poll_seconds: int = 60,
    ) -> None:
        self._snapshot_provider = snapshot_provider
        self._on_close = on_close
        self.take_profit_pct_of_edge = take_profit_pct_of_edge
        self.stop_loss_bps = stop_loss_bps
        self.max_hold_hours = max_hold_hours
        self.poll_seconds = poll_seconds
        self._positions: dict[str, OpenPosition] = {}   # keyed by market_id

    def open(self, intent: TradeIntent, fill_price: float) -> None:
        # YES side: target above entry, stop below. NO side: inverse.
        edge_room = max(0.01, intent.edge)
        if intent.side == "yes":
            target = min(0.99, fill_price + edge_room * self.take_profit_pct_of_edge)
            stop = max(0.01, fill_price * (1.0 - self.stop_loss_bps))
        else:
            target = max(0.01, fill_price - edge_room * self.take_profit_pct_of_edge)
            stop = min(0.99, fill_price * (1.0 + self.stop_loss_bps))

        self._positions[intent.market_id] = OpenPosition(
            intent=intent, entry_price=fill_price,
            opened_at=datetime.now(timezone.utc),
            target_price=target, stop_price=stop,
            max_hold_until=datetime.now(timezone.utc) + timedelta(hours=self.max_hold_hours),
        )
        logger.info("position_opened", market=intent.market_id, side=intent.side,
                    entry=fill_price, target=target, stop=stop)

    def has(self, market_id: str) -> bool:
        return market_id in self._positions

    def close(self, market_id: str) -> None:
        self._positions.pop(market_id, None)

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            await self._tick()
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self.poll_seconds)
            except asyncio.TimeoutError:
                pass

    async def _tick(self) -> None:
        for market_id, pos in list(self._positions.items()):
            snap = self._snapshot_provider(market_id)
            if snap is None:
                continue
            mark = snap.yes_price if pos.intent.side == "yes" else snap.no_price
            now = datetime.now(timezone.utc)
            reason: str | None = None
            if pos.intent.side == "yes":
                if mark >= pos.target_price:
                    reason = "take_profit"
                elif mark <= pos.stop_price:
                    reason = "stop_loss"
            else:
                if mark <= pos.target_price:
                    reason = "take_profit"
                elif mark >= pos.stop_price:
                    reason = "stop_loss"
            if reason is None and now >= pos.max_hold_until:
                reason = "max_hold"
            if reason is None:
                continue
            logger.info("position_close_signal", market=market_id, reason=reason, mark=mark)
            try:
                await self._on_close(pos, reason, mark)
            finally:
                self._positions.pop(market_id, None)
