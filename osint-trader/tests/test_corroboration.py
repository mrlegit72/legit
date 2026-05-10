from datetime import datetime, timedelta, timezone

from osint_trader.analysis import corroboration_score
from osint_trader.models import NewsEvent


def _evt(text: str, handle: str, credibility: float, minutes_ago: int = 0) -> NewsEvent:
    return NewsEvent(
        id=f"id-{handle}-{hash(text) & 0xFFFF:x}",
        source_kind="rss", source_handle=handle, credibility=credibility,
        language="en", text=text,
        fetched_at=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
    )


def test_single_source_returns_base_credibility():
    e = _evt("Israeli strike on Kharg oil terminal", "tasnim", 0.45)
    score, matches = corroboration_score(e, recent=[])
    assert score == 0.45
    assert matches == []


def test_two_distinct_sources_boost_score():
    target = _evt("Israeli strike on Kharg oil terminal", "amitsegal", 0.8, minutes_ago=2)
    other = _evt("BREAKING: Israel strikes Kharg Island oil terminal", "reuters", 0.92, minutes_ago=10)
    score, matches = corroboration_score(target, recent=[other])
    assert len(matches) == 1
    # Base 0.92 (best source) + 0.20 boost = 1.12 -> clamped to 1.0
    assert score == 1.0


def test_old_corroboration_excluded():
    target = _evt("Iran-US peace deal announced", "amitsegal", 0.8)
    stale = _evt("Iran and US announce peace deal", "reuters", 0.92, minutes_ago=600)
    score, matches = corroboration_score(target, recent=[stale])
    assert matches == []
    assert score == 0.8
