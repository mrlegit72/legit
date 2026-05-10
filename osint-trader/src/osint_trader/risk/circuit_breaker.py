"""Circuit breaker: blocks new trades after intraday loss limit or repeated errors."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass
class CircuitBreaker:
    daily_loss_limit_pct: float
    starting_equity: float
    cooloff_after_errors: int = 3
    cooloff_minutes: int = 15
    _error_count: int = 0
    _cool_until: datetime | None = field(default=None)

    def record_error(self) -> None:
        self._error_count += 1
        if self._error_count >= self.cooloff_after_errors:
            self._cool_until = datetime.now(timezone.utc) + timedelta(minutes=self.cooloff_minutes)
            self._error_count = 0

    def record_success(self) -> None:
        self._error_count = max(0, self._error_count - 1)

    def allow_trade(self, current_equity: float) -> tuple[bool, str]:
        now = datetime.now(timezone.utc)
        if self._cool_until and now < self._cool_until:
            return False, f"cooloff_active_until_{self._cool_until.isoformat()}"
        loss_pct = (self.starting_equity - current_equity) / max(self.starting_equity, 1e-6)
        if loss_pct >= self.daily_loss_limit_pct:
            return False, f"daily_loss_limit_hit({loss_pct:.2%})"
        return True, "ok"
