"""Scenario-level (correlation bucket) exposure caps."""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from .bankroll import Bankroll


class Scenario(BaseModel):
    id: str
    description: str = ""
    markets: list[str] = Field(default_factory=list)
    max_exposure_pct: float = 0.1


class ScenarioRegistry:
    def __init__(self, scenarios: list[Scenario]) -> None:
        self.scenarios = scenarios
        self._by_market: dict[str, list[Scenario]] = {}
        for sc in scenarios:
            for m in sc.markets:
                self._by_market.setdefault(m, []).append(sc)

    @classmethod
    def load(cls, path: Path) -> "ScenarioRegistry":
        if not path.exists():
            return cls([])
        data = yaml.safe_load(path.read_text()) or {}
        return cls([Scenario(**sc) for sc in data.get("scenarios", [])])

    def remaining_capacity_usdc(self, market_id: str, bankroll: Bankroll) -> float:
        """Smallest free $ allowed by any scenario this market belongs to."""
        scenarios = self._by_market.get(market_id, [])
        if not scenarios:
            return float("inf")
        equity = bankroll.equity
        smallest = float("inf")
        for sc in scenarios:
            cap = sc.max_exposure_pct * equity
            used = sum(bankroll.open_exposure_by_market.get(m, 0.0) for m in sc.markets)
            smallest = min(smallest, max(0.0, cap - used))
        return smallest
