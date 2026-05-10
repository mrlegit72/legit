"""Orchestrator entry point.

Spins up:
  * OSINT sources (Telegram / RSS / GDELT) feeding a single asyncio.Queue
  * A periodic Polymarket snapshot refresher
  * A worker that pulls events, dedups, asks Claude, sizes trades, executes,
    persists, and alerts

Run as:
    python -m osint_trader.main
or via console script:
    osint-trader
"""
from __future__ import annotations

import argparse
import asyncio
import signal as _sig

from .analysis import ClaudeAnalyst, Deduper, corroboration_score, is_relevant_to_any_market
from .config import (
    SourcesConfig,
    get_settings,
    load_analyst_prompt,
    load_markets,
    load_sources,
)
from .markets import PolymarketClient
from .models import NewsEvent
from .notify import TelegramAlerter
from .observability import configure_logging, get_logger
from .persistence import Store
from .risk import Bankroll, CircuitBreaker, size_trade
from .sources import EventQueue, GDELTSource, RSSSource, TelegramSource

logger = get_logger(__name__)


class Orchestrator:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.markets = load_markets()
        self.sources_cfg: SourcesConfig = load_sources()
        self.store = Store(self.settings.database_url)
        self.queue: EventQueue = asyncio.Queue(maxsize=512)
        self.deduper = Deduper()
        self.poly = PolymarketClient(self.settings)
        self.analyst = ClaudeAnalyst(self.settings, load_analyst_prompt())
        self.alerter = TelegramAlerter(self.settings.telegram_bot_token, self.settings.telegram_alert_chat_id)
        self.bankroll = Bankroll(starting_usdc=self.settings.bankroll_usdc)
        self.breaker = CircuitBreaker(
            daily_loss_limit_pct=self.settings.daily_loss_limit_pct,
            starting_equity=self.settings.bankroll_usdc,
        )
        self._stop = asyncio.Event()

    async def run(self) -> None:
        await self.store.init()
        await self.poly.refresh_snapshots(self.markets)
        logger.info(
            "orchestrator_started",
            mode=self.settings.trade_mode.value,
            markets=[m.market_id for m in self.markets],
        )

        tasks = [
            asyncio.create_task(self._snapshot_refresher(), name="snapshots"),
            asyncio.create_task(self._worker(), name="worker"),
            asyncio.create_task(TelegramSource(self.sources_cfg.telegram_channels).run(self.queue), name="telegram"),
            asyncio.create_task(RSSSource(self.sources_cfg.rss_feeds).run(self.queue), name="rss"),
            asyncio.create_task(GDELTSource(self.sources_cfg.gdelt).run(self.queue), name="gdelt"),
        ]

        loop = asyncio.get_running_loop()
        for s in (_sig.SIGINT, _sig.SIGTERM):
            try:
                loop.add_signal_handler(s, self._stop.set)
            except NotImplementedError:
                pass  # Windows

        await self._stop.wait()
        logger.info("orchestrator_stopping")
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await self.poly.aclose()
        await self.alerter.aclose()

    async def _snapshot_refresher(self) -> None:
        while not self._stop.is_set():
            try:
                await self.poly.refresh_snapshots(self.markets)
            except Exception as exc:
                logger.warning("snapshot_refresh_failed", error=str(exc))
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=60)
            except asyncio.TimeoutError:
                pass

    async def _worker(self) -> None:
        while not self._stop.is_set():
            event: NewsEvent = await self.queue.get()
            try:
                await self._handle_event(event)
            except Exception:
                logger.exception("worker_event_failed", event_id=event.id)
                self.breaker.record_error()
            finally:
                self.queue.task_done()

    async def _handle_event(self, event: NewsEvent) -> None:
        if self.deduper.is_duplicate(event):
            logger.debug("dedup_drop", event_id=event.id)
            return
        self.deduper.remember(event)

        is_new = await self.store.save_event(event)
        if not is_new:
            return

        if not is_relevant_to_any_market(event.text, self.markets):
            logger.debug("filtered_irrelevant", event_id=event.id, text=event.text[:80])
            return

        recent = await self.store.recent_events(since_minutes=360, limit=50)
        cor_mult, corroborating = corroboration_score(event, recent)

        snapshots = await self.poly.refresh_snapshots(self.markets)
        verdict = await self.analyst.analyze(event, self.markets, snapshots, corroborating)

        for signal in verdict.signals:
            await self.store.save_signal(signal)
            await self.alerter.signal_alert(event, signal, verdict.summary_en)

            snap = snapshots.get(signal.market_id)
            if snap is None:
                logger.info("skip_no_snapshot", market=signal.market_id)
                continue

            decision = size_trade(
                signal, snap,
                settings=self.settings,
                bankroll=self.bankroll,
                breaker=self.breaker,
                corroboration_multiplier=cor_mult,
            )
            if decision.intent is None:
                logger.info("skip_signal", market=signal.market_id, reason=decision.skip_reason)
                continue

            self.bankroll.add_exposure(decision.intent.market_id, decision.intent.size_usdc)
            result = await self.poly.place_order(decision.intent)
            await self.store.save_trade(result)
            await self.alerter.trade_alert(decision.intent, result)

            if result.status in ("dry_run", "filled"):
                self.breaker.record_success()
            elif result.status == "error":
                self.breaker.record_error()


def cli() -> None:
    parser = argparse.ArgumentParser(prog="osint-trader")
    parser.add_argument("--log-level", default=None, help="DEBUG/INFO/WARNING")
    args = parser.parse_args()
    settings = get_settings()
    configure_logging(args.log_level or settings.log_level)
    asyncio.run(Orchestrator().run())


if __name__ == "__main__":
    cli()
