"""Shared helpers: logging, slugging, file I/O."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from rich.logging import RichHandler


def setup_logging(level: str = "INFO") -> logging.Logger:
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
    )
    return logging.getLogger("yt_factory")


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str, max_len: int = 60) -> str:
    text = text.lower().strip()
    text = _SLUG_RE.sub("-", text).strip("-")
    return text[:max_len] or "untitled"


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
