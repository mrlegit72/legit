"""Cross-source corroboration scoring.

Idea: a single tweet from a pro-regime channel claiming "Israeli strike on
Kharg" is almost worthless. The same claim across Reuters + amitsegal + GDELT
within a short window is highly actionable.

We combine:
- credibility (max source weight) — anchors trust.
- corroboration count — number of distinct sources reporting near-duplicates.
- recency — older corroboration in the window counts less.

Output: 0..1 multiplier applied to the analyst confidence at decision time.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from rapidfuzz import fuzz

from ..models import NewsEvent


def corroboration_score(
    event: NewsEvent,
    recent: list[NewsEvent],
    *,
    similarity_cutoff: int = 70,
    window_minutes: int = 90,
) -> tuple[float, list[NewsEvent]]:
    """Return (score in [0, 1], list of corroborating events excluding self)."""
    cutoff_ts = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    matches: list[NewsEvent] = []
    seen_handles: set[str] = {event.source_handle}

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
        matches.append(other)

    # Distinct sources (incl. self), capped at 4 to avoid overweighting flood.
    distinct = min(1 + len(matches), 4)
    base_credibility = max([event.credibility, *[m.credibility for m in matches]], default=event.credibility)
    # 1 source: take its credibility. 2 sources: +20%. 3: +35%. 4: +45%.
    boost = {1: 0.0, 2: 0.20, 3: 0.35, 4: 0.45}[distinct]
    return min(1.0, base_credibility + boost), matches
