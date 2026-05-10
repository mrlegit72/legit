import os
import tempfile
from datetime import datetime, timezone

import pytest

from osint_trader.models import NewsEvent
from osint_trader.persistence import Store


@pytest.mark.asyncio
async def test_event_dedup_via_store():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "test.db")
        store = Store(path)
        await store.init()
        e = NewsEvent(
            id="abc123",
            source_kind="rss",
            source_handle="reuters",
            credibility=0.9,
            language="en",
            text="Iran reports something",
            fetched_at=datetime.now(timezone.utc),
        )
        assert await store.save_event(e) is True
        assert await store.save_event(e) is False  # dup
        events = await store.recent_events(since_minutes=10)
        assert any(x.id == "abc123" for x in events)
