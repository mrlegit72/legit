"""Two-layer dedup.

1. Exact id (hash) — collapses retransmits.
2. Fuzzy near-duplicate (rapidfuzz token_set_ratio) — collapses paraphrases &
   cross-channel re-postings within a sliding window.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta, timezone

from rapidfuzz import fuzz

from ..models import NewsEvent


class Deduper:
    def __init__(self, window_minutes: int = 90, similarity_cutoff: int = 88) -> None:
        self.window = timedelta(minutes=window_minutes)
        self.cutoff = similarity_cutoff
        self._recent: deque[tuple[datetime, str, str]] = deque()  # (ts, id, text)

    def is_duplicate(self, event: NewsEvent) -> bool:
        self._evict()
        for _, eid, text in self._recent:
            if eid == event.id:
                return True
            if fuzz.token_set_ratio(text, event.text) >= self.cutoff:
                return True
        return False

    def remember(self, event: NewsEvent) -> None:
        self._recent.append((datetime.now(timezone.utc), event.id, event.text))

    def _evict(self) -> None:
        cutoff = datetime.now(timezone.utc) - self.window
        while self._recent and self._recent[0][0] < cutoff:
            self._recent.popleft()
