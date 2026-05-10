"""Polymarket client.

Read path: Gamma API (no auth) returns live market metadata + prices.
Write path: py-clob-client (optional, only loaded in live mode).
"""
from __future__ import annotations

import asyncio
from typing import Any

import httpx
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential

from ..config import MarketConfig, Settings
from ..models import MarketSnapshot, TradeIntent, TradeResult
from ..observability import get_logger

logger = get_logger(__name__)


class PolymarketClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._gamma = settings.polymarket_gamma_host.rstrip("/")
        self._clob = settings.polymarket_clob_host.rstrip("/")
        self._http = httpx.AsyncClient(timeout=15)
        self._snapshots: dict[str, MarketSnapshot] = {}
        self._lock = asyncio.Lock()

    async def aclose(self) -> None:
        await self._http.aclose()

    # ---------- read ----------

    async def refresh_snapshots(self, markets: list[MarketConfig]) -> dict[str, MarketSnapshot]:
        async with self._lock:
            tasks = [self._fetch_one(m) for m in markets]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for m, res in zip(markets, results):
                if isinstance(res, Exception):
                    logger.warning("market_fetch_failed", slug=m.slug, error=str(res))
                    continue
                if res is not None:
                    self._snapshots[m.market_id] = res
        return dict(self._snapshots)

    def get_snapshot(self, market_id: str) -> MarketSnapshot | None:
        return self._snapshots.get(market_id)

    async def _fetch_one(self, market: MarketConfig) -> MarketSnapshot | None:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(min=1, max=4),
            reraise=True,
        ):
            with attempt:
                resp = await self._http.get(
                    f"{self._gamma}/markets",
                    params={"slug": market.slug},
                )
                resp.raise_for_status()
                data = resp.json()
        items = data if isinstance(data, list) else data.get("data", [])
        if not items:
            logger.info("market_not_found", slug=market.slug)
            return None
        m = items[0]
        return _gamma_to_snapshot(market, m)

    # ---------- write ----------

    async def place_order(self, intent: TradeIntent) -> TradeResult:
        if self.settings.trade_mode.value == "dry_run":
            logger.info("dry_run_order", market=intent.market_id, side=intent.side, size=intent.size_usdc)
            return TradeResult(intent=intent, status="dry_run")

        if self.settings.trade_mode.value == "paper":
            return TradeResult(
                intent=intent,
                status="filled",
                fill_price=intent.price,
                filled_size_usdc=intent.size_usdc,
                order_id=f"paper-{intent.created_at.isoformat()}",
            )

        # live
        if not self.settings.polymarket_private_key or not self.settings.polymarket_funder:
            return TradeResult(intent=intent, status="error",
                               error="POLYMARKET_PRIVATE_KEY or POLYMARKET_FUNDER missing")
        if not intent.token_id:
            return TradeResult(intent=intent, status="error", error="missing token_id")
        try:
            return await asyncio.to_thread(self._place_live, intent)
        except Exception as exc:
            logger.exception("polymarket_live_order_failed")
            return TradeResult(intent=intent, status="error", error=str(exc))

    def _place_live(self, intent: TradeIntent) -> TradeResult:
        # Optional dependency, only required for live mode.
        from py_clob_client.client import ClobClient
        from py_clob_client.clob_types import OrderArgs
        from py_clob_client.order_builder.constants import BUY

        client = ClobClient(
            host=self._clob,
            key=self.settings.polymarket_private_key,
            chain_id=137,
            funder=self.settings.polymarket_funder,
            signature_type=2,
        )
        client.set_api_creds(client.create_or_derive_api_creds())
        # On Polymarket, "buy NO" means buy the NO outcome token.
        order_args = OrderArgs(
            price=intent.price,
            size=intent.size_usdc / max(intent.price, 0.01),
            side=BUY,
            token_id=intent.token_id,
        )
        signed = client.create_order(order_args)
        resp = client.post_order(signed)
        return TradeResult(
            intent=intent,
            status="filled" if resp.get("success") else "rejected",
            order_id=str(resp.get("orderID") or resp.get("orderId") or ""),
            fill_price=intent.price,
            filled_size_usdc=intent.size_usdc if resp.get("success") else 0.0,
            error=None if resp.get("success") else str(resp),
        )


def _gamma_to_snapshot(cfg: MarketConfig, m: dict[str, Any]) -> MarketSnapshot:
    """Map a Gamma market response to our domain.

    Gamma returns `outcomePrices` / `clobTokenIds` as JSON-encoded strings of
    arrays for binary markets (index 0 = YES, 1 = NO).
    """
    prices = _maybe_json_list(m.get("outcomePrices"))
    token_ids = _maybe_json_list(m.get("clobTokenIds"))
    yes_price = _safe_float(prices[0]) if len(prices) > 0 else 0.5
    no_price = _safe_float(prices[1]) if len(prices) > 1 else round(1 - yes_price, 4)
    return MarketSnapshot(
        market_id=cfg.market_id,
        slug=cfg.slug,
        title=cfg.title,
        yes_price=yes_price,
        no_price=no_price,
        liquidity_usdc=_safe_float(m.get("liquidity")),
        volume_24h_usdc=_safe_float(m.get("volume24hr") or m.get("volume24Hr") or 0),
        yes_token_id=str(token_ids[0]) if len(token_ids) > 0 else None,
        no_token_id=str(token_ids[1]) if len(token_ids) > 1 else None,
    )


def _maybe_json_list(val: Any) -> list:
    if val is None:
        return []
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        import json as _json
        try:
            parsed = _json.loads(val)
            return parsed if isinstance(parsed, list) else []
        except _json.JSONDecodeError:
            return []
    return []


def _safe_float(val: Any, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default
