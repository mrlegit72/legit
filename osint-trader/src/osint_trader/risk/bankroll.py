"""In-memory bankroll tracker.

Real-money mode should reconcile against on-chain balance via the CLOB client;
for dry-run/paper we just track exposure locally so caps are still enforced.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class Bankroll:
    starting_usdc: float
    open_exposure_by_market: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    realized_pnl: float = 0.0

    @property
    def equity(self) -> float:
        return self.starting_usdc + self.realized_pnl

    @property
    def total_exposure(self) -> float:
        return sum(self.open_exposure_by_market.values())

    def add_exposure(self, market_id: str, size_usdc: float) -> None:
        self.open_exposure_by_market[market_id] += size_usdc

    def settle(self, market_id: str, pnl_usdc: float) -> None:
        self.realized_pnl += pnl_usdc
        self.open_exposure_by_market.pop(market_id, None)
