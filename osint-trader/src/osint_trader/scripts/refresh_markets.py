"""One-shot helper: fetch live snapshots for every configured market.

Useful for sanity-checking your slugs and seeing live YES/NO prices in the
terminal before running the full bot.
"""
from __future__ import annotations

import asyncio

from rich.console import Console
from rich.table import Table

from ..config import get_settings, load_markets
from ..markets import PolymarketClient

console = Console()


async def run() -> None:
    settings = get_settings()
    markets = load_markets()
    poly = PolymarketClient(settings)
    snapshots = await poly.refresh_snapshots(markets)

    table = Table(title="Polymarket snapshots")
    for col in ("market_id", "slug", "yes", "no", "liq", "vol24h"):
        table.add_column(col)
    for m in markets:
        snap = snapshots.get(m.market_id)
        if snap is None:
            table.add_row(m.market_id, m.slug, "-", "-", "-", "-")
            continue
        table.add_row(
            m.market_id, m.slug,
            f"{snap.yes_price:.3f}", f"{snap.no_price:.3f}",
            f"${snap.liquidity_usdc:,.0f}", f"${snap.volume_24h_usdc:,.0f}",
        )
    console.print(table)
    await poly.aclose()


def cli() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    cli()
