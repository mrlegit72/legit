"""Anthropic Batch API analyst — 50% discount on Claude calls.

When events aren't time-critical (overnight backtests, daily replay,
GitHub Actions tick that's OK with 10-min lag), batching slashes inference
cost in half. The trade-off: results aren't realtime; the batch can take
up to 24h (usually completes in minutes).

Use directly:
    ba = BatchAnalyst(settings, system_prompt)
    job_id = await ba.submit([(event, markets, snapshots, corroborating), ...])
    results = await ba.poll_until_complete(job_id, max_wait_s=900)

The orchestrator's realtime path keeps using ClaudeAnalyst; this is opt-in.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import anthropic

from ..config import MarketConfig, Settings
from ..models import AnalystVerdict, MarketSnapshot, NewsEvent
from ..observability import get_logger

logger = get_logger(__name__)


class BatchAnalyst:
    def __init__(self, settings: Settings, system_prompt: str) -> None:
        self.settings = settings
        self.system_prompt = system_prompt
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def submit(
        self,
        triples: list[tuple[NewsEvent, list[MarketConfig], dict[str, MarketSnapshot], list[NewsEvent]]],
    ) -> str:
        requests = []
        for event, markets, snapshots, corroborating in triples:
            requests.append({
                "custom_id": f"{event.id}-{uuid.uuid4().hex[:8]}",
                "params": {
                    "model": self.settings.anthropic_model,
                    "max_tokens": 600,
                    "system": [{"type": "text", "text": self.system_prompt,
                                "cache_control": {"type": "ephemeral"}}],
                    "messages": [{"role": "user", "content": _build_payload(
                        event, markets, snapshots, corroborating,
                    )}],
                },
            })
        batch = await self._client.messages.batches.create(requests=requests)
        logger.info("batch_submitted", batch_id=batch.id, count=len(requests))
        return batch.id

    async def poll_until_complete(self, batch_id: str, *, max_wait_s: int = 900) -> dict[str, AnalystVerdict]:
        waited = 0
        while waited < max_wait_s:
            batch = await self._client.messages.batches.retrieve(batch_id)
            if batch.processing_status == "ended":
                break
            await asyncio.sleep(15)
            waited += 15
        else:
            logger.warning("batch_poll_timeout", batch_id=batch_id, waited=waited)
            return {}

        results: dict[str, AnalystVerdict] = {}
        async for entry in await self._client.messages.batches.results(batch_id):
            event_id = entry.custom_id.rsplit("-", 1)[0]
            res = entry.result
            if res.type != "succeeded":
                results[event_id] = AnalystVerdict(summary_en="", is_propaganda_risk=True, signals=[])
                continue
            text = "".join(getattr(b, "text", "") for b in res.message.content).strip()
            try:
                data = json.loads(_strip_fence(text))
            except json.JSONDecodeError:
                data = {}
            from .claude_analyst import _strip_code_fence  # noqa
            # Reuse the strict parser by faking the call site:
            try:
                from ..models import Signal
                signals = [
                    Signal(
                        market_id=s["market_id"], side=s["side"],
                        prob_yes=float(s["prob_yes"]), edge=float(s["edge"]),
                        confidence=int(s["confidence"]),
                        reasoning=str(s.get("reasoning", ""))[:400],
                        triggered_by_event_id=event_id,
                    )
                    for s in data.get("signals", []) or []
                ]
            except (KeyError, TypeError, ValueError):
                signals = []
            results[event_id] = AnalystVerdict(
                summary_en=str(data.get("summary_en", ""))[:280],
                is_propaganda_risk=bool(data.get("is_propaganda_risk", False)),
                signals=signals,
            )
        return results


def _build_payload(
    event: NewsEvent, markets: list[MarketConfig],
    snapshots: dict[str, MarketSnapshot], corroborating: list[NewsEvent],
) -> list[dict[str, Any]]:
    market_blobs = []
    for m in markets:
        snap = snapshots.get(m.market_id)
        market_blobs.append({
            "market_id": m.market_id, "title": m.title,
            "current_price_yes": round(snap.yes_price, 4) if snap else None,
            "escalation_direction": m.escalation_direction,
            "timeframe_days": m.timeframe_days,
        })
    return [
        {"type": "text",
         "text": "MARKETS:\n" + json.dumps(market_blobs, ensure_ascii=False),
         "cache_control": {"type": "ephemeral"}},
        {"type": "text",
         "text": "EVENT:\n" + json.dumps({
             "event": {"text": event.text, "source_kind": event.source_kind,
                       "source_handle": event.source_handle, "language": event.language,
                       "credibility": round(event.credibility, 2), "url": event.url},
             "recent_context": [
                 {"source": c.source_handle, "text": c.text[:280],
                  "credibility": round(c.credibility, 2)}
                 for c in corroborating[:5]
             ],
         }, ensure_ascii=False)},
    ]


def _strip_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return text.strip()
