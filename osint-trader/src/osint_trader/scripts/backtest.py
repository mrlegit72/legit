"""Replay historical events from a JSONL file through the analyst+risk pipeline.

Format (one JSON object per line):
  {
    "text": "...",
    "source_kind": "rss",
    "source_handle": "reuters.com",
    "credibility": 0.9,
    "language": "en",
    "published_at": "2024-06-24T12:00:00Z",
    "snapshots": {
        "iranian-regime-fall": {"yes_price": 0.12, "no_price": 0.88, "title": "..."}
    }
  }

Run:
    python -m osint_trader.scripts.backtest events.jsonl
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.table import Table

from ..analysis import ClaudeAnalyst, corroboration_score
from ..config import get_settings, load_analyst_prompt, load_markets
from ..models import MarketSnapshot, NewsEvent
from ..risk import Bankroll, CircuitBreaker, size_trade
from ..sources.base import stable_event_id

console = Console()


async def run(path: Path) -> None:
    settings = get_settings()
    markets = load_markets()
    by_id = {m.market_id: m for m in markets}
    analyst = ClaudeAnalyst(settings, load_analyst_prompt())
    bankroll = Bankroll(starting_usdc=settings.bankroll_usdc)
    breaker = CircuitBreaker(daily_loss_limit_pct=settings.daily_loss_limit_pct,
                             starting_equity=settings.bankroll_usdc)

    table = Table(title="Backtest results")
    for col in ("event", "market", "side", "size", "edge", "conf", "skip"):
        table.add_column(col)

    history: list[NewsEvent] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        raw = json.loads(line)
        text = raw["text"]
        published = _parse_dt(raw.get("published_at"))
        event = NewsEvent(
            id=stable_event_id(raw.get("source_kind", "rss"), raw.get("source_handle", "unknown"), text),
            source_kind=raw.get("source_kind", "rss"),
            source_handle=raw.get("source_handle", "unknown"),
            credibility=float(raw.get("credibility", 0.5)),
            language=raw.get("language", "en"),
            text=text,
            published_at=published,
        )
        snapshots: dict[str, MarketSnapshot] = {}
        for mid, payload in (raw.get("snapshots") or {}).items():
            cfg = by_id.get(mid)
            if not cfg:
                continue
            snapshots[mid] = MarketSnapshot(
                market_id=mid, slug=cfg.slug, title=payload.get("title", cfg.title),
                yes_price=float(payload["yes_price"]), no_price=float(payload["no_price"]),
            )
        cor_mult, corroborating = corroboration_score(event, history)
        verdict = await analyst.analyze(event, markets, snapshots, corroborating)
        for signal in verdict.signals:
            snap = snapshots.get(signal.market_id)
            if snap is None:
                continue
            decision = size_trade(signal, snap, settings=settings, bankroll=bankroll,
                                  breaker=breaker, corroboration_multiplier=cor_mult)
            if decision.intent:
                bankroll.add_exposure(decision.intent.market_id, decision.intent.size_usdc)
                table.add_row(text[:40], signal.market_id, signal.side,
                              f"${decision.intent.size_usdc:.2f}",
                              f"{decision.intent.edge:+.3f}",
                              str(decision.intent.confidence), "")
            else:
                table.add_row(text[:40], signal.market_id, signal.side, "-", "-", "-",
                              decision.skip_reason or "skipped")
        history.append(event)

    console.print(table)
    console.print(f"\nFinal exposure: ${bankroll.total_exposure:.2f}  Equity: ${bankroll.equity:.2f}")


def cli() -> None:
    parser = argparse.ArgumentParser(prog="osint-backtest")
    parser.add_argument("events", type=Path, help="Path to JSONL file")
    args = parser.parse_args()
    if not args.events.exists():
        console.print(f"[red]File not found: {args.events}")
        sys.exit(1)
    asyncio.run(run(args.events))


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s).astimezone(timezone.utc)
    except ValueError:
        return None


if __name__ == "__main__":
    cli()
