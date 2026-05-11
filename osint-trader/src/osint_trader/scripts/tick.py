"""Stateless tick mode for cron / GitHub Actions / serverless invocations.

Each `osint-tick` run:
  1. Acquires the leader lock (refuses overlapping cron runs)
  2. Loads the watermark (last successful run time) from SQLite
  3. Pulls RSS + GDELT entries newer than the watermark
  4. Runs each through the analyst → risk → execution pipeline
  5. Updates the watermark, releases the lock, exits

No long-lived processes, no Telegram realtime (use the full daemon for that).
This is the mode designed to run under GitHub Actions cron / Modal scheduled
function / Fly.io scheduled machine — all of which have generous free tiers.

Run:
    osint-tick                  # one-shot
    osint-tick --window-min 30  # how far back to look for new items

Exit codes:
    0  success (zero or more events processed)
    2  another instance is running
    3  preflight failed (bad slug, missing API key, etc.)
    4  unexpected error
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

from ..analysis import (
    ClaudeAnalyst,
    Deduper,
    FactChecker,
    corroboration_score,
    is_relevant_to_any_market,
)
from ..config import (
    CONFIG_DIR,
    get_settings,
    load_analyst_prompt,
    load_markets,
    load_sources,
)
from ..credibility import CredibilityTracker
from ..execution import quote_for
from ..markets import PolymarketClient
from ..models import NewsEvent
from ..notify import TelegramAlerter
from ..observability import configure_logging, get_logger
from ..observability.leader import LeaderLock, LeaderLockError
from ..persistence import Store
from ..preflight import PreflightError, run_preflight
from ..risk import Bankroll, CircuitBreaker, size_trade
from ..risk.cooldown import CooldownTracker
from ..risk.scenarios import ScenarioRegistry
from ..sources import EventQueue, GDELTSource, RSSSource

logger = get_logger(__name__)


async def tick(window_minutes: int = 15) -> int:
    settings = get_settings()
    markets = load_markets()
    sources_cfg = load_sources()

    store = Store(settings.database_url)
    await store.init()

    deduper = Deduper()
    poly = PolymarketClient(settings)
    analyst = ClaudeAnalyst(settings, load_analyst_prompt())
    fact_checker = FactChecker(settings)
    alerter = TelegramAlerter(
        settings.telegram_bot_token,
        settings.telegram_alert_chat_id,
        min_tier=os.getenv("ALERT_MIN_TIER", "actionable"),  # type: ignore[arg-type]
    )
    bankroll = Bankroll(starting_usdc=settings.bankroll_usdc)
    breaker = CircuitBreaker(
        daily_loss_limit_pct=settings.daily_loss_limit_pct,
        starting_equity=settings.bankroll_usdc,
    )
    cooldown = CooldownTracker(minutes=30)
    scenarios = ScenarioRegistry.load(CONFIG_DIR / "scenarios.yaml")
    credibility = CredibilityTracker()
    for ch in sources_cfg.telegram_channels:
        credibility.seed_prior(ch.handle, ch.credibility)
    for f in sources_cfg.rss_feeds:
        credibility.seed_prior(f.url, f.credibility)
    for src, won in await store.source_outcomes():
        credibility.update(src, won)

    try:
        await run_preflight(settings, markets, poly)
    except PreflightError as exc:
        logger.error("preflight_failed", error=str(exc))
        return 3

    queue: EventQueue = asyncio.Queue()
    rss = RSSSource(sources_cfg.rss_feeds, poll_seconds=0)
    gdelt = GDELTSource(sources_cfg.gdelt)

    # Poll each source ONCE — we don't loop forever.
    pollers = []
    for feed in sources_cfg.rss_feeds:
        pollers.append(rss._poll_one(feed, queue))
    if sources_cfg.gdelt.enabled and sources_cfg.gdelt.query:
        import httpx
        async with httpx.AsyncClient(timeout=20) as http:
            try:
                await gdelt._poll(http, queue)
            except Exception as exc:
                logger.warning("gdelt_tick_failed", error=str(exc))
    if pollers:
        await asyncio.gather(*pollers, return_exceptions=True)

    watermark = await store.get_watermark("tick") or (
        datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    )
    logger.info("tick_started", queue_size=queue.qsize(), watermark=watermark.isoformat())

    n_events = n_signals = n_trades = 0
    while not queue.empty():
        event: NewsEvent = queue.get_nowait()
        if event.published_at and event.published_at < watermark:
            continue
        event.credibility = credibility.credibility(event.source_handle, event.credibility)
        if deduper.is_duplicate(event):
            continue
        deduper.remember(event)
        if not await store.save_event(event):
            continue
        if not is_relevant_to_any_market(event.text, markets):
            continue
        n_events += 1

        recent = await store.recent_events(since_minutes=360, limit=50)
        cor_mult, corroborating = corroboration_score(event, recent)
        active = [m for m in markets if not poly.is_inactive(m.market_id)]
        snapshots = await poly.refresh_snapshots(active)
        verdict = await analyst.analyze(event, active, snapshots, corroborating)

        for signal in verdict.signals:
            await store.save_signal(signal)
            n_signals += 1
            verified, why = await fact_checker.verify(event, signal, corroborating)
            if not verified:
                await alerter.signal_alert(event, signal, verdict.summary_en,
                                           actionable=False, skip_reason=f"factcheck:{why}")
                continue
            snap = snapshots.get(signal.market_id)
            if snap is None:
                continue
            token_id = snap.yes_token_id if signal.side == "yes" else snap.no_token_id
            book = await poly.fetch_orderbook(token_id) if token_id else None
            decision = size_trade(
                signal, snap, settings=settings, bankroll=bankroll, breaker=breaker,
                cooldown=cooldown, scenarios=scenarios, book=book,
                corroboration_multiplier=cor_mult,
            )
            if decision.intent is None:
                await alerter.signal_alert(event, signal, verdict.summary_en,
                                           actionable=False, skip_reason=decision.skip_reason)
                continue
            strategy = os.getenv("PRICING_STRATEGY", "taker")
            if book is not None and strategy != "taker":
                decision.intent = decision.intent.model_copy(
                    update={"price": quote_for(decision.intent.side, book,
                                               decision.intent.price, strategy=strategy)}  # type: ignore[arg-type]
                )
            await alerter.signal_alert(event, signal, verdict.summary_en, actionable=True)
            bankroll.add_exposure(decision.intent.market_id, decision.intent.size_usdc)
            result = await poly.place_order(decision.intent)
            await store.save_trade(result, triggered_by_event_id=event.id)
            await alerter.trade_alert(decision.intent, result)
            n_trades += 1

    await store.set_watermark("tick", datetime.now(timezone.utc))
    await poly.aclose()
    await alerter.aclose()
    logger.info("tick_done", events=n_events, signals=n_signals, trades=n_trades)
    return 0


def cli() -> None:
    parser = argparse.ArgumentParser(prog="osint-tick")
    parser.add_argument("--window-min", type=int, default=15,
                        help="On first run, how far back to look (default 15min)")
    parser.add_argument("--log-level", default=None)
    args = parser.parse_args()
    settings = get_settings()
    configure_logging(args.log_level or settings.log_level)
    lock = LeaderLock(os.getenv("LEADER_LOCK_PATH", ".osint_tick.lock"))
    try:
        lock.acquire()
    except LeaderLockError as exc:
        logger.error("leader_lock_failed", error=str(exc))
        sys.exit(2)
    try:
        sys.exit(asyncio.run(tick(window_minutes=args.window_min)))
    except Exception:
        logger.exception("tick_unexpected_error")
        sys.exit(4)
    finally:
        lock.release()


if __name__ == "__main__":
    cli()
