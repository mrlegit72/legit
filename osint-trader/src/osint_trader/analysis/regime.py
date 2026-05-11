"""News-volume regime detector.

In calm regimes, signals should clear a higher confidence bar (you don't want
to trade on weak headlines when nothing is happening). In crisis regimes,
news velocity itself is information; lower the bar so you don't miss the
window.

Implementation: rolling 60-min event count vs 24h baseline. The detector
returns a `tightening_bps` value the orchestrator adds to the configured
min_confidence.

  ratio < 0.5     → calm regime, +5 confidence
  0.5 <= r < 1.5  → normal, +0
  1.5 <= r < 3    → elevated, -3
  r >= 3          → crisis, -7
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass
class RegimeDetector:
    short_window_min: int = 60
    long_window_hours: int = 24
    _events: deque[datetime] = field(default_factory=deque)

    def record(self, ts: datetime | None = None) -> None:
        ts = ts or datetime.now(timezone.utc)
        self._events.append(ts)
        cutoff = ts - timedelta(hours=self.long_window_hours)
        while self._events and self._events[0] < cutoff:
            self._events.popleft()

    def regime(self, now: datetime | None = None) -> tuple[str, int]:
        now = now or datetime.now(timezone.utc)
        short_cutoff = now - timedelta(minutes=self.short_window_min)
        short_count = sum(1 for t in self._events if t >= short_cutoff)
        long_count = max(1, len(self._events))
        # Expected per-window if uniformly distributed.
        expected = long_count * (self.short_window_min / (self.long_window_hours * 60))
        ratio = short_count / max(expected, 0.5)
        if ratio < 0.5:
            return "calm", +5
        if ratio < 1.5:
            return "normal", 0
        if ratio < 3.0:
            return "elevated", -3
        return "crisis", -7
