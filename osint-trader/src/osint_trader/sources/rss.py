"""RSS source. Polls feeds, dedups by entry id/link/title."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Iterable

import feedparser

from ..config import RSSFeed
from ..models import NewsEvent
from ..observability import get_logger
from .base import EventQueue, Source, stable_event_id

logger = get_logger(__name__)


class RSSSource(Source):
    name = "rss"

    def __init__(self, feeds: list[RSSFeed], poll_seconds: int = 120) -> None:
        self.feeds = feeds
        self.poll_seconds = poll_seconds

    async def run(self, queue: EventQueue) -> None:
        if not self.feeds:
            logger.info("rss_no_feeds")
            return
        logger.info("rss_started", feeds=[f.url for f in self.feeds], poll=self.poll_seconds)
        while True:
            for feed in self.feeds:
                try:
                    await self._poll_one(feed, queue)
                except Exception as exc:  # network is flaky; keep going
                    logger.warning("rss_poll_failed", url=feed.url, error=str(exc))
            await asyncio.sleep(self.poll_seconds)

    async def _poll_one(self, feed: RSSFeed, queue: EventQueue) -> None:
        # feedparser is sync; run in thread to keep loop responsive.
        parsed = await asyncio.to_thread(feedparser.parse, feed.url)
        for entry in self._iter_entries(parsed):
            title = (entry.get("title") or "").strip()
            summary = (entry.get("summary") or entry.get("description") or "").strip()
            link = entry.get("link")
            if not title and not summary:
                continue
            text = f"{title}\n\n{summary}".strip()
            published = _parse_published(entry)
            evt_id = stable_event_id("rss", feed.url, text, ts=entry.get("id", link or ""))
            await queue.put(NewsEvent(
                id=evt_id,
                source_kind="rss",
                source_handle=feed.url,
                credibility=feed.credibility,
                language=feed.language,
                text=text,
                url=link,
                published_at=published,
            ))

    @staticmethod
    def _iter_entries(parsed) -> Iterable[dict]:
        return list(parsed.get("entries", []))[:25]


def _parse_published(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        st = entry.get(key)
        if st:
            try:
                return datetime(*st[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                pass
    return None
