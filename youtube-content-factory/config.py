"""Centralized configuration. Loads from .env, validates required keys."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class ConfigError(RuntimeError):
    pass


def _require(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise ConfigError(
            f"Missing required environment variable: {key}. "
            f"Copy .env.example to .env and fill it in."
        )
    return value


@dataclass(frozen=True)
class Config:
    anthropic_api_key: str
    openai_api_key: str
    elevenlabs_api_key: str
    elevenlabs_voice_id: str
    elevenlabs_model_id: str
    default_niche: str
    default_market: str
    default_video_length_minutes: int
    output_dir: Path

    @classmethod
    def load(cls) -> "Config":
        output_dir = Path(os.getenv("OUTPUT_DIR", "./output")).resolve()
        return cls(
            anthropic_api_key=_require("ANTHROPIC_API_KEY"),
            openai_api_key=_require("OPENAI_API_KEY"),
            elevenlabs_api_key=_require("ELEVENLABS_API_KEY"),
            elevenlabs_voice_id=os.getenv(
                "ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB"
            ),
            elevenlabs_model_id=os.getenv(
                "ELEVENLABS_MODEL_ID", "eleven_multilingual_v2"
            ),
            default_niche=os.getenv("DEFAULT_NICHE", "AI Tools for Productivity"),
            default_market=os.getenv("DEFAULT_MARKET", "US"),
            default_video_length_minutes=int(
                os.getenv("DEFAULT_VIDEO_LENGTH_MINUTES", "8")
            ),
            output_dir=output_dir,
        )

    def ensure_dirs(self) -> None:
        for sub in ("scripts", "audio", "images", "metadata"):
            (self.output_dir / sub).mkdir(parents=True, exist_ok=True)
