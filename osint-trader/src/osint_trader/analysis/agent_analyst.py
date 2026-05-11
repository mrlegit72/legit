"""Claude Agent SDK wrapper around the analyst.

Wraps the analysis pipeline as an Agent SDK agent so Claude can call tools
to fetch:
  - the live Polymarket snapshot for any market in the list
  - corroborating items from our local SQLite store
  - the order book for either side of a market

This is a richer alternative to the single-shot ClaudeAnalyst when you want
the model to investigate (e.g., "is the headline on Tasnim actually backed
by Reuters in the last hour?").

The SDK is optional (`pip install -e ".[agent]"`); without it, callers fall
back to ClaudeAnalyst.

Reference: https://docs.anthropic.com/en/api/agent-sdk
"""
from __future__ import annotations

import json
from typing import Any

from ..config import MarketConfig, Settings
from ..models import AnalystVerdict, MarketSnapshot, NewsEvent
from ..observability import get_logger
from ..persistence import Store
from ..markets import PolymarketClient

logger = get_logger(__name__)


SYSTEM = (
    "You are an OSINT analyst trading on Polymarket. You may call tools to "
    "fetch corroborating news, live market prices, and the order book before "
    "deciding. Your final answer must be STRICT JSON matching this schema: "
    "{\"summary_en\":\"...\",\"is_propaganda_risk\":bool,\"signals\":[{...}]}"
)


class AgentAnalyst:
    def __init__(self, settings: Settings, system_prompt: str, store: Store, poly: PolymarketClient) -> None:
        self.settings = settings
        self.system_prompt = f"{SYSTEM}\n\n{system_prompt}"
        self.store = store
        self.poly = poly

    async def analyze(
        self,
        event: NewsEvent,
        markets: list[MarketConfig],
        snapshots: dict[str, MarketSnapshot],
        corroborating: list[NewsEvent],
    ) -> AnalystVerdict:
        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            raise RuntimeError("anthropic SDK missing")

        client = AsyncAnthropic(api_key=self.settings.anthropic_api_key)

        tools = [
            {
                "name": "get_corroboration",
                "description": "Return recent events from our store that resemble the given query text.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query_text": {"type": "string"},
                        "minutes_back": {"type": "integer", "default": 360},
                    },
                    "required": ["query_text"],
                },
            },
            {
                "name": "get_orderbook",
                "description": "Return the top-5 levels of the Polymarket CLOB book for a market+side.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "market_id": {"type": "string"},
                        "side": {"type": "string", "enum": ["yes", "no"]},
                    },
                    "required": ["market_id", "side"],
                },
            },
        ]

        messages: list[dict[str, Any]] = [{
            "role": "user",
            "content": json.dumps({
                "event": {"text": event.text, "source": event.source_handle,
                          "credibility": round(event.credibility, 2)},
                "markets": [{"id": m.market_id, "title": m.title,
                             "current_yes": snapshots.get(m.market_id).yes_price
                             if snapshots.get(m.market_id) else None}
                            for m in markets],
                "preloaded_context": [
                    {"source": c.source_handle, "text": c.text[:240]}
                    for c in corroborating[:3]
                ],
            }, ensure_ascii=False),
        }]

        for _ in range(4):  # at most 4 tool-use turns
            resp = await client.messages.create(
                model=self.settings.anthropic_model,
                max_tokens=1500,
                system=[{"type": "text", "text": self.system_prompt,
                         "cache_control": {"type": "ephemeral"}}],
                tools=tools,
                messages=messages,
            )
            if resp.stop_reason == "end_turn":
                text = "".join(getattr(b, "text", "") for b in resp.content).strip()
                return _parse_strict(text, event.id, {m.market_id for m in markets})
            # Otherwise process tool calls.
            messages.append({"role": "assistant", "content": resp.content})
            tool_results = []
            for block in resp.content:
                if getattr(block, "type", None) != "tool_use":
                    continue
                output = await self._dispatch_tool(block.name, block.input, markets, snapshots)
                tool_results.append({
                    "type": "tool_result", "tool_use_id": block.id, "content": output,
                })
            if not tool_results:
                break
            messages.append({"role": "user", "content": tool_results})
        return AnalystVerdict(summary_en="", is_propaganda_risk=True, signals=[])

    async def _dispatch_tool(
        self, name: str, params: dict, markets: list[MarketConfig],
        snapshots: dict[str, MarketSnapshot],
    ) -> str:
        if name == "get_corroboration":
            minutes = int(params.get("minutes_back", 360))
            recent = await self.store.recent_events(since_minutes=minutes, limit=30)
            from rapidfuzz import fuzz
            query = str(params["query_text"])
            hits = [
                {"source": e.source_handle, "credibility": round(e.credibility, 2),
                 "text": e.text[:240]}
                for e in recent
                if fuzz.token_set_ratio(e.text, query) >= 60
            ][:5]
            return json.dumps(hits)
        if name == "get_orderbook":
            mid = params["market_id"]
            snap = snapshots.get(mid)
            if snap is None:
                return "[]"
            token_id = snap.yes_token_id if params["side"] == "yes" else snap.no_token_id
            book = await self.poly.fetch_orderbook(token_id) if token_id else None
            if book is None:
                return "[]"
            return json.dumps({
                "asks": [{"price": l.price, "size": l.size_shares} for l in book.asks[:5]],
                "bids": [{"price": l.price, "size": l.size_shares} for l in book.bids[:5]],
            })
        return ""


def _parse_strict(text: str, event_id: str, valid_market_ids: set[str]) -> AnalystVerdict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return AnalystVerdict(summary_en="", is_propaganda_risk=True, signals=[])
    from ..models import Signal
    sigs = []
    for s in data.get("signals", []) or []:
        if s.get("market_id") not in valid_market_ids:
            continue
        try:
            sigs.append(Signal(
                market_id=s["market_id"], side=s["side"],
                prob_yes=float(s["prob_yes"]), edge=float(s["edge"]),
                confidence=int(s["confidence"]),
                reasoning=str(s.get("reasoning", ""))[:400],
                triggered_by_event_id=event_id,
            ))
        except (KeyError, TypeError, ValueError):
            continue
    return AnalystVerdict(
        summary_en=str(data.get("summary_en", ""))[:280],
        is_propaganda_risk=bool(data.get("is_propaganda_risk", False)),
        signals=sigs,
    )
