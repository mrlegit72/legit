"""Polymarket client.

Read path: Gamma API (no auth) returns live market metadata + prices, plus the
CLOB /book endpoint for depth. Write path: py-clob-client (optional, only
loaded in live mode).

Hardening:
- Pydantic-validated GammaMarket so silent schema drift loudly fails one market
  instead of quietly trading at price 0.5.
- Status filter: only `acceptingOrders` non-archived non-closed markets pass.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential

from ..config import MarketConfig, Settings
from ..models import MarketSnapshot, TradeIntent, TradeResult
from ..observability import get_logger
from .orderbook import OrderBook, fetch_book

logger = get_logger(__name__)


class GammaMarket(BaseModel):
    """Strict subset of the Gamma /markets response we depend on."""
    slug: str
    closed: bool = False
    archived: bool = False
    accepting_orders: bool = Field(True, alias="acceptingOrders")
    outcome_prices: list[float] = Field(default_factory=list, alias="outcomePrices")
    clob_token_ids: list[str] = Field(default_factory=list, alias="clobTokenIds")
    liquidity: float = 0.0
    volume24hr: float = 0.0

    model_config = {"populate_by_name": True, "extra": "ignore"}

    @field_validator("outcome_prices", mode="before")
    @classmethod
    def _decode_prices(cls, v: Any) -> Any:
        return _decode_json_list_floats(v)

    @field_validator("clob_token_ids", mode="before")
    @classmethod
    def _decode_tokens(cls, v: Any) -> Any:
        return _decode_json_list_strs(v)

    @field_validator("liquidity", "volume24hr", mode="before")
    @classmethod
    def _safe_float(cls, v: Any) -> float:
        try:
            return float(v) if v is not None else 0.0
        except (TypeError, ValueError):
            return 0.0


class PolymarketClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._gamma = settings.polymarket_gamma_host.rstrip("/")
        self._clob = settings.polymarket_clob_host.rstrip("/")
        self._http = httpx.AsyncClient(timeout=15)
        self._snapshots: dict[str, MarketSnapshot] = {}
        self._inactive: set[str] = set()
        self._last_validation_failure: dict[str, str] = {}
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

    def is_inactive(self, market_id: str) -> bool:
        return market_id in self._inactive

    def last_validation_failures(self) -> dict[str, str]:
        return dict(self._last_validation_failure)

    async def fetch_orderbook(self, token_id: str) -> OrderBook | None:
        try:
            return await fetch_book(self._http, self._clob, token_id)
        except Exception as exc:
            logger.warning("orderbook_fetch_failed", token=token_id, error=str(exc))
            return None

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
            self._inactive.add(market.market_id)
            return None
        try:
            gm = GammaMarket.model_validate(items[0])
        except ValidationError as exc:
            self._last_validation_failure[market.market_id] = str(exc)
            logger.warning("market_validation_failed", slug=market.slug, error=str(exc))
            return None
        self._last_validation_failure.pop(market.market_id, None)

        if gm.closed or gm.archived or not gm.accepting_orders:
            self._inactive.add(market.market_id)
            logger.info("market_inactive", slug=market.slug,
                        closed=gm.closed, archived=gm.archived,
                        accepting=gm.accepting_orders)
            return None
        self._inactive.discard(market.market_id)

        prices = gm.outcome_prices
        token_ids = gm.clob_token_ids
        yes_price = prices[0] if len(prices) > 0 else 0.5
        no_price = prices[1] if len(prices) > 1 else round(1 - yes_price, 4)
        return MarketSnapshot(
            market_id=market.market_id,
            slug=market.slug,
            title=market.title,
            yes_price=yes_price,
            no_price=no_price,
            liquidity_usdc=gm.liquidity,
            volume_24h_usdc=gm.volume24hr,
            yes_token_id=token_ids[0] if len(token_ids) > 0 else None,
            no_token_id=token_ids[1] if len(token_ids) > 1 else None,
        )

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

    async def cancel_order(self, order_id: str) -> bool:
        if self.settings.trade_mode.value != "live" or not order_id:
            return True
        try:
            return await asyncio.to_thread(self._cancel_live, order_id)
        except Exception:
            logger.exception("cancel_failed", order=order_id)
            return False

    def _cancel_live(self, order_id: str) -> bool:
        from py_clob_client.client import ClobClient
        client = ClobClient(
            host=self._clob,
            key=self.settings.polymarket_private_key,
            chain_id=137,
            funder=self.settings.polymarket_funder,
            signature_type=2,
        )
        client.set_api_creds(client.create_or_derive_api_creds())
        return bool(client.cancel(order_id))


def _decode_json_list_floats(val: Any) -> list[float]:
    decoded = _decode_list(val)
    out = []
    for item in decoded:
        try:
            out.append(float(item))
        except (TypeError, ValueError):
            continue
    return out


def _decode_json_list_strs(val: Any) -> list[str]:
    return [str(x) for x in _decode_list(val)]


def _decode_list(val: Any) -> list:
    if val is None:
        return []
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []
