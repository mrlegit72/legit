"""Orchestrator entry point.

Spins up:
  * OSINT sources (Telegram / RSS / GDELT) feeding a single asyncio.Queue
  * A periodic Polymarket snapshot refresher
  * A worker that pulls events, dedups, asks Claude, sizes trades, executes,
    persists, and alerts
  * PositionManager (exits) + OrderMonitor (cancel-replace) loops
  * Optional: Prometheus metrics server, Telegram kill switch,
    on-chain settlement reader, OpenTelemetry tracing.

Pre-flight: validates every market slug + (in live mode) checks USDC balance.
Single-instance: file pidlock prevents two copies.

Run:
    osint-trader
"""
from __future__ import annotations

import argparse
import asyncio
import os
import signal as _sig
import sys

from .analysis import (
    ClaudeAnalyst,
    Deduper,
    FactChecker,
    corroboration_score,
    is_relevant_to_any_market,
)
from .analysis.regime import RegimeDetector
from .config import (
    CONFIG_DIR,
    SourcesConfig,
    get_settings,
    load_analyst_prompt,
    load_markets,
    load_sources,
)
from .credibility import CredibilityTracker
from .execution import OrderMonitor, PositionManager, Settlement, quote_for
from .execution.chain_settlement import ChainSettlementReader
from .markets import PolymarketClient
from .models import NewsEvent, TradeIntent
from .notify import TelegramAlerter
from .observability import configure_logging, get_logger, metrics
from .observability import tracing
from .observability.kill_switch import KillSwitch
from .observability.leader import LeaderLock, LeaderLockError
from .persistence import Store
from .preflight import PreflightError, run_preflight
from .risk import Bankroll, CircuitBreaker, size_trade
from .risk.cooldown import CooldownTracker
from .risk.scenarios import ScenarioRegistry
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
        timeout_s = float(os.getenv("ANALYST_TIMEOUT_S", "8"))
        fallback_s = float(os.getenv("ANALYST_FALLBACK_TIMEOUT_S", "4"))
        self.analyst = ClaudeAnalyst(
            self.settings, load_analyst_prompt(),
            analyst_timeout_s=timeout_s, fallback_timeout_s=fallback_s,
        )
        self.fact_checker = FactChecker(self.settings)
        self.alerter = TelegramAlerter(
            self.settings.telegram_bot_token,
            self.settings.telegram_alert_chat_id,
            min_tier=os.getenv("ALERT_MIN_TIER", "actionable"),  # type: ignore[arg-type]
            digest_window_s=float(os.getenv("ALERT_DIGEST_WINDOW_S", "0")),
        )
        self.kill_switch = KillSwitch(
            self.settings.telegram_bot_token,
            self.settings.telegram_alert_chat_id,
        )
        self.bankroll = Bankroll(starting_usdc=self.settings.bankroll_usdc)
        self.breaker = CircuitBreaker(
            daily_loss_limit_pct=self.settings.daily_loss_limit_pct,
            starting_equity=self.settings.bankroll_usdc,
        )
        self.cooldown = CooldownTracker(minutes=30)
        self.scenarios = ScenarioRegistry.load(CONFIG_DIR / "scenarios.yaml")
        self.credibility = CredibilityTracker()
        self.regime = RegimeDetector()
        self.settlement = Settlement(self.store, self.bankroll, polymarket=self.poly)
        self.position_manager = PositionManager(
            snapshot_provider=self.poly.get_snapshot,
            on_close=self._handle_position_close,
        )
        self.order_monitor = OrderMonitor(self.poly, self.poly.get_snapshot)
        self.chain_reader = ChainSettlementReader(self.settings.polymarket_funder)
        self.pricing_strategy = os.getenv("PRICING_STRATEGY", "taker")  # taker | join_bid | mid_minus_bp
        self.lock = LeaderLock(os.getenv("LEADER_LOCK_PATH", ".osint_trader.lock"))
        self._stop = asyncio.Event()
        self._intent_event: dict[str, str] = {}

    async def run(self) -> None:
        tracing.init()
        try:
            self.lock.acquire()
        except LeaderLockError as exc:
            logger.error("leader_lock_failed", error=str(exc))
            sys.exit(2)

        try:
            await self.store.init()
            await self._hydrate_credibility()
            try:
                await run_preflight(self.settings, self.markets, self.poly)
            except PreflightError as exc:
                logger.error("preflight_failed", error=str(exc))
                sys.exit(3)

            metrics.equity(self.bankroll.equity)
            logger.info(
                "orchestrator_started",
                mode=self.settings.trade_mode.value,
                markets=[m.market_id for m in self.markets],
                pricing_strategy=self.pricing_strategy,
            )

            host = os.getenv("METRICS_HOST", "127.0.0.1")
            port = int(os.getenv("METRICS_PORT", "9108"))

            tasks = [
                asyncio.create_task(self._snapshot_refresher(), name="snapshots"),
                asyncio.create_task(self._worker(), name="worker"),
                asyncio.create_task(self.position_manager.run(self._stop), name="positions"),
                asyncio.create_task(self.order_monitor.run(self._stop), name="orders"),
                asyncio.create_task(self.kill_switch.run(self._stop), name="kill_switch"),
                asyncio.create_task(metrics.serve_forever(host, port, self._stop), name="metrics"),
                asyncio.create_task(TelegramSource(self.sources_cfg.telegram_channels).run(self.queue), name="telegram"),
                asyncio.create_task(RSSSource(self.sources_cfg.rss_feeds).run(self.queue), name="rss"),
                asyncio.create_task(GDELTSource(self.sources_cfg.gdelt).run(self.queue), name="gdelt"),
            ]
            if self.settings.trade_mode.value == "live" and self.settings.polymarket_funder:
                tasks.append(asyncio.create_task(
                    self.chain_reader.run(self._on_chain_payout), name="chain_settlement"))

            loop = asyncio.get_running_loop()
            for s in (_sig.SIGINT, _sig.SIGTERM):
                try:
                    loop.add_signal_handler(s, self._stop.set)
                except NotImplementedError:
                    pass

            await self._stop.wait()
            logger.info("orchestrator_stopping")
            self.chain_reader.stop()
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await self.poly.aclose()
            await self.alerter.aclose()
            await self.kill_switch.aclose()
        finally:
            self.lock.release()

    # ----------- background loops -----------

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

    async def _hydrate_credibility(self) -> None:
        for ch in self.sources_cfg.telegram_channels:
            self.credibility.seed_prior(ch.handle, ch.credibility)
        for f in self.sources_cfg.rss_feeds:
            self.credibility.seed_prior(f.url, f.credibility)
        outcomes = await self.store.source_outcomes()
        if outcomes:
            self.credibility.hydrate_from_outcomes(outcomes)

    async def _worker(self) -> None:
        while not self._stop.is_set():
            event: NewsEvent = await self.queue.get()
            metrics.queue_depth(self.queue.qsize())
            try:
                with tracing.span("handle_event", event_id=event.id, source=event.source_kind):
                    await self._handle_event(event)
            except Exception:
                logger.exception("worker_event_failed", event_id=event.id)
                self.breaker.record_error()
            finally:
                self.queue.task_done()

    async def _handle_event(self, event: NewsEvent) -> None:
        metrics.event_received(event.source_kind)
        event.credibility = self.credibility.credibility(event.source_handle, event.credibility)
        self.regime.record(event.fetched_at)

        if self.deduper.is_duplicate(event):
            metrics.event_dropped("dedup")
            return
        self.deduper.remember(event)

        if not await self.store.save_event(event):
            metrics.event_dropped("dedup_db")
            return

        if not is_relevant_to_any_market(event.text, self.markets):
            metrics.event_dropped("filter")
            return

        recent = await self.store.recent_events(since_minutes=360, limit=50)
        cor_mult, corroborating = corroboration_score(event, recent)

        active_markets = [m for m in self.markets if not self.poly.is_inactive(m.market_id)]
        if not active_markets:
            metrics.event_dropped("no_active_markets")
            return

        snapshots = await self.poly.refresh_snapshots(active_markets)
        with metrics.measure_claude(), tracing.span("claude_analyze"):
            verdict = await self.analyst.analyze(event, active_markets, snapshots, corroborating)

        regime_label, conf_adjustment = self.regime.regime()

        for signal in verdict.signals:
            await self.store.save_signal(signal)
            metrics.signal_emitted(signal.market_id, signal.side)

            verified, why = await self.fact_checker.verify(event, signal, corroborating)
            if not verified:
                logger.info("factcheck_blocked", market=signal.market_id, why=why)
                await self.alerter.signal_alert(event, signal, verdict.summary_en,
                                                actionable=False, skip_reason=f"factcheck:{why}")
                continue

            if self.kill_switch.is_active():
                await self.alerter.signal_alert(event, signal, verdict.summary_en,
                                                actionable=False, skip_reason="kill_switch")
                continue

            snap = snapshots.get(signal.market_id)
            if snap is None:
                continue

            token_id = snap.yes_token_id if signal.side == "yes" else snap.no_token_id
            book = await self.poly.fetch_orderbook(token_id) if token_id else None

            # Apply regime-aware confidence adjustment via a temporary settings shim.
            # We bump min_confidence ↑ in calm regimes, ↓ in crisis regimes.
            effective_min_conf = max(50, self.settings.min_confidence + conf_adjustment)
            adjusted_settings = self.settings.model_copy(update={"min_confidence": effective_min_conf})

            decision = size_trade(
                signal, snap,
                settings=adjusted_settings,
                bankroll=self.bankroll,
                breaker=self.breaker,
                cooldown=self.cooldown,
                scenarios=self.scenarios,
                book=book,
                corroboration_multiplier=cor_mult,
            )
            if decision.intent is None:
                await self.alerter.signal_alert(event, signal, verdict.summary_en,
                                                actionable=False, skip_reason=decision.skip_reason)
                continue

            # Override taker price with the configured anti-front-running strategy.
            if book is not None and self.pricing_strategy != "taker":
                quoted = quote_for(decision.intent.side, book, decision.intent.price,
                                   strategy=self.pricing_strategy)  # type: ignore[arg-type]
                decision.intent = decision.intent.model_copy(update={"price": quoted})

            await self.alerter.signal_alert(event, signal, verdict.summary_en, actionable=True)
            self.bankroll.add_exposure(decision.intent.market_id, decision.intent.size_usdc)
            self._intent_event[decision.intent.market_id] = event.id

            with tracing.span("place_order", market=decision.intent.market_id,
                              side=decision.intent.side, regime=regime_label):
                result = await self.poly.place_order(decision.intent)
            await self.store.save_trade(result, triggered_by_event_id=event.id)
            metrics.trade_recorded(decision.intent.market_id, decision.intent.side, result.status)
            await self.alerter.trade_alert(decision.intent, result)

            if result.status in ("dry_run", "filled"):
                self.breaker.record_success()
                if result.status == "filled":
                    fill_price = result.fill_price or decision.intent.price
                    self.position_manager.open(decision.intent, fill_price)
                    if result.order_id:
                        self.order_monitor.track(decision.intent, result.order_id)
            elif result.status == "error":
                self.breaker.record_error()

            metrics.equity(self.bankroll.equity)

    # ----------- exit / chain handlers -----------

    async def _handle_position_close(self, position, reason: str, mark: float) -> None:
        intent: TradeIntent = position.intent
        triggered_by = self._intent_event.pop(intent.market_id, None)
        pnl = await self.settlement.settle(
            intent=intent,
            entry_price=position.entry_price,
            exit_price=mark,
            reason=reason,
            triggered_by_event_id=triggered_by,
        )
        await self.alerter.position_alert(intent, reason, mark, pnl)
        if triggered_by:
            recent = await self.store.recent_events(since_minutes=24 * 60, limit=200)
            for ev in recent:
                if ev.id == triggered_by:
                    self.credibility.update(ev.source_handle, won=pnl > 0)
                    break
        metrics.equity(self.bankroll.equity)

    async def _on_chain_payout(self, payout) -> None:
        """Called when ChainSettlementReader sees a PayoutRedemption for our funder."""
        logger.info("chain_payout_observed",
                    condition_id=payout.condition_id,
                    payout_usdc=payout.payout_usdc,
                    tx=payout.tx_hash)
        # Production hook: look up the condition_id → market_id, overwrite the
        # synthetic settlement row with the realised payout. Left as a TODO
        # because mapping requires the on-chain conditionId index built at
        # market creation time, which py-clob-client exposes per-market.


def cli() -> None:
    parser = argparse.ArgumentParser(prog="osint-trader")
    parser.add_argument("--log-level", default=None, help="DEBUG/INFO/WARNING")
    args = parser.parse_args()
    settings = get_settings()
    configure_logging(args.log_level or settings.log_level)
    asyncio.run(Orchestrator().run())


if __name__ == "__main__":
    cli()
