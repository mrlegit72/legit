"""Settlement & PnL reconciliation.

When a position closes (manually or via PositionManager), realised PnL flows
back into Bankroll so the daily-loss circuit breaker can actually fire on real
losses. We also write a `settlements` row so per-source learning can ask
"did this signal ultimately win?".
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..models import TradeIntent
from ..observability import get_logger
from ..persistence import Store
from ..risk.bankroll import Bankroll

logger = get_logger(__name__)


class Settlement:
    def __init__(self, store: Store, bankroll: Bankroll) -> None:
        self.store = store
        self.bankroll = bankroll

    async def settle(
        self,
        intent: TradeIntent,
        entry_price: float,
        exit_price: float,
        reason: str,
        triggered_by_event_id: str,
    ) -> float:
        """Record an exit, update bankroll, and persist for learning.

        Realised PnL approximation per $1 of size (limit-order at entry price):
            shares = size / entry_price
            payout = shares * exit_price
            pnl = payout - size
        For NO side we use (1 - price) as the "cost" of a NO share.
        """
        size = intent.size_usdc
        if intent.side == "yes":
            shares = size / max(entry_price, 1e-6)
            payout = shares * exit_price
        else:
            shares = size / max(1.0 - entry_price, 1e-6)
            payout = shares * (1.0 - exit_price)
        pnl = payout - size

        self.bankroll.settle(intent.market_id, pnl)
        await self.store.save_settlement(
            market_id=intent.market_id,
            side=intent.side,
            entry_price=entry_price,
            exit_price=exit_price,
            size_usdc=size,
            pnl_usdc=pnl,
            reason=reason,
            triggered_by_event_id=triggered_by_event_id,
            settled_at=datetime.now(timezone.utc),
        )
        logger.info("settled", market=intent.market_id, pnl=round(pnl, 2),
                    reason=reason, equity=round(self.bankroll.equity, 2))
        return pnl
