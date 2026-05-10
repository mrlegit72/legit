"""Domain models passed between sources, analyst, risk, and execution."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


class NewsEvent(BaseModel):
    """A single OSINT item normalized to English-friendly form before analysis."""
    id: str                                    # stable hash; used for dedup
    source_kind: Literal["telegram", "rss", "gdelt", "nitter"]
    source_handle: str                         # channel name / feed URL / etc.
    credibility: float = 0.5                   # 0..1, from sources.yaml
    language: str = "en"
    text: str
    url: str | None = None
    fetched_at: datetime = Field(default_factory=_now)
    published_at: datetime | None = None


class MarketSnapshot(BaseModel):
    """Live state of a Polymarket market, fed to the analyst as context."""
    market_id: str
    slug: str
    title: str
    yes_price: float                           # 0..1, mid-price for YES side
    no_price: float
    liquidity_usdc: float = 0.0
    volume_24h_usdc: float = 0.0
    yes_token_id: str | None = None
    no_token_id: str | None = None


class Signal(BaseModel):
    """Analyst output for a single market."""
    market_id: str
    side: Literal["yes", "no"]
    prob_yes: float                            # analyst's posterior estimate
    edge: float                                # post - market mid (signed)
    confidence: int                            # 0..100
    reasoning: str
    triggered_by_event_id: str
    created_at: datetime = Field(default_factory=_now)


class AnalystVerdict(BaseModel):
    summary_en: str
    is_propaganda_risk: bool = False
    signals: list[Signal] = Field(default_factory=list)


class TradeIntent(BaseModel):
    """Risk-sized trade ready to be executed (or simulated)."""
    market_id: str
    slug: str
    side: Literal["yes", "no"]
    token_id: str | None
    price: float                               # limit price
    size_usdc: float
    edge: float
    confidence: int
    kelly_fraction_used: float
    reasoning: str
    signal_created_at: datetime
    created_at: datetime = Field(default_factory=_now)


class TradeResult(BaseModel):
    intent: TradeIntent
    status: Literal["dry_run", "filled", "rejected", "error"]
    fill_price: float | None = None
    filled_size_usdc: float | None = None
    order_id: str | None = None
    error: str | None = None
    executed_at: datetime = Field(default_factory=_now)
