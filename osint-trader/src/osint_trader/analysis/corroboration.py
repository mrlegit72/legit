"""Cross-source corroboration scoring with graded recency decay.

A single tweet from a pro-regime channel is worth nearly nothing; the same
claim across Reuters + amitsegal + GDELT within minutes is highly actionable.

Output is a multiplier in [0, 1] applied to analyst confidence at decision
time, plus the list of corroborating events (passed to Claude as context).
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from rapidfuzz import fuzz

from ..models import NewsEvent

DEFAULT_TAU_MINUTES = 30.0  # exponential decay half-life-ish


def corroboration_score(
    event: NewsEvent,
    recent: list[NewsEvent],
    *,
    similarity_cutoff: int = 70,
    window_minutes: int = 90,
    tau_minutes: float = DEFAULT_TAU_MINUTES,
) -> tuple[float, list[NewsEvent]]:
    """Return (score in [0, 1], list of corroborating events excluding self).

    Recency decay: each match contributes weight = exp(-Δt / tau). Old matches
    fade out before the hard window even cuts them off.
    """
    now = datetime.now(timezone.utc)
    cutoff_ts = now - timedelta(minutes=window_minutes)
    matches: list[NewsEvent] = []
    seen_handles: set[str] = {event.source_handle}

    weighted_distinct = 1.0  # self counts as 1.0
    for other in recent:
        if other.id == event.id:
            continue
        if other.fetched_at < cutoff_ts:
            continue
        if fuzz.token_set_ratio(other.text, event.text) < similarity_cutoff:
            continue
        if other.source_handle in seen_handles:
            continue
        seen_handles.add(other.source_handle)
        delta_min = max(0.0, (now - other.fetched_at).total_seconds() / 60.0)
        weight = math.exp(-delta_min / max(tau_minutes, 1e-6))
        weighted_distinct += weight * other.credibility
        matches.append(other)

    base_credibility = max([event.credibility, *[m.credibility for m in matches]], default=event.credibility)

    # Convert weighted_distinct (1..~5) into a boost capped at +0.45.
    # 1.0 = no corroboration -> 0 boost. 2.0 (one fresh full-credibility match) -> ~+0.20.
    # Diminishing returns above 3.0.
    extra = max(0.0, weighted_distinct - 1.0)
    boost = min(0.45, 0.20 * math.log1p(extra) + 0.10 * extra)

    return min(1.0, base_credibility + boost), matches
