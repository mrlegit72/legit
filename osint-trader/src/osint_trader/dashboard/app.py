"""Minimal FastAPI dashboard.

Endpoints:
  GET /                 → HTML overview (open positions, today's PnL, last 20 signals)
  GET /api/positions    → JSON
  GET /api/signals      → JSON
  GET /api/credibility  → JSON (current learned credibility per source)
  GET /api/drift        → JSON (DriftReport)

Run:
    pip install -e ".[dashboard]"
    uvicorn osint_trader.dashboard.app:app --host 127.0.0.1 --port 9109
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import aiosqlite

from ..analysis.drift_monitor import compute_drift
from ..config import get_settings


def create_app():
    try:
        from fastapi import FastAPI
        from fastapi.responses import HTMLResponse
    except ImportError as exc:
        raise RuntimeError("install with `pip install -e \".[dashboard]\"`") from exc

    settings = get_settings()
    db_path = settings.database_url.split("///", 1)[-1]
    app = FastAPI(title="osint-trader")

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        positions = await _open_positions(db_path)
        pnl = await _today_pnl(db_path)
        signals = await _recent_signals(db_path, limit=20)
        return _render_html(positions, pnl, signals)

    @app.get("/api/positions")
    async def api_positions() -> list[dict]:
        return await _open_positions(db_path)

    @app.get("/api/signals")
    async def api_signals() -> list[dict]:
        return await _recent_signals(db_path, limit=100)

    @app.get("/api/credibility")
    async def api_credibility() -> dict:
        return await _credibility(db_path)

    @app.get("/api/drift")
    async def api_drift() -> dict:
        report = await compute_drift(db_path)
        return report.__dict__

    return app


app = None  # populated by uvicorn if you import via app:app


def __getattr__(name: str):
    global app
    if name == "app":
        if app is None:
            app = create_app()
        return app
    raise AttributeError(name)


async def _open_positions(db_path: str) -> list[dict]:
    """Open = trade with no later settlement on the same market."""
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            """SELECT t.market_id, t.side, t.price, t.size_usdc, t.executed_at
               FROM trades t
               LEFT JOIN settlements s
                 ON s.market_id = t.market_id AND s.settled_at > t.executed_at
               WHERE t.status IN ('filled', 'dry_run') AND s.id IS NULL
               ORDER BY t.executed_at DESC"""
        ) as cur:
            rows = await cur.fetchall()
    return [{"market_id": r[0], "side": r[1], "price": r[2],
             "size_usdc": r[3], "executed_at": r[4]} for r in rows]


async def _today_pnl(db_path: str) -> float:
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT COALESCE(SUM(pnl_usdc), 0) FROM settlements WHERE settled_at >= ?",
            (start,),
        ) as cur:
            row = await cur.fetchone()
    return float(row[0] if row else 0.0)


async def _recent_signals(db_path: str, *, limit: int) -> list[dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            """SELECT market_id, side, prob_yes, edge, confidence, reasoning, created_at
               FROM signals WHERE created_at >= ?
               ORDER BY created_at DESC LIMIT ?""",
            (cutoff, limit),
        ) as cur:
            rows = await cur.fetchall()
    return [{"market_id": r[0], "side": r[1], "prob_yes": r[2], "edge": r[3],
             "confidence": r[4], "reasoning": r[5], "created_at": r[6]} for r in rows]


async def _credibility(db_path: str) -> dict:
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            """SELECT e.source_handle,
                      SUM(CASE WHEN s.pnl_usdc > 0 THEN 1 ELSE 0 END) AS wins,
                      SUM(CASE WHEN s.pnl_usdc <= 0 THEN 1 ELSE 0 END) AS losses
               FROM settlements s
               JOIN events e ON e.id = s.triggered_by_event_id
               GROUP BY e.source_handle
               ORDER BY wins DESC"""
        ) as cur:
            rows = await cur.fetchall()
    return {r[0]: {"wins": r[1], "losses": r[2],
                   "rate": (r[1] / max(r[1] + r[2], 1)) if (r[1] + r[2]) else None}
            for r in rows}


def _render_html(positions, pnl, signals) -> str:
    pos_rows = "".join(
        f"<tr><td>{p['market_id']}</td><td>{p['side']}</td>"
        f"<td>{p['price']:.3f}</td><td>${p['size_usdc']:.2f}</td>"
        f"<td>{p['executed_at']}</td></tr>"
        for p in positions
    ) or "<tr><td colspan=5><i>none</i></td></tr>"
    sig_rows = "".join(
        f"<tr><td>{s['market_id']}</td><td>{s['side']}</td>"
        f"<td>{s['prob_yes']:.2f}</td><td>{s['edge']:+.2f}</td>"
        f"<td>{s['confidence']}</td><td>{(s['reasoning'] or '')[:80]}</td>"
        f"<td>{s['created_at']}</td></tr>"
        for s in signals
    ) or "<tr><td colspan=7><i>none</i></td></tr>"
    return f"""<!doctype html>
<html><head><title>osint-trader</title>
<style>
 body {{ font-family: ui-monospace, monospace; max-width: 1100px; margin: 2em auto; }}
 h1, h2 {{ font-weight: 500; }} h1 {{ font-size: 1.5em; }} h2 {{ font-size: 1.1em; margin-top:2em; }}
 .pnl {{ font-size: 2em; color: {'green' if pnl >= 0 else 'red'}; }}
 table {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
 th, td {{ border-bottom: 1px solid #eee; padding: 4px 8px; text-align: left; }}
 th {{ background: #f7f7f7; }}
</style></head>
<body>
<h1>osint-trader</h1>
<div>Today PnL: <span class="pnl">${pnl:+.2f}</span></div>
<h2>Open positions</h2>
<table><tr><th>market</th><th>side</th><th>price</th><th>size</th><th>opened</th></tr>{pos_rows}</table>
<h2>Recent signals (last 48h)</h2>
<table><tr><th>market</th><th>side</th><th>prob</th><th>edge</th><th>conf</th><th>why</th><th>at</th></tr>{sig_rows}</table>
<p><small>API: <a href="/api/positions">/api/positions</a> · <a href="/api/signals">/api/signals</a> · <a href="/api/credibility">/api/credibility</a> · <a href="/api/drift">/api/drift</a></small></p>
</body></html>"""
