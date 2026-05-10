"""Telegram alert client (Bot API).

Used to push human-readable signal/trade alerts to a chat. Pure HTTP — no
Telethon dependency, so it works even when the OSINT Telegram session is
disabled.
"""
from __future__ import annotations

import httpx

from ..models import NewsEvent, Signal, TradeIntent, TradeResult
from ..observability import get_logger

logger = get_logger(__name__)


class TelegramAlerter:
    def __init__(self, bot_token: str, chat_id: str) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self._http = httpx.AsyncClient(timeout=10)

    async def aclose(self) -> None:
        await self._http.aclose()

    @property
    def enabled(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    async def signal_alert(self, event: NewsEvent, signal: Signal, summary: str) -> None:
        if not self.enabled:
            return
        emoji = self._tier_emoji(signal.confidence)
        text = (
            f"{emoji} *Signal*: {signal.market_id}\n"
            f"side: *{signal.side.upper()}*  prob_yes: `{signal.prob_yes:.2f}`  "
            f"edge: `{signal.edge:+.2f}`  conf: `{signal.confidence}`\n"
            f"\n_summary_: {summary or event.text[:140]}\n"
            f"_why_: {signal.reasoning}\n"
            f"_source_: {event.source_kind}/{event.source_handle}"
        )
        await self._send(text)

    async def trade_alert(self, intent: TradeIntent, result: TradeResult) -> None:
        if not self.enabled:
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
