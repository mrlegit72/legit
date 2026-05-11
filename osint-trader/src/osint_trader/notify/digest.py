"""Rolling-window alert collapser.

A burst of correlated headlines fires N signals in seconds; we don't want N
Telegram pings. The Digest holds queued alerts for `window_seconds` and emits
either a single message (if 1 alert) or a digest with the top-K reasons.

Used by TelegramAlerter when `digest_window_s > 0`.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Awaitable, Callable

from ..models import NewsEvent, Signal


@dataclass
class _Pending:
    event: NewsEvent
    signal: Signal
    summary: str
    actionable: bool
    skip_reason: str | None
    queued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AlertDigest:
    def __init__(
        self,
        send_text: Callable[[str], Awaitable[None]],
        window_seconds: float = 30.0,
        max_per_message: int = 5,
    ) -> None:
        self._send = send_text
        self.window_seconds = window_seconds
        self.max_per_message = max_per_message
        self._buffers: dict[str, list[_Pending]] = defaultdict(list)
        self._timers: dict[str, asyncio.TimerHandle] = {}

    def queue(
        self,
        event: NewsEvent,
        signal: Signal,
        summary: str,
        actionable: bool,
        skip_reason: str | None,
    ) -> None:
        key = signal.market_id
        self._buffers[key].append(_Pending(event, signal, summary, actionable, skip_reason))
        loop = asyncio.get_running_loop()
        if key not in self._timers:
            self._timers[key] = loop.call_later(
                self.window_seconds, lambda: asyncio.create_task(self._flush(key))
            )

    async def _flush(self, key: str) -> None:
        self._timers.pop(key, None)
        items = self._buffers.pop(key, [])
        if not items:
            return
        await self._send(self._render(key, items))

    def _render(self, market_id: str, items: list[_Pending]) -> str:
        if len(items) == 1:
            return _render_one(items[0])
        items_sorted = sorted(items, key=lambda i: i.signal.confidence, reverse=True)
        head = items_sorted[0]
        tier = "🔥" if head.signal.confidence >= 80 else "📡"
        lines = [
            f"{tier} *Digest*: {market_id}  ({len(items)} signals in {self.window_seconds:.0f}s)",
            f"top side: *{head.signal.side.upper()}*  prob_yes: `{head.signal.prob_yes:.2f}`  "
            f"edge: `{head.signal.edge:+.2f}`  conf: `{head.signal.confidence}`",
            "",
        ]
        for item in items_sorted[: self.max_per_message]:
            tag = "▶" if item.actionable else "•"
            why = item.signal.reasoning[:80].replace("\n", " ")
            lines.append(f"{tag} {item.event.source_handle}: {why}")
        if len(items_sorted) > self.max_per_message:
            lines.append(f"_(+{len(items_sorted) - self.max_per_message} more)_")
        return "\n".join(lines)

    async def aclose(self) -> None:
        for key in list(self._buffers):
            await self._flush(key)


def _render_one(p: _Pending) -> str:
    emoji = "🔥🔥" if p.signal.confidence >= 90 else "🔥" if p.signal.confidence >= 80 else "📡"
    flag = "" if p.actionable else f"  _(skipped: `{p.skip_reason}`)_"
    return (
        f"{emoji} *Signal*: {p.signal.market_id}{flag}\n"
        f"side: *{p.signal.side.upper()}*  prob_yes: `{p.signal.prob_yes:.2f}`  "
        f"edge: `{p.signal.edge:+.2f}`  conf: `{p.signal.confidence}`\n"
        f"\n_summary_: {p.summary or p.event.text[:140]}\n"
        f"_why_: {p.signal.reasoning}\n"
        f"_source_: {p.event.source_kind}/{p.event.source_handle}"
    )
