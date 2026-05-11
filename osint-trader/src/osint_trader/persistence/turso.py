"""Optional Turso libSQL adapter for cross-invocation state.

Turso is SQLite-over-HTTP/2 with a generous free tier (9 GB, 1 billion row
reads/month). When running stateless ticks in GitHub Actions / Modal / Fly
scheduled machines, point DATABASE_URL at a Turso URL so SQLite state
survives between invocations without committing the .db file back to the
repo.

Activation: install `libsql-experimental`, set TURSO_DATABASE_URL and
TURSO_AUTH_TOKEN env vars; this module re-routes Store opens accordingly.

Reference: https://docs.turso.tech/sdk/python
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator


def turso_url() -> str | None:
    return os.getenv("TURSO_DATABASE_URL")


def turso_auth() -> str | None:
    return os.getenv("TURSO_AUTH_TOKEN")


def is_configured() -> bool:
    return bool(turso_url() and turso_auth())


@asynccontextmanager
async def connect() -> AsyncIterator[object]:
    """Open a libSQL connection. Imported lazily so the dep stays optional."""
    try:
        import libsql_experimental as libsql
    except ImportError as exc:
        raise RuntimeError(
            "Turso configured but `libsql-experimental` not installed. "
            "Run: pip install libsql-experimental"
        ) from exc
    conn = libsql.connect(turso_url(), auth_token=turso_auth())
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            pass
