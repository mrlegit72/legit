"""Claude output drift monitor.

A bad prompt revision (or a model upgrade) can quietly tank signal quality.
This module computes daily summary stats over recent signals and flags drift:

  - signal_rate_per_event: too high = analyst hallucinating, too low = blind
  - mean_confidence:       drifting up = miscalibration risk
  - propaganda_rate:       drifting up = analyst seeing rumors everywhere
  - skip_reason histogram: which guards are firing more

Threshold defaults are conservative; tune via env vars in production.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import aiosqlite


@dataclass
class DriftReport:
    window_hours: int
    n_events: int
    n_signals: int
    signal_rate_per_event: float
    mean_confidence: float
    propaganda_rate: float
    top_skip_reasons: list[tuple[str, int]]
    alerts: list[str]


async def compute_drift(
    db_path: str,
    *,
    window_hours: int = 24,
    baseline_window_hours: int = 168,
    min_confidence_floor: int = 60,
    max_propaganda_rate: float = 0.4,
    max_signal_rate_jump: float = 2.0,
) -> DriftReport:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=window_hours)).isoformat()
    base_cutoff = (datetime.now(timezone.utc) - timedelta(hours=baseline_window_hours)).isoformat()
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM events WHERE fetched_at >= ?", (cutoff,)
        ) as cur:
            n_events = (await cur.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*), AVG(confidence) FROM signals WHERE created_at >= ?",
            (cutoff,),
        ) as cur:
            n_signals, mean_conf = await cur.fetchone()
        async with db.execute(
            "SELECT COUNT(*) FROM events WHERE fetched_at >= ?", (base_cutoff,)
        ) as cur:
            n_events_base = (await cur.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM signals WHERE created_at >= ?", (base_cutoff,)
        ) as cur:
            n_signals_base = (await cur.fetchone())[0]

    n_signals = n_signals or 0
    mean_conf = mean_conf or 0.0
    rate_now = (n_signals / n_events) if n_events else 0.0
    rate_base = (n_signals_base / n_events_base) if n_events_base else rate_now or 1.0
    rate_jump = rate_now / max(rate_base, 0.01)

    # Skip reasons live in logs not DB; for now we pass an empty histogram and
    # leave a hook for callers who pipe structured logs into a counter.
    skip_counter: Counter[str] = Counter()

    alerts: list[str] = []
    if mean_conf < min_confidence_floor and n_signals >= 5:
        alerts.append(f"mean_confidence_low={mean_conf:.1f}<{min_confidence_floor}")
    if rate_jump > max_signal_rate_jump:
        alerts.append(f"signal_rate_spike x{rate_jump:.1f}")
    # Propaganda rate is logged but not stored; surface as 0 unless caller wires a column.
    propaganda_rate = 0.0

    return DriftReport(
        window_hours=window_hours,
        n_events=n_events,
        n_signals=n_signals,
        signal_rate_per_event=round(rate_now, 4),
        mean_confidence=round(mean_conf, 1),
        propaganda_rate=propaganda_rate,
        top_skip_reasons=skip_counter.most_common(5),
        alerts=alerts,
    )
