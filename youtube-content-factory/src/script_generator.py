"""Generate niche analysis + per-video scripts via Claude.

Returns structured Pydantic objects so downstream stages (voiceover, image gen,
SEO) get typed data instead of having to parse free-form text.
"""
from __future__ import annotations

import logging
from typing import List

import anthropic
from pydantic import BaseModel, Field

log = logging.getLogger("yt_factory.script")

MODEL = "claude-opus-4-7"

# Static system prompt — first thing in the request, eligible for prompt cache.
NICHE_ANALYST_SYSTEM = """You are an expert YouTube channel strategist and scriptwriter.

Your job has two modes:
1. CONTENT PLANNING: Given a niche and a target market, produce a list of
   high-CTR video ideas optimized for that market's CPM and search behavior.
2. SCRIPT WRITING: Given a single video idea, produce a fully structured
   shooting script broken into scenes. Every scene contains:
   - narrator: what the voiceover says (natural spoken English, no markdown)
   - visual: bracketed direction for what the viewer sees on screen
   - image_prompt: a detailed prompt suitable for DALL-E 3 / Midjourney /
     Microsoft Designer to generate the B-roll image for this scene
     (cinematic, specific, no text on image)

Constraints:
- Hook the viewer in the first 8 seconds.
- Match the requested market (US/EU expectations for pacing and references).
- Match the requested length: ~150 spoken words per minute.
- Keep narrator lines self-contained — they will be voiced one at a time.
- Never include speaker labels, music cues, or markdown in narrator text."""


class VideoIdea(BaseModel):
    title: str = Field(description="High-CTR YouTube title (under 70 chars).")
    angle: str = Field(description="One-sentence hook / unique angle.")
    target_keyword: str = Field(description="Primary SEO keyword.")
    estimated_search_intent: str = Field(
        description="Why people search for this — informational, comparison, etc."
    )


class ContentPlan(BaseModel):
    niche: str
    market: str
    ideas: List[VideoIdea] = Field(min_length=1)


class Scene(BaseModel):
    scene_number: int = Field(ge=1)
    narrator: str = Field(min_length=1)
    visual: str = Field(min_length=1)
    image_prompt: str = Field(min_length=1)


class VideoScript(BaseModel):
    title: str
    hook: str = Field(description="The first 8-second hook line.")
    target_minutes: int = Field(ge=1)
    scenes: List[Scene] = Field(min_length=3)


class ScriptGenerator:
    def __init__(self, api_key: str):
        self._client = anthropic.Anthropic(api_key=api_key)

    def plan(self, niche: str, market: str, num_videos: int = 10) -> ContentPlan:
        log.info("Planning %d videos for niche=%r market=%r", num_videos, niche, market)
        user = (
            f"NICHE: {niche}\n"
            f"MARKET: {market}\n"
            f"TASK: Produce a content plan of {num_videos} video ideas. "
            "Optimize for CTR and search intent in the target market."
        )
        return self._parse(user, ContentPlan).model_copy(
            update={"niche": niche, "market": market}
        )

    def script(self, idea: VideoIdea, target_minutes: int) -> VideoScript:
        log.info("Writing %d-minute script for: %s", target_minutes, idea.title)
        user = (
            f"VIDEO TITLE: {idea.title}\n"
            f"ANGLE: {idea.angle}\n"
            f"TARGET KEYWORD: {idea.target_keyword}\n"
            f"SEARCH INTENT: {idea.estimated_search_intent}\n"
            f"TARGET LENGTH: {target_minutes} minutes "
            f"(~{target_minutes * 150} spoken words total)\n"
            "TASK: Write the full structured script."
        )
        return self._parse(user, VideoScript)

    def _parse(self, user_text: str, schema):
        # Adaptive thinking lets Claude reason as deeply as the task warrants;
        # cache_control on the system prompt makes repeated calls (e.g. 10
        # script generations from one plan) ~90% cheaper on the system tokens.
        response = self._client.messages.parse(
            model=MODEL,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            system=[
                {
                    "type": "text",
                    "text": NICHE_ANALYST_SYSTEM,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_text}],
            output_format=schema,
        )
        if response.parsed_output is None:
            raise RuntimeError(
                f"Claude returned unparseable output. stop_reason={response.stop_reason}"
            )
        log.debug(
            "usage: in=%d out=%d cache_read=%d cache_write=%d",
            response.usage.input_tokens,
            response.usage.output_tokens,
            response.usage.cache_read_input_tokens or 0,
            response.usage.cache_creation_input_tokens or 0,
        )
        return response.parsed_output
