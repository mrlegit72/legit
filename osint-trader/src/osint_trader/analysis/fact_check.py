"""Optional second-pass fact-check for high-impact signals.

Two modes:
  * `corroboration_only`  (default): Haiku reads the original event plus
    1-5 corroborating items already in our queue. Cheap, fast, no external
    dependency. Good for catching pure-rumor signals.
  * `web_search`:  Haiku is given the Anthropic web_search tool and must
    cite at least one independent source published in the last 24h before
    returning verified=true. Adds latency + cost; turn on for high-edge
    claims only.

Mode is per-call: `verify(use_web_search=True)`.
"""
from __future__ import annotations

import json

import anthropic
from tenacity import AsyncRetrying, RetryError, stop_after_attempt, wait_exponential

from ..config import Settings
from ..models import NewsEvent, Signal
from ..observability import get_logger

logger = get_logger(__name__)

SYSTEM_BASIC = (
    "You are a fact-check filter. Given an event and 1-5 corroborating recent items, "
    "decide if the headline claim is independently supported. "
    "Return STRICT JSON: {\"verified\": <bool>, \"why\": \"<<=120 chars>\"}. "
    "Conservative bias: if only the original source carries the story, return false."
)

SYSTEM_WEB = (
    "You are a fact-check filter with a web_search tool. Use it once or twice "
    "to find independent confirmation of the claim from sources different "
    "from the original poster. Return STRICT JSON: "
    "{\"verified\": <bool>, \"why\": \"<<=160 chars, cite the corroborating source>\"}. "
    "If web_search returns nothing or only mirrors of the original claim, return false."
)


class FactChecker:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def verify(
        self,
        event: NewsEvent,
        signal: Signal,
        corroborating: list[NewsEvent],
        *,
        use_web_search: bool = False,
        edge_threshold_for_web: float = 0.15,
    ) -> tuple[bool, str]:
        # Cheap signals don't deserve a fact-check round trip.
        if abs(signal.edge) < 0.10:
            return True, "skipped_below_threshold"

        # Auto-promote to web_search for very-high-edge claims.
        web = use_web_search or abs(signal.edge) >= edge_threshold_for_web

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
            raw = await self._call(json.dumps(payload, ensure_ascii=False), web=web)
        except RetryError as exc:
            logger.warning("factcheck_failed", error=str(exc))
            return True, "factcheck_unavailable"
        try:
            data = json.loads(_strip_fence(raw))
            return bool(data.get("verified", False)), str(data.get("why", ""))[:200]
        except (json.JSONDecodeError, TypeError):
            return True, "factcheck_unparseable"

    async def _call(self, user_text: str, *, web: bool) -> str:
        system_text = SYSTEM_WEB if web else SYSTEM_BASIC
        tools = (
            [{"type": "web_search_20250305", "name": "web_search", "max_uses": 2}]
            if web else None
        )
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(2),
            wait=wait_exponential(min=1, max=4),
            reraise=True,
        ):
            with attempt:
                kwargs = dict(
                    model=self.settings.anthropic_fast_model,
                    max_tokens=400 if web else 200,
                    system=[{"type": "text", "text": system_text,
                             "cache_control": {"type": "ephemeral"}}],
                    messages=[{"role": "user", "content": user_text}],
                )
                if tools is not None:
                    kwargs["tools"] = tools
                resp = await self._client.messages.create(**kwargs)
                # Web-search responses interleave tool use with text; just
                # concatenate every text block.
                return "".join(getattr(b, "text", "") for b in resp.content).strip()
        return ""


def _strip_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return text.strip()
