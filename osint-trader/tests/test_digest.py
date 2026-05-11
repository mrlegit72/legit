import asyncio
from datetime import datetime, timezone

import pytest

from osint_trader.models import NewsEvent, Signal
from osint_trader.notify.digest import AlertDigest


def _evt(handle: str = "src") -> NewsEvent:
    return NewsEvent(
        id=f"e-{handle}", source_kind="rss", source_handle=handle,
        credibility=0.8, language="en", text="something happened",
        fetched_at=datetime.now(timezone.utc),
    )


def _sig(market: str = "m1") -> Signal:
    return Signal(
        market_id=market, side="yes", prob_yes=0.6, edge=0.1, confidence=85,
        reasoning="r", triggered_by_event_id="e-src",
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_single_signal_renders_normally():
    sent: list[str] = []

    async def send(text: str) -> None:
        sent.append(text)

    digest = AlertDigest(send_text=send, window_seconds=0.05)
    digest.queue(_evt(), _sig(), "summary", actionable=True, skip_reason=None)
    await asyncio.sleep(0.15)
    assert len(sent) == 1
    assert "*Signal*: m1" in sent[0]


@pytest.mark.asyncio
async def test_burst_collapses_into_digest():
    sent: list[str] = []

    async def send(text: str) -> None:
        sent.append(text)

    digest = AlertDigest(send_text=send, window_seconds=0.05)
    for h in ("a", "b", "c"):
        digest.queue(_evt(h), _sig(), "summary", actionable=True, skip_reason=None)
    await asyncio.sleep(0.15)
    assert len(sent) == 1
    assert "Digest" in sent[0]
    assert "3 signals" in sent[0]


@pytest.mark.asyncio
async def test_different_markets_get_separate_messages():
    sent: list[str] = []

    async def send(text: str) -> None:
        sent.append(text)

    digest = AlertDigest(send_text=send, window_seconds=0.05)
    digest.queue(_evt(), _sig("m1"), "", actionable=True, skip_reason=None)
    digest.queue(_evt(), _sig("m2"), "", actionable=True, skip_reason=None)
    await asyncio.sleep(0.15)
    assert len(sent) == 2
