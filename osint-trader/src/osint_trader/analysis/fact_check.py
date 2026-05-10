"""Optional second-pass fact-check for high-impact signals.

For any signal whose absolute edge exceeds a threshold, we ask the cheaper
Haiku model to verify the underlying claim against the recent corroborating
sources. If it returns `verified=false`, we down-weight the signal.

This is intentionally lightweight: no external web calls (one extra model
call, again with prompt caching on the static instructions). Disable by
setting min_edge_to_verify above 1.0.
"""
from __future__ import annotations

import json

import anthropic
from tenacity import AsyncRetrying, RetryError, stop_after_attempt, wait_exponential

from ..config import Settings
from ..models import NewsEvent, Signal
from ..observability import get_logger

logger = get_logger(__name__)

SYSTEM = (
    "You are a fact-check filter. Given an event and 1-5 corroborating recent items, "
    "decide if the headline claim is independently supported. "
    "Return STRICT JSON: {\"verified\": <bool>, \"why\": \"<<=120 chars>\"}. "
    "Conservative bias: if only the original source carries the story, return false."
)


class FactChecker:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def verify(
        self, event: NewsEvent, signal: Signal, corroborating: list[NewsEvent]
    ) -> tuple[bool, str]:
        if abs(signal.edge) < 0.10:
            return True, "skipped_below_threshold"
        payload = {
            "event": {"source": event.source_handle, "credibility": event.credibility,
                      "text": event.text[:500]},
            "corroborating": [
                {"source": c.source_handle, "credibility": c.credibility, "text": c.text[:280]}
                for c in corroborating[:5]
            ],
            "claim_market": signal.market_id,
            "claim_side": signal.side,
        }
        try:
            raw = await self._call(json.dumps(payload, ensure_ascii=False))
        except RetryError as exc:
            logger.warning("factcheck_failed", error=str(exc))
            return True, "factcheck_unavailable"
        try:
            data = json.loads(_strip_fence(raw))
            return bool(data.get("verified", False)), str(data.get("why", ""))[:200]
        except (json.JSONDecodeError, TypeError):
            return True, "factcheck_unparseable"

    async def _call(self, user_text: str) -> str:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(2),
            wait=wait_exponential(min=1, max=4),
            reraise=True,
        ):
            with attempt:
                resp = await self._client.messages.create(
                    model=self.settings.anthropic_fast_model,
                    max_tokens=200,
                    system=[{"type": "text", "text": SYSTEM,
                             "cache_control": {"type": "ephemeral"}}],
                    messages=[{"role": "user", "content": user_text}],
                )
                return "".join(getattr(b, "text", "") for b in resp.content).strip()
        return ""


def _strip_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        # naive, good enough for our parser
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return text.strip()
