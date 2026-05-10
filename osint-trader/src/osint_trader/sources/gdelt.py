"""GDELT 2.0 doc API source. No API key required.

We poll the GDELT DOC 2.0 API in JSON mode and translate each result into a
NewsEvent. Reference: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import httpx

from ..config import GDELTConfig
from ..models import NewsEvent
from ..observability import get_logger
from .base import EventQueue, Source, stable_event_id

logger = get_logger(__name__)

GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"


class GDELTSource(Source):
    name = "gdelt"

    def __init__(self, cfg: GDELTConfig) -> None:
        self.cfg = cfg

    async def run(self, queue: EventQueue) -> None:
        if not self.cfg.enabled or not self.cfg.query:
            logger.info("gdelt_disabled")
            return
        logger.info("gdelt_started", query=self.cfg.query, poll=self.cfg.poll_seconds)
        async with httpx.AsyncClient(timeout=20) as client:
            while True:
                try:
                    await self._poll(client, queue)
                except Exception as exc:
                    logger.warning("gdelt_poll_failed", error=str(exc))
                await asyncio.sleep(self.cfg.poll_seconds)

    async def _poll(self, client: httpx.AsyncClient, queue: EventQueue) -> None:
        params = {
            "query": self.cfg.query,
            "mode": "ArtList",
            "maxrecords": "25",
            "sort": "DateDesc",
            "format": "json",
            "timespan": "30min",
        }
        resp = await client.get(GDELT_DOC_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
        for art in data.get("articles", []):
            title = (art.get("title") or "").strip()
            if not title:
                continue
            url = art.get("url")
            seendate = art.get("seendate")  # YYYYMMDDTHHMMSSZ
            published = _parse_seendate(seendate)
            text = title
            if art.get("socialimage"):
                text += f"\n[image: {art['socialimage']}]"
            evt_id = stable_event_id("gdelt", art.get("domain", "gdelt"), text, ts=url or "")
            await queue.put(NewsEvent(
                id=evt_id,
                source_kind="gdelt",
                source_handle=art.get("domain", "gdelt"),
                credibility=self.cfg.credibility,
                language=art.get("language", "en"),
                text=text,
                url=url,
                published_at=published,
            ))


def _parse_seendate(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
