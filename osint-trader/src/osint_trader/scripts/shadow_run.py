"""Daily shadow run: replay yesterday's events, compare signal distribution.

Run as a cron job:
    osint-shadow-run

Compares today's signal distribution against the previous baseline. Exits 1
if drift_alerts is non-empty so monitoring catches it.
"""
from __future__ import annotations

import asyncio
import sys

from rich.console import Console
from rich.table import Table

from ..analysis.drift_monitor import compute_drift
from ..config import get_settings

console = Console()


async def run() -> int:
    settings = get_settings()
    db_path = settings.database_url.split("///", 1)[-1]
    report = await compute_drift(db_path)

    table = Table(title=f"Drift report: last {report.window_hours}h")
    for col in ("metric", "value"):
        table.add_column(col)
    table.add_row("events", str(report.n_events))
    table.add_row("signals", str(report.n_signals))
    table.add_row("signals/event", f"{report.signal_rate_per_event:.3f}")
    table.add_row("mean confidence", f"{report.mean_confidence:.1f}")
    console.print(table)

    if report.alerts:
        console.print("[red]ALERTS:")
        for a in report.alerts:
            console.print(f"  • {a}")
        return 1
    console.print("[green]no drift detected")
    return 0


def cli() -> None:
    sys.exit(asyncio.run(run()))


if __name__ == "__main__":
    cli()
