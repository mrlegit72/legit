"""Telegram OSINT source.

Wraps Telethon's NewMessage event into NewsEvents pushed onto the shared queue.
Telethon import is deferred so missing creds don't crash the rest of the system.
"""
from __future__ import annotations

from datetime import timezone

from ..config import TelegramChannel, get_settings
from ..models import NewsEvent
from ..observability import get_logger
from .base import EventQueue, Source, stable_event_id

logger = get_logger(__name__)


class TelegramSource(Source):
    name = "telegram"

    def __init__(self, channels: list[TelegramChannel]) -> None:
        self.channels = channels
        self._cred_by_handle = {c.handle: c.credibility for c in channels}
        self._lang_by_handle = {c.handle: c.language for c in channels}

    async def run(self, queue: EventQueue) -> None:
        settings = get_settings()
        if not settings.telegram_api_id or not settings.telegram_api_hash:
            logger.warning("telegram_disabled", reason="missing TELEGRAM_API_ID/HASH")
            return
        if not self.channels:
            logger.info("telegram_no_channels")
            return

        from telethon import TelegramClient, events  # noqa: WPS433 (deferred)

        client = TelegramClient(
            settings.telegram_session_name,
            settings.telegram_api_id,
            settings.telegram_api_hash,
        )
        handles = [c.handle for c in self.channels]

        @client.on(events.NewMessage(chats=handles))
        async def _on_message(event):  # type: ignore[no-untyped-def]
            text = (event.message.message or "").strip()
            if not text:
                return
            chat = await event.get_chat()
            handle = getattr(chat, "username", None) or str(getattr(chat, "id", "unknown"))
            published = event.message.date
            if published and published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            news = NewsEvent(
                id=stable_event_id("telegram", handle, text, ts=str(event.message.id)),
                source_kind="telegram",
                source_handle=handle,
                credibility=self._cred_by_handle.get(handle, 0.4),
                language=self._lang_by_handle.get(handle, "en"),
                text=text,
                url=f"https://t.me/{handle}/{event.message.id}" if handle.isidentifier() else None,
                published_at=published,
            )
            await queue.put(news)
            logger.info("telegram_event", handle=handle, chars=len(text))

        await client.start()
        logger.info("telegram_started", channels=handles)
        await client.run_until_disconnected()
