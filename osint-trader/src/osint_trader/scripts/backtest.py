"""Replay historical events and simulate end-to-end PnL.

Each JSONL event can include:
  - `text`, `source_kind`, `source_handle`, `credibility`, `language`, `published_at`
  - `snapshots`: { market_id: {yes_price, no_price, title?, liquidity?, depth?} }
       depth: list of [price, size_shares] for the asks side; if absent we use
              a flat book at yes_price/no_price.
  - `resolutions`: { market_id: 1|0 }   # final outcome of the market for PnL
  - `next_prices`: { market_id: yes_price_after_event }  # used for take-profit

Run:
    osint-backtest events.jsonl
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

import random

from ..analysis import ClaudeAnalyst, corroboration_score
from ..config import get_settings, load_analyst_prompt, load_markets
from ..markets.fill_model import estimate_fill
from ..markets.orderbook import BookLevel, OrderBook
from ..markets.subgraph import fetch_resolution
from ..models import MarketSnapshot, NewsEvent
from ..risk import Bankroll, CircuitBreaker, size_trade
from ..risk.cooldown import CooldownTracker
from ..risk.scenarios import ScenarioRegistry
from ..sources.base import stable_event_id

console = Console()


async def run(path: Path, *, use_subgraph_resolutions: bool = True, seed: int = 42) -> None:
    settings = get_settings()
    markets = load_markets()
    by_id = {m.market_id: m for m in markets}
    analyst = ClaudeAnalyst(settings, load_analyst_prompt())
    bankroll = Bankroll(starting_usdc=settings.bankroll_usdc)
    breaker = CircuitBreaker(daily_loss_limit_pct=settings.daily_loss_limit_pct,
                             starting_equity=settings.bankroll_usdc)
    cooldown = CooldownTracker(minutes=30)
    scenarios = ScenarioRegistry.load(Path("config/scenarios.yaml"))
    rng = random.Random(seed)
    n_filled = n_missed = 0

    # Optional: hydrate resolutions from the live Polymarket Gamma API for
    # markets that have already settled. Falls back to the JSONL `resolutions`
    # field when the subgraph call fails or the market is still open.
    live_resolutions: dict[str, int | None] = {}
    if use_subgraph_resolutions:
        for m in markets:
            live_resolutions[m.market_id] = await fetch_resolution(
                settings.polymarket_gamma_host, m.slug,
            )

    table = Table(title="Backtest results")
    for col in ("event", "market", "side", "size", "fill", "exit", "pnl", "skip"):
        table.add_column(col)

    history: list[NewsEvent] = []
    open_positions: dict[str, tuple[float, str, float, str]] = {}  # mid -> (entry, side, size, evt_id)
    total_pnl = 0.0
    n_trades = n_wins = 0

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
        books: dict[str, OrderBook] = {}
        for mid, payload in (raw.get("snapshots") or {}).items():
            cfg = by_id.get(mid)
            if not cfg:
                continue
            yes = float(payload["yes_price"])
            no = float(payload["no_price"])
            snapshots[mid] = MarketSnapshot(
                market_id=mid, slug=cfg.slug, title=payload.get("title", cfg.title),
                yes_price=yes, no_price=no,
                liquidity_usdc=float(payload.get("liquidity", 5000)),
            )
            depth = payload.get("depth")
            if depth:
                asks = [BookLevel(float(p), float(s)) for p, s in depth]
                books[mid] = OrderBook(bids=[], asks=sorted(asks, key=lambda x: x.price))
            else:
                # flat book: assume infinite depth at the snapshot price (no slippage)
                books[mid] = OrderBook(bids=[], asks=[BookLevel(yes, 100000)])

        cor_mult, corroborating = corroboration_score(event, history)
        verdict = await analyst.analyze(event, markets, snapshots, corroborating)

        for signal in verdict.signals:
            snap = snapshots.get(signal.market_id)
            if snap is None:
                continue
            book = books.get(signal.market_id)
            decision = size_trade(
                signal, snap,
                settings=settings, bankroll=bankroll, breaker=breaker,
                cooldown=cooldown, scenarios=scenarios, book=book,
                corroboration_multiplier=cor_mult,
            )
            if decision.intent is None:
                table.add_row(text[:30], signal.market_id, signal.side, "-", "-", "-", "-",
                              decision.skip_reason or "skipped")
                continue
            intent = decision.intent

            # Adverse-selection fill model: maybe we don't get filled at all,
            # maybe partial. Adjusts intent.size_usdc and intent.price in place.
            filled_usdc, fill_price = estimate_fill(
                intent.side, intent.size_usdc, intent.price, book, rng=rng,
            )
            if filled_usdc < 1.0:
                n_missed += 1
                table.add_row(text[:30], intent.market_id, intent.side,
                              f"${intent.size_usdc:.2f}", f"{intent.price:.3f}",
                              "-", "-", "missed_fill")
                continue
            n_filled += 1
            intent = intent.model_copy(update={
                "size_usdc": round(filled_usdc, 2),
                "price": round(fill_price, 4),
            })
            bankroll.add_exposure(intent.market_id, intent.size_usdc)
            open_positions[intent.market_id] = (intent.price, intent.side,
                                                intent.size_usdc, event.id)

            # Resolution priority: live subgraph > JSONL > none.
            resolution = (raw.get("resolutions") or {}).get(intent.market_id)
            if resolution is None:
                resolution = live_resolutions.get(intent.market_id)
            next_price = (raw.get("next_prices") or {}).get(intent.market_id)
            exit_price, pnl, label = _settle(intent, resolution, next_price)
            if pnl is not None:
                total_pnl += pnl
                n_trades += 1
                n_wins += 1 if pnl > 0 else 0
                bankroll.settle(intent.market_id, pnl)
                table.add_row(text[:30], intent.market_id, intent.side,
                              f"${intent.size_usdc:.2f}", f"{intent.price:.3f}",
                              f"{exit_price:.3f}({label})", f"${pnl:+.2f}", "")
                open_positions.pop(intent.market_id, None)
            else:
                table.add_row(text[:30], intent.market_id, intent.side,
                              f"${intent.size_usdc:.2f}", f"{intent.price:.3f}",
                              "open", "-", "")
        history.append(event)

    console.print(table)
    hit_rate = (n_wins / n_trades * 100) if n_trades else 0.0
    console.print(
        f"\nFilled: {n_filled}  Missed: {n_missed}  "
        f"Trades: {n_trades}  Wins: {n_wins}  Hit-rate: {hit_rate:.1f}%  "
        f"Total PnL: ${total_pnl:+.2f}  Final equity: ${bankroll.equity:.2f}"
    )


def _settle(intent, resolution, next_price):
    """Return (exit_price, pnl, label) or (..., None, ...) if still open."""
    if resolution is not None:
        # Final outcome resolved; YES pays $1 if 1, NO pays $1 if 0.
        if intent.side == "yes":
            shares = intent.size_usdc / max(intent.price, 1e-6)
            payout = shares * (1.0 if resolution else 0.0)
        else:
            shares = intent.size_usdc / max(1.0 - intent.price, 1e-6)
            payout = shares * (1.0 if not resolution else 0.0)
        return float(resolution), payout - intent.size_usdc, "resolve"
    if next_price is not None:
        # Mark-to-market exit at next_price (simulates a fast take-profit).
        if intent.side == "yes":
            shares = intent.size_usdc / max(intent.price, 1e-6)
            payout = shares * float(next_price)
        else:
            shares = intent.size_usdc / max(1.0 - intent.price, 1e-6)
            payout = shares * (1.0 - float(next_price))
        return float(next_price), payout - intent.size_usdc, "mtm"
    return 0.0, None, "open"


def cli() -> None:
    parser = argparse.ArgumentParser(prog="osint-backtest")
    parser.add_argument("events", type=Path, help="Path to JSONL file")
    parser.add_argument("--no-subgraph", action="store_true",
                        help="Skip live Polymarket Gamma resolution lookup")
    parser.add_argument("--seed", type=int, default=42,
                        help="RNG seed for the fill model")
    args = parser.parse_args()
    if not args.events.exists():
        console.print(f"[red]File not found: {args.events}")
        sys.exit(1)
    asyncio.run(run(args.events, use_subgraph_resolutions=not args.no_subgraph, seed=args.seed))


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
