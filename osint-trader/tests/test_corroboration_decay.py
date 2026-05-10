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


def test_recent_corroboration_outscores_old_corroboration():
    target = _evt("Israeli strike on Kharg oil terminal", "amitsegal", 0.8, minutes_ago=2)
    fresh = _evt("BREAKING: Israel strikes Kharg Island oil terminal", "reuters", 0.92, minutes_ago=5)
    stale = _evt("BREAKING: Israel strikes Kharg Island oil terminal", "reuters", 0.92, minutes_ago=70)
    fresh_score, _ = corroboration_score(target, recent=[fresh])
    stale_score, _ = corroboration_score(target, recent=[stale])
    assert fresh_score > stale_score


def test_three_distinct_sources_boost_more_than_two():
    target = _evt("Iran cuts off Hormuz traffic", "amitsegal", 0.8, minutes_ago=2)
    a = _evt("Iran halts Hormuz traffic - Reuters", "reuters", 0.92, minutes_ago=4)
    b = _evt("Hormuz traffic blocked by Iran", "bbc", 0.90, minutes_ago=6)
    two_score, _ = corroboration_score(target, recent=[a])
    three_score, _ = corroboration_score(target, recent=[a, b])
    assert three_score >= two_score
