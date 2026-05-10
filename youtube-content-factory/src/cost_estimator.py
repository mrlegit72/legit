"""Estimate per-stage spend and print an itemized prompt before charging.

These are *floor* estimates from public list prices. Token counts for
Claude calls are approximated; actual usage may be ±50% depending on the
length the model chooses. The point is to catch the case where you
accidentally run `full` against a 50-video plan.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import List, Tuple


# Public list prices as of writing — adjust if you change models.
DALLE3_HD_16x9_USD = 0.080  # 1792x1024
DALLE3_STANDARD_USD = 0.040  # 1024x1024
WHISPER_USD_PER_MIN = 0.006
CLAUDE_OPUS_INPUT_USD_PER_M = 5.0
CLAUDE_OPUS_OUTPUT_USD_PER_M = 25.0
ELEVENLABS_USD_PER_VIDEO_AMORTIZED = 0.20  # ~$5/mo Starter ÷ 25 videos


@dataclass
class CostLine:
    label: str
    amount_usd: float


@dataclass
class CostEstimate:
    lines: List[CostLine]

    @property
    def total(self) -> float:
        return sum(line.amount_usd for line in self.lines)

    def print_table(self) -> None:
        width = max(len(line.label) for line in self.lines)
        print()
        print(f"  {'Stage'.ljust(width)}    Est. cost")
        print(f"  {'-' * width}    ---------")
        for line in self.lines:
            print(f"  {line.label.ljust(width)}    ${line.amount_usd:0.3f}")
        print(f"  {'-' * width}    ---------")
        print(f"  {'TOTAL'.ljust(width)}    ${self.total:0.3f}")
        print()


def estimate_full_run(
    num_scenes: int,
    target_minutes: int,
    include_subtitles: bool = True,
    include_thumbnail: bool = True,
) -> CostEstimate:
    lines: List[CostLine] = []

    # Claude — script + SEO + affiliate research. Empirical avg ~30k input
    # (mostly cached after the first run) + ~6k output across all calls.
    claude_input_tokens = 30_000
    claude_output_tokens = 6_000
    claude_cost = (
        claude_input_tokens * CLAUDE_OPUS_INPUT_USD_PER_M / 1_000_000
        + claude_output_tokens * CLAUDE_OPUS_OUTPUT_USD_PER_M / 1_000_000
    )
    lines.append(CostLine("Claude (script+SEO+affiliates)", claude_cost))

    # Scene images
    lines.append(CostLine(
        f"DALL-E 3 HD ({num_scenes} scene images)",
        num_scenes * DALLE3_HD_16x9_USD,
    ))

    # ElevenLabs amortized
    lines.append(CostLine("ElevenLabs voiceover (amortized)", ELEVENLABS_USD_PER_VIDEO_AMORTIZED))

    # Whisper subtitles
    if include_subtitles:
        lines.append(CostLine(
            f"Whisper subtitles ({target_minutes} min)",
            target_minutes * WHISPER_USD_PER_MIN,
        ))

    # Thumbnail = 1 extra DALL-E call
    if include_thumbnail:
        lines.append(CostLine("Thumbnail (1 DALL-E HD)", DALLE3_HD_16x9_USD))

    return CostEstimate(lines=lines)


def confirm(estimate: CostEstimate, *, auto_approve: bool = False) -> bool:
    estimate.print_table()
    if auto_approve:
        print("[--approve set, skipping prompt]")
        return True
    if not sys.stdin.isatty():
        # Non-interactive; require explicit --approve to spend money.
        print("Non-interactive shell; pass --approve to proceed.")
        return False
    answer = input("Proceed? [y/N] ").strip().lower()
    return answer in ("y", "yes")
