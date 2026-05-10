"""SEO metadata: title variants, description, thumbnail concepts."""
from __future__ import annotations

import logging
from typing import List

import anthropic
from pydantic import BaseModel, Field

log = logging.getLogger("yt_factory.seo")

MODEL = "claude-opus-4-7"

SEO_SYSTEM = """You are a YouTube SEO specialist focused on US/EU markets.

You write titles that achieve >10% CTR by using curiosity gaps, numbers,
and the primary keyword early. You write descriptions that rank in YouTube
search by leading with the keyword and including secondary phrases naturally.

Never use clickbait that misrepresents the video. Never invent statistics."""


class ThumbnailConcept(BaseModel):
    headline_text: str = Field(description="2-5 words, big bold text on the thumbnail.")
    visual_description: str = Field(description="What the thumbnail image shows.")


class SeoBundle(BaseModel):
    titles: List[str] = Field(min_length=3, description="Title A/B variants.")
    description: str = Field(description="Full YouTube description with keywords.")
    tags: List[str] = Field(min_length=5)
    thumbnail_concepts: List[ThumbnailConcept] = Field(min_length=3)


class SeoGenerator:
    def __init__(self, api_key: str):
        self._client = anthropic.Anthropic(api_key=api_key)

    def generate(self, video_title: str, keywords: List[str], summary: str) -> SeoBundle:
        log.info("Generating SEO bundle for: %s", video_title)
        user = (
            f"VIDEO TITLE: {video_title}\n"
            f"PRIMARY + SECONDARY KEYWORDS: {', '.join(keywords)}\n"
            f"VIDEO SUMMARY: {summary}\n\n"
            "Produce: 5 title variants targeting >10% CTR, a full YouTube "
            "description (~200 words) with keywords woven in naturally, "
            "10 tags, and 5 thumbnail concepts."
        )
        response = self._client.messages.parse(
            model=MODEL,
            max_tokens=8000,
            thinking={"type": "adaptive"},
            output_config={"effort": "medium"},
            system=[
                {
                    "type": "text",
                    "text": SEO_SYSTEM,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user}],
            output_format=SeoBundle,
        )
        if response.parsed_output is None:
            raise RuntimeError(f"SEO parse failed. stop_reason={response.stop_reason}")
        return response.parsed_output
