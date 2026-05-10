"""Find affiliate programs for the tools/products mentioned in a script.

Note: Claude returns *suggestions* based on its training data. Always verify
the program is still open and the commission terms are current before relying
on a link in production. This module flags that for the user explicitly.
"""
from __future__ import annotations

import logging
from typing import List

import anthropic
from pydantic import BaseModel, Field

log = logging.getLogger("yt_factory.affiliate")

MODEL = "claude-opus-4-7"

AFFILIATE_SYSTEM = """You are a monetization analyst for YouTube creators.

Given a list of tools or products mentioned in a video, suggest known
affiliate programs that pay creators when viewers sign up via referral link.

Be conservative: only suggest programs you have high confidence existed and
were creator-accessible. Flag uncertainty explicitly. Never invent commission
rates — if you're not sure, say so."""


class AffiliateProgram(BaseModel):
    tool_or_product: str
    program_name: str
    sign_up_hint: str = Field(
        description="Where to find the program — e.g. 'search Impact.com for X'."
    )
    typical_commission: str = Field(
        description="Typical payout. Use ranges, not exact figures, and mark "
        "with 'verify' if uncertain."
    )
    confidence: str = Field(description="high | medium | low")


class AffiliateReport(BaseModel):
    programs: List[AffiliateProgram]
    disclaimer: str = Field(
        description="Reminder that creator must verify each program before use."
    )


class AffiliateFinder:
    def __init__(self, api_key: str):
        self._client = anthropic.Anthropic(api_key=api_key)

    def find(self, tools_mentioned: List[str], niche: str) -> AffiliateReport:
        log.info("Researching affiliate programs for %d tools", len(tools_mentioned))
        user = (
            f"NICHE: {niche}\n"
            f"TOOLS / PRODUCTS MENTIONED: {', '.join(tools_mentioned)}\n\n"
            "List affiliate programs the creator could realistically apply to. "
            "Mark each with confidence and a sign-up hint."
        )
        response = self._client.messages.parse(
            model=MODEL,
            max_tokens=4000,
            thinking={"type": "adaptive"},
            output_config={"effort": "medium"},
            system=[
                {
                    "type": "text",
                    "text": AFFILIATE_SYSTEM,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user}],
            output_format=AffiliateReport,
        )
        if response.parsed_output is None:
            raise RuntimeError(
                f"Affiliate parse failed. stop_reason={response.stop_reason}"
            )
        return response.parsed_output
