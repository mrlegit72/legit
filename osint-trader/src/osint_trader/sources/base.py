"""Source base class + shared event queue."""
from __future__ import annotations

import asyncio
import hashlib
from abc import ABC, abstractmethod

from ..models import NewsEvent


def stable_event_id(source_kind: str, source_handle: str, text: str, ts: str = "") -> str:
    """Hash that's stable across restarts so duplicates collapse."""
    h = hashlib.sha256()
    h.update(source_kind.encode())
    h.update(b"|")
    h.update(source_handle.encode())
    h.update(b"|")
    h.update(text.strip().encode())
    if ts:
        h.update(b"|")
        h.update(ts.encode())
    return h.hexdigest()[:32]


EventQueue = asyncio.Queue["NewsEvent"]


class Source(ABC):
    name: str = "base"

    @abstractmethod
    async def run(self, queue: EventQueue) -> None:
        """Long-running task that pushes NewsEvents into the queue."""
