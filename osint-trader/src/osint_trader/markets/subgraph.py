"""Polymarket subgraph + Gamma history client for backtesting.

We use two endpoints:
  * Gamma `/markets-history?market=<condition_id>&interval=...` for time-series
    YES prices on a market.
  * Gamma `/markets/<id>/trades` (or the trades subgraph) for fill volumes.

The functions here return plain dicts/lists; the backtest harness converts
those into NewsEvent + snapshot replay frames.

Network failures return empty lists so the backtest can fall back to its
in-line synthetic snapshots from the JSONL file.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential

from ..observability import get_logger

logger = get_logger(__name__)


@dataclass
class PriceTick:
    timestamp: datetime
    yes_price: float


async def fetch_price_history(
    gamma_host: str,
    market_id: str,
    *,
    interval: str = "1h",
    fidelity_minutes: int = 60,
) -> list[PriceTick]:
    """Best-effort fetch of YES price ticks for a market id (Gamma's market id)."""
    url = f"{gamma_host.rstrip('/')}/markets-history"
    params = {"market": market_id, "interval": interval, "fidelity": fidelity_minutes}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(2),
                wait=wait_exponential(min=1, max=3),
                reraise=True,
            ):
                with attempt:
                    resp = await client.get(url, params=params)
                    resp.raise_for_status()
                    data = resp.json()
    except Exception as exc:
        logger.warning("subgraph_history_failed", market=market_id, error=str(exc))
        return []

    history = data.get("history", []) if isinstance(data, dict) else data
    out: list[PriceTick] = []
    for row in history:
        ts = row.get("t")
        price = row.get("p")
        if ts is None or price is None:
            continue
        try:
            out.append(PriceTick(
                timestamp=datetime.fromtimestamp(int(ts), tz=timezone.utc),
                yes_price=float(price),
            ))
        except (TypeError, ValueError):
            continue
    return out


async def price_at(
    gamma_host: str, market_id: str, target: datetime, *, fidelity_minutes: int = 60,
) -> float | None:
    """Best-effort YES price at (or just after) a target datetime.

    Used by the backtest to compute mark-to-market exits at `event_ts +
    holding_period` rather than only at final resolution.
    """
    history = await fetch_price_history(gamma_host, market_id, fidelity_minutes=fidelity_minutes)
    if not history:
        return None
    after = [t for t in history if t.timestamp >= target]
    chosen = after[0] if after else history[-1]
    return chosen.yes_price


async def fetch_resolution(gamma_host: str, slug: str) -> int | None:
    """Return the binary YES/NO resolution if the market has resolved, else None."""
    url = f"{gamma_host.rstrip('/')}/markets"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params={"slug": slug})
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("subgraph_resolution_failed", slug=slug, error=str(exc))
        return None
    items = data if isinstance(data, list) else data.get("data", [])
    if not items:
        return None
    item = items[0]
    if not item.get("closed"):
        return None
    # Gamma encodes outcome arrays as JSON strings sometimes.
    outcome_prices = item.get("outcomePrices")
    if isinstance(outcome_prices, str):
        import json
        try:
            outcome_prices = json.loads(outcome_prices)
        except json.JSONDecodeError:
            outcome_prices = []
    if not outcome_prices:
        return None
    yes = float(outcome_prices[0])
    return 1 if yes >= 0.5 else 0
