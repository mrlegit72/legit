"""Prometheus metrics + tiny HTTP server.

Exports:
    osint_events_total{source}          : counter, raw events received
    osint_events_dropped_total{reason}  : counter, dropped (dedup/filter/etc.)
    osint_signals_total{market,side}    : counter, analyst-emitted signals
    osint_trades_total{market,side,status}: counter, sized + executed trades
    osint_claude_latency_seconds        : histogram, end-to-end analyst call
    osint_queue_depth                   : gauge, current event queue size
    osint_bankroll_equity_usdc          : gauge

prometheus_client is optional; if absent, all helpers no-op silently so the
core pipeline never depends on metrics being available.
"""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from typing import Any

from ..observability import get_logger

logger = get_logger(__name__)

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )
    _ENABLED = True
except ImportError:  # pragma: no cover - optional dep
    _ENABLED = False
    CONTENT_TYPE_LATEST = "text/plain; charset=utf-8"

if _ENABLED:
    EVENTS = Counter("osint_events_total", "Raw events received", ["source"])
    EVENTS_DROPPED = Counter("osint_events_dropped_total", "Events dropped", ["reason"])
    SIGNALS = Counter("osint_signals_total", "Analyst signals", ["market", "side"])
    TRADES = Counter("osint_trades_total", "Trade outcomes", ["market", "side", "status"])
    CLAUDE_LATENCY = Histogram("osint_claude_latency_seconds", "Claude analyst latency")
    QUEUE_DEPTH = Gauge("osint_queue_depth", "Event queue depth")
    EQUITY = Gauge("osint_bankroll_equity_usdc", "Bankroll equity")
    KILL_SWITCH = Gauge("osint_kill_switch", "1 = halted")
else:
    EVENTS = EVENTS_DROPPED = SIGNALS = TRADES = CLAUDE_LATENCY = None  # type: ignore
    QUEUE_DEPTH = EQUITY = KILL_SWITCH = None  # type: ignore


def event_received(source: str) -> None:
    if _ENABLED:
        EVENTS.labels(source=source).inc()


def event_dropped(reason: str) -> None:
    if _ENABLED:
        EVENTS_DROPPED.labels(reason=reason).inc()


def signal_emitted(market: str, side: str) -> None:
    if _ENABLED:
        SIGNALS.labels(market=market, side=side).inc()


def trade_recorded(market: str, side: str, status: str) -> None:
    if _ENABLED:
        TRADES.labels(market=market, side=side, status=status).inc()


def queue_depth(n: int) -> None:
    if _ENABLED:
        QUEUE_DEPTH.set(n)


def equity(usdc: float) -> None:
    if _ENABLED:
        EQUITY.set(usdc)


def kill_switch(active: bool) -> None:
    if _ENABLED:
        KILL_SWITCH.set(1 if active else 0)


@contextmanager
def measure_claude():
    if _ENABLED:
        with CLAUDE_LATENCY.time():
            yield
    else:
        yield


def render() -> tuple[bytes, str]:
    if not _ENABLED:
        return b"", CONTENT_TYPE_LATEST
    return generate_latest(), CONTENT_TYPE_LATEST


async def serve_forever(host: str, port: int, stop_event: asyncio.Event) -> None:
    """Serve /metrics from a tiny pure-asyncio HTTP loop. No aiohttp dep."""
    if not _ENABLED:
        logger.info("metrics_disabled", reason="prometheus_client not installed")
        await stop_event.wait()
        return

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            line = await asyncio.wait_for(reader.readline(), timeout=2)
            while True:                  # consume rest of headers
                hdr = await asyncio.wait_for(reader.readline(), timeout=2)
                if hdr in (b"\r\n", b""):
                    break
            if b"GET /metrics" in line:
                payload, ctype = render()
                writer.write(b"HTTP/1.1 200 OK\r\n")
                writer.write(f"Content-Type: {ctype}\r\n".encode())
                writer.write(f"Content-Length: {len(payload)}\r\n\r\n".encode())
                writer.write(payload)
            else:
                writer.write(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")
            await writer.drain()
        except (asyncio.TimeoutError, ConnectionResetError):
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    server = await asyncio.start_server(handle, host=host, port=port)
    logger.info("metrics_listening", host=host, port=port)
    try:
        async with server:
            stop_task = asyncio.create_task(stop_event.wait())
            await asyncio.wait({stop_task}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        server.close()
        await server.wait_closed()


def is_enabled() -> bool:
    return _ENABLED


__all__: list[Any] = [
    "event_received", "event_dropped", "signal_emitted", "trade_recorded",
    "queue_depth", "equity", "kill_switch", "measure_claude", "serve_forever",
    "is_enabled",
]
