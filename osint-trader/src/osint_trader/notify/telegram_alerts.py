"""Telegram alert client (Bot API) with tiered routing + optional digest.

Tiers:
  info       — every analyst signal, even if risk drops it. Useful for tuning.
  actionable — passed sizing, will trade in non-dry_run modes.
  executed   — order outcome (filled/rejected/error/dry_run).
  position   — exits (take_profit/stop_loss/max_hold) with realised PnL.

When `digest_window_s > 0`, signal alerts within the window for the same
market collapse into a single digest message.
"""
from __future__ import annotations

from typing import Literal

import httpx

from ..models import NewsEvent, Signal, TradeIntent, TradeResult
from ..observability import get_logger
from .digest import AlertDigest

logger = get_logger(__name__)

Tier = Literal["info", "actionable", "executed", "position"]
_TIER_RANK = {"info": 0, "actionable": 1, "executed": 2, "position": 3}


class TelegramAlerter:
    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        min_tier: Tier = "actionable",
        digest_window_s: float = 0.0,
    ) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.min_tier = min_tier
        self._http = httpx.AsyncClient(timeout=10)
        self._digest = AlertDigest(self._send, window_seconds=digest_window_s) if digest_window_s > 0 else None

    async def aclose(self) -> None:
        if self._digest is not None:
            await self._digest.aclose()
        await self._http.aclose()

    @property
    def enabled(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def _emits(self, tier: Tier) -> bool:
        return self.enabled and _TIER_RANK[tier] >= _TIER_RANK[self.min_tier]

    async def signal_alert(
        self,
        event: NewsEvent,
        signal: Signal,
        summary: str,
        *,
        actionable: bool,
        skip_reason: str | None = None,
    ) -> None:
        tier: Tier = "actionable" if actionable else "info"
        if not self._emits(tier):
            return
        if self._digest is not None:
            self._digest.queue(event, signal, summary, actionable, skip_reason)
            return
        emoji = self._tier_emoji(signal.confidence)
        flag = "" if actionable else f"  _(skipped: `{skip_reason}`)_"
        text = (
            f"{emoji} *Signal*: {signal.market_id}{flag}\n"
            f"side: *{signal.side.upper()}*  prob_yes: `{signal.prob_yes:.2f}`  "
            f"edge: `{signal.edge:+.2f}`  conf: `{signal.confidence}`\n"
            f"\n_summary_: {summary or event.text[:140]}\n"
            f"_why_: {signal.reasoning}\n"
            f"_source_: {event.source_kind}/{event.source_handle}"
        )
        await self._send(text)

    async def trade_alert(self, intent: TradeIntent, result: TradeResult) -> None:
        if not self._emits("executed"):
            return
        status_emoji = {"dry_run": "🧪", "filled": "✅", "rejected": "🚫", "error": "⚠️"}.get(result.status, "•")
        text = (
            f"{status_emoji} *Trade {result.status}*: {intent.slug}\n"
            f"side: *{intent.side.upper()}*  price: `{intent.price:.3f}`  "
            f"size: `${intent.size_usdc:.2f}`  edge: `{intent.edge:+.3f}`  "
            f"conf: `{intent.confidence}`  kelly: `{intent.kelly_fraction_used:.3f}`"
        )
        if result.error:
            text += f"\nerror: `{result.error[:200]}`"
        await self._send(text)

    async def position_alert(
        self, intent: TradeIntent, reason: str, exit_price: float, pnl_usdc: float,
    ) -> None:
        if not self._emits("position"):
            return
        emoji = "💰" if pnl_usdc > 0 else "💸"
        text = (
            f"{emoji} *Closed*: {intent.slug}  ({reason})\n"
            f"side: *{intent.side.upper()}*  exit: `{exit_price:.3f}`  "
            f"pnl: `${pnl_usdc:+.2f}`"
        )
        await self._send(text)

    async def kill_switch_alert(self, halted: bool) -> None:
        if not self.enabled:
            return
        text = "⛔ *Trading halted* via /halt" if halted else "✅ *Trading resumed* via /resume"
        await self._send(text)

    @staticmethod
    def _tier_emoji(confidence: int) -> str:
        if confidence >= 90:
            return "🔥🔥"
        if confidence >= 80:
            return "🔥"
        if confidence >= 70:
            return "📡"
        return "•"

    async def _send(self, text: str) -> None:
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            resp = await self._http.post(
                url,
                json={"chat_id": self.chat_id, "text": text, "parse_mode": "Markdown",
                      "disable_web_page_preview": True},
            )
            if resp.status_code != 200:
                logger.warning("alert_send_failed", status=resp.status_code, body=resp.text[:200])
        except Exception as exc:
            logger.warning("alert_send_error", error=str(exc))
