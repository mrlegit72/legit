"""Settings & config loaders.

All secrets come from env vars (loaded via pydantic-settings); market and source
definitions come from YAML so non-Python users can edit them.
"""
from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]   # .../osint-trader/src/osint_trader -> .../osint-trader
CONFIG_DIR = REPO_ROOT / "config"


class TradeMode(str, Enum):
    DRY_RUN = "dry_run"   # log only
    PAPER = "paper"       # simulate fills, persist as if real
    LIVE = "live"         # send real orders to Polymarket CLOB


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-7"
    anthropic_fast_model: str = "claude-haiku-4-5-20251001"

    # --- Telegram (OSINT ingestion)
    telegram_api_id: int | None = None
    telegram_api_hash: str = ""
    telegram_session_name: str = "osint_session"

    # --- Telegram (alerts)
    telegram_bot_token: str = ""
    telegram_alert_chat_id: str = ""

    # --- Polymarket
    polymarket_clob_host: str = "https://clob.polymarket.com"
    polymarket_gamma_host: str = "https://gamma-api.polymarket.com"
    polymarket_private_key: str = ""
    polymarket_funder: str = ""

    # --- Risk
    trade_mode: TradeMode = TradeMode.DRY_RUN
    bankroll_usdc: float = 500.0
    max_position_pct: float = 0.05
    min_edge: float = 0.05
    min_confidence: int = 80
    kelly_fraction: float = 0.25
    daily_loss_limit_pct: float = 0.15

    # --- Storage
    database_url: str = "sqlite+aiosqlite:///./osint_trader.db"
    log_level: str = "INFO"


# ---------- YAML configs ----------

class MarketConfig(BaseModel):
    market_id: str
    slug: str
    title: str
    keywords: list[str] = Field(default_factory=list)
    escalation_direction: str = "no"  # "yes" or "no"
    timeframe_days: int = 30


class TelegramChannel(BaseModel):
    handle: str
    credibility: float = 0.5
    language: str = "en"


class RSSFeed(BaseModel):
    url: str
    credibility: float = 0.5
    language: str = "en"


class GDELTConfig(BaseModel):
    enabled: bool = False
    query: str = ""
    poll_seconds: int = 180
    credibility: float = 0.7


class NitterConfig(BaseModel):
    enabled: bool = False
    base: str = ""
    handles: list[str] = Field(default_factory=list)
    poll_seconds: int = 120
    credibility: float = 0.4


class SourcesConfig(BaseModel):
    telegram_channels: list[TelegramChannel] = Field(default_factory=list)
    rss_feeds: list[RSSFeed] = Field(default_factory=list)
    gdelt: GDELTConfig = Field(default_factory=GDELTConfig)
    nitter: NitterConfig = Field(default_factory=NitterConfig)


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def load_markets(path: Path | None = None) -> list[MarketConfig]:
    path = path or (CONFIG_DIR / "markets.yaml")
    data = yaml.safe_load(path.read_text())
    return [MarketConfig(**m) for m in data.get("markets", [])]


@lru_cache
def load_sources(path: Path | None = None) -> SourcesConfig:
    path = path or (CONFIG_DIR / "sources.yaml")
    data = yaml.safe_load(path.read_text())
    return SourcesConfig(
        telegram_channels=[TelegramChannel(**c) for c in (data.get("telegram", {}) or {}).get("channels", [])],
        rss_feeds=[RSSFeed(**f) for f in (data.get("rss", {}) or {}).get("feeds", [])],
        gdelt=GDELTConfig(**(data.get("gdelt") or {})),
        nitter=NitterConfig(**(data.get("nitter") or {})),
    )


def load_analyst_prompt() -> str:
    return (CONFIG_DIR / "prompts" / "analyst.md").read_text()
