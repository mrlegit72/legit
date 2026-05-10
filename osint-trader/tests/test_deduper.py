from datetime import datetime, timezone

from osint_trader.analysis.deduper import Deduper
from osint_trader.models import NewsEvent


def _evt(text: str, idx: int = 0) -> NewsEvent:
    return NewsEvent(
        id=f"id-{idx}-{hash(text) & 0xFFFFFFFF:x}",
        source_kind="rss",
        source_handle="example.com",
        credibility=0.5,
        language="en",
        text=text,
        fetched_at=datetime.now(timezone.utc),
    )


def test_exact_id_dedup():
    d = Deduper()
    e = _evt("Israeli strike on Kharg oil terminal", 1)
    assert not d.is_duplicate(e)
    d.remember(e)
    assert d.is_duplicate(e)


def test_fuzzy_dedup_catches_paraphrase():
    d = Deduper(similarity_cutoff=80)
    a = _evt("Reuters: Israeli strike hits Kharg Island oil terminal", 1)
    b = _evt("BREAKING: Israel strikes Kharg Island oil terminal, Reuters reports", 2)
    d.remember(a)
    assert d.is_duplicate(b)


def test_distinct_events_not_deduped():
    d = Deduper()
    a = _evt("Iran and Saudi Arabia announce new diplomatic protocol", 1)
    b = _evt("Trump announces end of military operations against Iran", 2)
    d.remember(a)
    assert not d.is_duplicate(b)
