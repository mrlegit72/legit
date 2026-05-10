"""Per-market signal cooldown: prevent doubling-up on the same trade.

Allows a re-entry only if the edge widened materially (default: +5pp).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass
class _Last:
    when: datetime
    edge: float


@dataclass
class CooldownTracker:
    minutes: int = 30
    edge_widening_required: float = 0.05
    _last: dict[tuple[str, str], _Last] = field(default_factory=dict)

    def allow(self, market_id: str, side: str, current_edge: float) -> tuple[bool, str]:
        key = (market_id, side)
        last = self._last.get(key)
        if last is None:
            return True, "ok"
        elapsed = datetime.now(timezone.utc) - last.when
        if elapsed >= timedelta(minutes=self.minutes):
            return True, "ok"
        if current_edge - last.edge >= self.edge_widening_required:
            return True, f"edge_widened(+{current_edge - last.edge:.3f})"
        return False, f"cooldown_active(remaining={self.minutes - int(elapsed.total_seconds() // 60)}m)"

    def record(self, market_id: str, side: str, edge: float) -> None:
        self._last[(market_id, side)] = _Last(datetime.now(timezone.utc), edge)
