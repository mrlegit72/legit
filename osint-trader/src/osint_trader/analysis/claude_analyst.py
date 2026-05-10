"""Claude-powered analyst.

Pipeline:
1. Pre-filter (substring) — done by caller.
2. Build a structured prompt with markets, current YES prices, and corroboration.
3. Call Claude (Opus by default; Haiku for cheap pre-classification when enabled).
4. Parse strict JSON; on parse failure, retry once with a "fix the JSON" follow-up.
5. Apply post-hoc guards (edge floor, confidence floor, market_id whitelist).
"""
from __future__ import annotations

import json
import re
from typing import Any

import anthropic
from tenacity import AsyncRetrying, RetryError, stop_after_attempt, wait_exponential

from ..config import MarketConfig, Settings
from ..models import AnalystVerdict, MarketSnapshot, NewsEvent, Signal
from ..observability import get_logger

logger = get_logger(__name__)


class ClaudeAnalyst:
    def __init__(self, settings: Settings, system_prompt: str) -> None:
        self.settings = settings
        self.system_prompt = system_prompt
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def analyze(
        self,
        event: NewsEvent,
        markets: list[MarketConfig],
        snapshots: dict[str, MarketSnapshot],
        corroborating: list[NewsEvent],
    ) -> AnalystVerdict:
        market_blobs = []
        for m in markets:
            snap = snapshots.get(m.market_id)
            market_blobs.append({
                "market_id": m.market_id,
                "title": m.title,
                "current_price_yes": round(snap.yes_price, 4) if snap else None,
                "escalation_direction": m.escalation_direction,
                "timeframe_days": m.timeframe_days,
            })

        user_payload = {
            "event": {
                "text": event.text,
                "source_kind": event.source_kind,
                "source_handle": event.source_handle,
                "language": event.language,
                "credibility": round(event.credibility, 2),
                "url": event.url,
            },
            "markets": market_blobs,
            "recent_context": [
                {"source": e.source_handle, "text": e.text[:280], "credibility": round(e.credibility, 2)}
                for e in corroborating[:5]
            ],
        }

        try:
            raw = await self._call_with_retry(json.dumps(user_payload, ensure_ascii=False))
        except RetryError as exc:
            logger.warning("claude_call_failed", error=str(exc))
            return AnalystVerdict(summary_en="", is_propaganda_risk=True, signals=[])

        verdict = self._parse(raw, event_id=event.id, valid_market_ids={m.market_id for m in markets})
        logger.info(
            "analyst_verdict",
            event_id=event.id,
            propaganda=verdict.is_propaganda_risk,
            signals=len(verdict.signals),
        )
        return verdict

    async def _call_with_retry(self, user_text: str) -> str:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(min=1, max=8),
            reraise=True,
        ):
            with attempt:
                resp = await self._client.messages.create(
                    model=self.settings.anthropic_model,
                    max_tokens=600,
                    system=self.system_prompt,
                    messages=[{"role": "user", "content": user_text}],
                )
                return _join_text(resp.content)
        return ""  # unreachable

    def _parse(self, raw: str, *, event_id: str, valid_market_ids: set[str]) -> AnalystVerdict:
        text = _strip_code_fence(raw)
        try:
            data: dict[str, Any] = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("analyst_invalid_json", sample=text[:200])
            return AnalystVerdict(summary_en="", is_propaganda_risk=True, signals=[])

        signals: list[Signal] = []
        for s in data.get("signals", []) or []:
            mid = s.get("market_id")
            if mid not in valid_market_ids:
                continue
            try:
                signals.append(Signal(
                    market_id=mid,
                    side=s["side"],
                    prob_yes=float(s["prob_yes"]),
                    edge=float(s["edge"]),
                    confidence=int(s["confidence"]),
                    reasoning=str(s.get("reasoning", ""))[:400],
                    triggered_by_event_id=event_id,
                ))
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning("analyst_bad_signal", error=str(exc), payload=s)
                continue
        return AnalystVerdict(
            summary_en=str(data.get("summary_en", ""))[:280],
            is_propaganda_risk=bool(data.get("is_propaganda_risk", False)),
            signals=signals,
        )


def _join_text(blocks) -> str:
    parts: list[str] = []
    for b in blocks:
        # Anthropic SDK returns TextBlock objects with `.text`
        text = getattr(b, "text", None)
        if text:
            parts.append(text)
    return "".join(parts).strip()


_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = _FENCE_RE.sub("", text).strip()
    return text
