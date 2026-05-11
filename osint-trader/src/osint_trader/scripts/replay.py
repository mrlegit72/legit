"""Replay a stored event through the current analyst + risk pipeline.

Use this when something in production looks wrong: pick the event id from
SQLite or the dashboard and ask "what would today's prompt have done?".

    osint-replay --event-id abc123def456
    osint-replay --since 2h --market iranian-regime-fall

Output prints the analyst verdict + each signal's would-be sizing decision.
Nothing is persisted; nothing is traded.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone

import aiosqlite
from rich.console import Console
from rich.table import Table

from ..analysis import ClaudeAnalyst, corroboration_score
from ..config import CONFIG_DIR, get_settings, load_analyst_prompt, load_markets
from ..markets import PolymarketClient
from ..models import NewsEvent
from ..risk import Bankroll, CircuitBreaker, size_trade
from ..risk.cooldown import CooldownTracker
from ..risk.scenarios import ScenarioRegistry

console = Console()


async def _load_events(
    db_path: str, *, event_id: str | None, since: timedelta | None, market: str | None
) -> list[NewsEvent]:
    out: list[NewsEvent] = []
    async with aiosqlite.connect(db_path) as db:
        if event_id:
            query = ("SELECT id, source_kind, source_handle, credibility, language, "
                     "text, url, fetched_at, published_at FROM events WHERE id = ?")
            params: tuple = (event_id,)
        else:
            cutoff = (datetime.now(timezone.utc) - (since or timedelta(hours=1))).isoformat()
            if market:
                query = ("SELECT e.id, e.source_kind, e.source_handle, e.credibility, e.language, "
                         "e.text, e.url, e.fetched_at, e.published_at "
                         "FROM events e JOIN signals s ON s.triggered_by_event_id = e.id "
                         "WHERE s.market_id = ? AND e.fetched_at >= ? "
                         "GROUP BY e.id ORDER BY e.fetched_at DESC LIMIT 20")
                params = (market, cutoff)
            else:
                query = ("SELECT id, source_kind, source_handle, credibility, language, "
                         "text, url, fetched_at, published_at FROM events "
                         "WHERE fetched_at >= ? ORDER BY fetched_at DESC LIMIT 20")
                params = (cutoff,)
        async with db.execute(query, params) as cur:
            rows = await cur.fetchall()
    for r in rows:
        out.append(NewsEvent(
            id=r[0], source_kind=r[1], source_handle=r[2], credibility=r[3], language=r[4],
            text=r[5], url=r[6], fetched_at=datetime.fromisoformat(r[7]),
            published_at=datetime.fromisoformat(r[8]) if r[8] else None,
        ))
    return out


async def replay(events: list[NewsEvent]) -> None:
    settings = get_settings()
    markets = load_markets()
    analyst = ClaudeAnalyst(settings, load_analyst_prompt())
    poly = PolymarketClient(settings)
    bankroll = Bankroll(starting_usdc=settings.bankroll_usdc)
    breaker = CircuitBreaker(daily_loss_limit_pct=settings.daily_loss_limit_pct,
                             starting_equity=settings.bankroll_usdc)
    cooldown = CooldownTracker(minutes=30)
    scenarios = ScenarioRegistry.load(CONFIG_DIR / "scenarios.yaml")
    snapshots = await poly.refresh_snapshots(markets)

    db_path = settings.database_url.split("///", 1)[-1]
    recent: list[NewsEvent] = []
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT id, source_kind, source_handle, credibility, language, "
            "text, url, fetched_at, published_at FROM events "
            "ORDER BY fetched_at DESC LIMIT 100"
        ) as cur:
            for r in await cur.fetchall():
                recent.append(NewsEvent(
                    id=r[0], source_kind=r[1], source_handle=r[2], credibility=r[3],
                    language=r[4], text=r[5], url=r[6],
                    fetched_at=datetime.fromisoformat(r[7]),
                    published_at=datetime.fromisoformat(r[8]) if r[8] else None,
                ))

    table = Table(title="Replay results")
    for col in ("event_id", "source", "market", "side", "edge", "conf", "would_size", "decision"):
        table.add_column(col)

    for event in events:
        cor_mult, corroborating = corroboration_score(event, recent)
        verdict = await analyst.analyze(event, markets, snapshots, corroborating)
        if not verdict.signals:
            table.add_row(event.id[:10], event.source_handle, "-", "-", "-", "-", "-",
                          "no_signal_emitted")
        for s in verdict.signals:
            snap = snapshots.get(s.market_id)
            if snap is None:
                table.add_row(event.id[:10], event.source_handle, s.market_id, s.side,
                              f"{s.edge:+.3f}", str(s.confidence), "-", "no_snapshot")
                continue
            decision = size_trade(
                s, snap, settings=settings, bankroll=bankroll, breaker=breaker,
                cooldown=cooldown, scenarios=scenarios,
                corroboration_multiplier=cor_mult,
            )
            if decision.intent is None:
                table.add_row(event.id[:10], event.source_handle, s.market_id, s.side,
                              f"{s.edge:+.3f}", str(s.confidence), "-",
                              decision.skip_reason or "skipped")
            else:
                table.add_row(event.id[:10], event.source_handle, s.market_id, s.side,
                              f"{decision.intent.edge:+.3f}", str(decision.intent.confidence),
                              f"${decision.intent.size_usdc:.2f}", "would_trade")

    console.print(table)
    await poly.aclose()


def _parse_duration(s: str) -> timedelta:
    s = s.strip().lower()
    if s.endswith("h"):
        return timedelta(hours=float(s[:-1]))
    if s.endswith("m"):
        return timedelta(minutes=float(s[:-1]))
    if s.endswith("d"):
        return timedelta(days=float(s[:-1]))
    return timedelta(hours=float(s))


def cli() -> None:
    parser = argparse.ArgumentParser(prog="osint-replay")
    parser.add_argument("--event-id", help="Replay a single event by id")
    parser.add_argument("--since", default="1h", help="Replay events from the last N (e.g. 2h, 30m, 1d)")
    parser.add_argument("--market", help="Filter to events that originally triggered a signal on this market")
    args = parser.parse_args()
    settings = get_settings()
    db_path = settings.database_url.split("///", 1)[-1]
    since = None if args.event_id else _parse_duration(args.since)
    events = asyncio.run(_load_events(db_path, event_id=args.event_id, since=since, market=args.market))
    if not events:
        console.print("[yellow]no events matched")
        sys.exit(0)
    asyncio.run(replay(events))


if __name__ == "__main__":
    cli()
