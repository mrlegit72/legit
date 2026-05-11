import os
import tempfile
from datetime import datetime, timezone

import pytest

from osint_trader.persistence import Store


@pytest.mark.asyncio
async def test_watermark_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        store = Store(os.path.join(d, "t.db"))
        await store.init()
        assert await store.get_watermark("tick") is None
        ts = datetime.now(timezone.utc).replace(microsecond=0)
        await store.set_watermark("tick", ts)
        assert await store.get_watermark("tick") == ts
        # overwrite
        ts2 = ts.replace(year=ts.year + 1)
        await store.set_watermark("tick", ts2)
        assert await store.get_watermark("tick") == ts2


@pytest.mark.asyncio
async def test_condition_index_upsert_and_lookup():
    with tempfile.TemporaryDirectory() as d:
        store = Store(os.path.join(d, "t.db"))
        await store.init()
        await store.upsert_condition(
            condition_id="0xabc", market_id="iranian-regime-fall",
            slug="will-the-iranian-regime-fall",
            yes_token_id="123", no_token_id="456",
        )
        assert await store.market_for_condition("0xabc") == (
            "iranian-regime-fall", "will-the-iranian-regime-fall",
        )
        # idempotent overwrite, no duplicate
        await store.upsert_condition(
            condition_id="0xabc", market_id="iranian-regime-fall",
            slug="will-the-iranian-regime-fall",
            yes_token_id="999", no_token_id="888",
        )
        assert await store.market_for_condition("0xabc") == (
            "iranian-regime-fall", "will-the-iranian-regime-fall",
        )
        assert await store.market_for_condition("0xunknown") is None
