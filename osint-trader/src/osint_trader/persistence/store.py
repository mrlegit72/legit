"""SQLite-backed event/signal/trade/position store.

Schema is small on purpose: fast inserts, easy to query for backtest/analytics.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiosqlite

from ..models import NewsEvent, Signal, TradeResult


SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id              TEXT PRIMARY KEY,
    source_kind     TEXT NOT NULL,
    source_handle   TEXT NOT NULL,
    credibility     REAL NOT NULL,
    language        TEXT NOT NULL,
    text            TEXT NOT NULL,
    url             TEXT,
    fetched_at      TEXT NOT NULL,
    published_at    TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_fetched_at ON events(fetched_at);

CREATE TABLE IF NOT EXISTS signals (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    triggered_by_event_id   TEXT NOT NULL,
    market_id               TEXT NOT NULL,
    side                    TEXT NOT NULL,
    prob_yes                REAL NOT NULL,
    edge                    REAL NOT NULL,
    confidence              INTEGER NOT NULL,
    reasoning               TEXT NOT NULL,
    created_at              TEXT NOT NULL,
    FOREIGN KEY (triggered_by_event_id) REFERENCES events(id)
);

CREATE INDEX IF NOT EXISTS idx_signals_market_created ON signals(market_id, created_at);

CREATE TABLE IF NOT EXISTS trades (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id       TEXT NOT NULL,
    slug            TEXT NOT NULL,
    side            TEXT NOT NULL,
    price           REAL NOT NULL,
    size_usdc       REAL NOT NULL,
    edge            REAL NOT NULL,
    confidence      INTEGER NOT NULL,
    status          TEXT NOT NULL,
    fill_price      REAL,
    filled_size_usdc REAL,
    order_id        TEXT,
    error           TEXT,
    intent_json     TEXT NOT NULL,
    triggered_by_event_id TEXT,
    executed_at     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_trades_executed_at ON trades(executed_at);

CREATE TABLE IF NOT EXISTS settlements (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id               TEXT NOT NULL,
    side                    TEXT NOT NULL,
    entry_price             REAL NOT NULL,
    exit_price              REAL NOT NULL,
    size_usdc               REAL NOT NULL,
    pnl_usdc                REAL NOT NULL,
    reason                  TEXT NOT NULL,
    triggered_by_event_id   TEXT,
    settled_at              TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_settlements_settled_at ON settlements(settled_at);
"""


class Store:
    def __init__(self, path: str | Path = "osint_trader.db") -> None:
        if isinstance(path, str) and path.startswith("sqlite"):
            path = path.split("///", 1)[-1]
        self.path = str(path)

    async def init(self) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(SCHEMA)
            await db.commit()

    # ---------------- events ----------------

    async def event_exists(self, event_id: str) -> bool:
        async with aiosqlite.connect(self.path) as db:
            async with db.execute("SELECT 1 FROM events WHERE id = ?", (event_id,)) as cur:
                return (await cur.fetchone()) is not None

    async def save_event(self, event: NewsEvent) -> bool:
        async with aiosqlite.connect(self.path) as db:
            try:
                await db.execute(
                    """INSERT INTO events (id, source_kind, source_handle, credibility,
                                           language, text, url, fetched_at, published_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        event.id, event.source_kind, event.source_handle,
                        event.credibility, event.language, event.text, event.url,
                        event.fetched_at.isoformat(),
                        event.published_at.isoformat() if event.published_at else None,
                    ),
                )
                await db.commit()
                return True
            except aiosqlite.IntegrityError:
                return False

    async def recent_events(self, since_minutes: int = 360, limit: int = 50) -> list[NewsEvent]:
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=since_minutes)).isoformat()
        async with aiosqlite.connect(self.path) as db:
            async with db.execute(
                """SELECT id, source_kind, source_handle, credibility, language,
                          text, url, fetched_at, published_at
                   FROM events WHERE fetched_at >= ?
                   ORDER BY fetched_at DESC LIMIT ?""",
                (cutoff, limit),
            ) as cur:
                rows = await cur.fetchall()
        return [
            NewsEvent(
                id=r[0], source_kind=r[1], source_handle=r[2], credibility=r[3],
                language=r[4], text=r[5], url=r[6],
                fetched_at=datetime.fromisoformat(r[7]),
                published_at=datetime.fromisoformat(r[8]) if r[8] else None,
            )
            for r in rows
        ]

    # ---------------- signals ----------------

    async def save_signal(self, signal: Signal) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """INSERT INTO signals (triggered_by_event_id, market_id, side, prob_yes,
                                        edge, confidence, reasoning, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    signal.triggered_by_event_id, signal.market_id, signal.side,
                    signal.prob_yes, signal.edge, signal.confidence, signal.reasoning,
                    signal.created_at.isoformat(),
                ),
            )
            await db.commit()
            return cur.lastrowid

    # ---------------- trades ----------------

    async def save_trade(self, result: TradeResult, triggered_by_event_id: str | None = None) -> int:
        intent = result.intent
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """INSERT INTO trades (market_id, slug, side, price, size_usdc, edge,
                                       confidence, status, fill_price, filled_size_usdc,
                                       order_id, error, intent_json, triggered_by_event_id,
                                       executed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    intent.market_id, intent.slug, intent.side, intent.price,
                    intent.size_usdc, intent.edge, intent.confidence, result.status,
                    result.fill_price, result.filled_size_usdc, result.order_id,
                    result.error, json.dumps(intent.model_dump(mode="json")),
                    triggered_by_event_id, result.executed_at.isoformat(),
                ),
            )
            await db.commit()
            return cur.lastrowid

    # ---------------- settlements ----------------

    async def save_settlement(
        self, *, market_id: str, side: str, entry_price: float, exit_price: float,
        size_usdc: float, pnl_usdc: float, reason: str,
        triggered_by_event_id: str | None, settled_at: datetime,
    ) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """INSERT INTO settlements (market_id, side, entry_price, exit_price,
                                            size_usdc, pnl_usdc, reason,
                                            triggered_by_event_id, settled_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (market_id, side, entry_price, exit_price, size_usdc, pnl_usdc,
                 reason, triggered_by_event_id, settled_at.isoformat()),
            )
            await db.commit()
            return cur.lastrowid

    async def realized_pnl_today_usdc(self) -> float:
        start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        async with aiosqlite.connect(self.path) as db:
            async with db.execute(
                "SELECT COALESCE(SUM(pnl_usdc), 0) FROM settlements WHERE settled_at >= ?",
                (start,),
            ) as cur:
                row = await cur.fetchone()
        return float(row[0] if row else 0.0)

    async def source_outcomes(self) -> list[tuple[str, bool]]:
        """Return (source_handle, won) pairs joining settlements ↔ events for credibility learning."""
        async with aiosqlite.connect(self.path) as db:
            async with db.execute(
                """SELECT e.source_handle, s.pnl_usdc
                   FROM settlements s
                   JOIN events e ON e.id = s.triggered_by_event_id
                   ORDER BY s.settled_at"""
            ) as cur:
                rows = await cur.fetchall()
        return [(r[0], r[1] > 0) for r in rows]
