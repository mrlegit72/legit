"""Remote kill switch via Telegram bot polling.

The orchestrator checks `is_active()` before placing any new trades. Toggling
is done by sending /halt or /resume to the alert bot from an authorised
chat_id (defaults to TELEGRAM_ALERT_CHAT_ID).
"""
from __future__ import annotations

import asyncio

import httpx

from . import get_logger
from . import metrics

logger = get_logger(__name__)


class KillSwitch:
    def __init__(self, bot_token: str, authorized_chat_id: str) -> None:
        self.bot_token = bot_token
        self.authorized_chat_id = str(authorized_chat_id) if authorized_chat_id else ""
        self._active = False
        self._offset = 0
        self._http = httpx.AsyncClient(timeout=35)

    @property
    def enabled(self) -> bool:
        return bool(self.bot_token and self.authorized_chat_id)

    def is_active(self) -> bool:
        return self._active

    def force(self, active: bool) -> None:
        self._active = active
        metrics.kill_switch(active)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def run(self, stop_event: asyncio.Event) -> None:
        if not self.enabled:
            logger.info("kill_switch_disabled")
            return
        logger.info("kill_switch_listening")
        while not stop_event.is_set():
            try:
                await self._poll_once()
            except Exception as exc:
                logger.warning("kill_switch_poll_failed", error=str(exc))
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=5)
                except asyncio.TimeoutError:
                    pass

    async def _poll_once(self) -> None:
        url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
        resp = await self._http.get(url, params={"offset": self._offset, "timeout": 25})
        resp.raise_for_status()
        data = resp.json()
        for upd in data.get("result", []):
            self._offset = max(self._offset, upd.get("update_id", 0) + 1)
            msg = upd.get("message") or {}
            chat_id = str((msg.get("chat") or {}).get("id", ""))
            text = (msg.get("text") or "").strip().lower()
            if chat_id != self.authorized_chat_id:
                continue
            if text == "/halt":
                self.force(True)
                logger.warning("kill_switch_halt")
                await self._reply("⛔ Trading halted. Send /resume to re-enable.")
            elif text == "/resume":
                self.force(False)
                logger.info("kill_switch_resume")
                await self._reply("✅ Trading resumed.")
            elif text == "/status":
                await self._reply(f"kill_switch_active={self._active}")

    async def _reply(self, text: str) -> None:
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            await self._http.post(url, json={"chat_id": self.authorized_chat_id, "text": text})
        except Exception:
            pass
