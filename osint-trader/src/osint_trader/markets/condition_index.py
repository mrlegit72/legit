"""Build the condition_id → market_id index used by the chain settlement reader.

Polymarket markets have:
  - slug              (URL-friendly, what we configure)
  - market_id         (our alias)
  - condition_id      (UMA / conditional tokens identifier — what payouts use)
  - clobTokenIds      (YES/NO ERC1155 token ids on Polygon)

The Gamma market response exposes `conditionId` for binary markets. We pull
that field at startup (and on snapshot refresh) and persist it so the
ChainSettlementReader can map an on-chain `PayoutRedemption` log back to
the market the signal originated from.
"""
from __future__ import annotations

import httpx
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential

from ..config import MarketConfig
from ..observability import get_logger
from ..persistence import Store

logger = get_logger(__name__)


async def hydrate_condition_index(
    store: Store, gamma_host: str, markets: list[MarketConfig],
) -> int:
    """Pull condition_id for every configured market and upsert into the index.

    Returns the number of rows upserted.
    """
    count = 0
    async with httpx.AsyncClient(timeout=15) as client:
        for m in markets:
            try:
                async for attempt in AsyncRetrying(
                    stop=stop_after_attempt(2),
                    wait=wait_exponential(min=1, max=3),
                    reraise=True,
                ):
                    with attempt:
                        resp = await client.get(
                            f"{gamma_host.rstrip('/')}/markets",
                            params={"slug": m.slug},
                        )
                        resp.raise_for_status()
                        data = resp.json()
            except Exception as exc:
                logger.warning("condition_index_fetch_failed", slug=m.slug, error=str(exc))
                continue
            items = data if isinstance(data, list) else data.get("data", [])
            if not items:
                continue
            item = items[0]
            condition_id = item.get("conditionId") or item.get("condition_id")
            if not condition_id:
                logger.info("condition_id_absent", slug=m.slug)
                continue
            token_ids = _decode_token_ids(item.get("clobTokenIds"))
            await store.upsert_condition(
                condition_id=str(condition_id),
                market_id=m.market_id,
                slug=m.slug,
                yes_token_id=token_ids[0] if len(token_ids) > 0 else None,
                no_token_id=token_ids[1] if len(token_ids) > 1 else None,
            )
            count += 1
    logger.info("condition_index_hydrated", rows=count, requested=len(markets))
    return count


def _decode_token_ids(val) -> list[str]:
    if val is None:
        return []
    if isinstance(val, list):
        return [str(x) for x in val]
    if isinstance(val, str):
        import json
        try:
            parsed = json.loads(val)
            return [str(x) for x in parsed] if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []
