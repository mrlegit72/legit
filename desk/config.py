"""Desk rules. Frozen on purpose: paper and live run the exact same numbers.

There is no CLI flag or env var that changes these. Editing this file is the
only way, and that shows up in git.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Rules:
    # SCOUT
    min_age_min: float = 30
    max_age_h: float = 72
    min_mcap: float = 300_000
    max_mcap: float = 20_000_000
    dexes: tuple = ("raydium", "pumpswap", "pumpfun")

    # FILTER (kill rules)
    min_liquidity: float = 40_000
    min_vol_1h: float = 50_000
    max_top10_pct: float = 25
    max_dev_pct: float = 3
    max_bundled_pct: float = 10
    max_change_1h_pct: float = 80

    # ANALYST
    min_score: int = 70

    # EXECUTOR
    max_trade_pct: float = 8

    # RISK
    stop_pct: float = -6
    trail_trigger_pct: float = 12
    trail_distance_pct: float = 6  # trail sits this far below the peak once armed


RULES = Rules()

KILL_RULES = {
    1: "mint or freeze authority not revoked",
    2: "LP not burned or locked",
    3: "liquidity under $40k",
    4: "1h volume under $50k",
    5: "top 10 holders own more than 25%",
    6: "dev wallet holds more than 3% or dev has past rugs",
    7: "bundled launch over 10%",
    8: "already up 80%+ in the last hour",
}


@dataclass(frozen=True)
class Runtime:
    """Operational knobs. None of these affect what gets killed or traded."""
    scan_every_s: int = 60
    position_poll_s: int = 15
    holder_resample_min: float = 5   # analyst waits for a second holder count this far apart
    paper_slippage_pct: float = 1.0  # applied on both entry and exit in paper mode
