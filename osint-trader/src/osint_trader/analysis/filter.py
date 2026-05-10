"""Cheap pre-filter that decides whether an event is even worth Claude tokens.

Strategy: substring/keyword scan against `markets.yaml` keywords and the
market titles themselves. Anything that scores zero is dropped before we pay
for inference. Tunable but conservative.
"""
from __future__ import annotations

from ..config import MarketConfig


def is_relevant_to_any_market(text: str, markets: list[MarketConfig]) -> bool:
    lowered = text.lower()
    for m in markets:
        if any(k.lower() in lowered for k in m.keywords):
            return True
        # Title words are also useful — split & match on >=4 char tokens.
        tokens = [t for t in m.title.lower().split() if len(t) >= 4]
        if any(t in lowered for t in tokens):
            return True
    # Keep the global Iran/Israel umbrella so generic-but-relevant items pass
    umbrella = ("iran", "israel", "hormuz", "kharg", "tehran", "irgc", "khamenei", "houthi")
    return any(k in lowered for k in umbrella)
