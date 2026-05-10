"""ElevenLabs text-to-speech with retries and per-scene chunking."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

log = logging.getLogger("yt_factory.voiceover")

API_BASE = "https://api.elevenlabs.io/v1"


class ElevenLabsError(RuntimeError):
    pass


@dataclass
class VoiceInfo:
    voice_id: str
    name: str
    category: str  # "premade" | "cloned" | "professional" | "generated"
    description: str = ""


def list_voices(api_key: str) -> List[VoiceInfo]:
    """List all voices available to this account, including cloned ones.

    Free/Starter tiers see premade voices. ElevenLabs Creator+ tiers get to
    *clone* their own voice — clone in the web UI, then run `pipeline voices`
    to find the new voice_id and paste it into ELEVENLABS_VOICE_ID in .env.
    """
    response = requests.get(
        f"{API_BASE}/voices",
        headers={"xi-api-key": api_key},
        timeout=30,
    )
    if not response.ok:
        raise ElevenLabsError(
            f"ElevenLabs /voices error {response.status_code}: {response.text[:200]}"
        )
    out: List[VoiceInfo] = []
    for v in response.json().get("voices", []):
        out.append(VoiceInfo(
            voice_id=v.get("voice_id", ""),
            name=v.get("name", ""),
            category=v.get("category", ""),
            description=(v.get("description") or "")[:80],
        ))
    return out


class Voiceover:
    def __init__(
        self,
        api_key: str,
        voice_id: str,
        model_id: str = "eleven_multilingual_v2",
        stability: float = 0.5,
        similarity_boost: float = 0.8,
    ):
        self._api_key = api_key
        self._voice_id = voice_id
        self._model_id = model_id
        self._stability = stability
        self._similarity_boost = similarity_boost

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((requests.RequestException, ElevenLabsError)),
        reraise=True,
    )
    def synthesize(self, text: str, out_path: Path) -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        url = f"{API_BASE}/text-to-speech/{self._voice_id}"
        headers = {
            "xi-api-key": self._api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload = {
            "text": text,
            "model_id": self._model_id,
            "voice_settings": {
                "stability": self._stability,
                "similarity_boost": self._similarity_boost,
            },
        }
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        if response.status_code == 401:
            raise ElevenLabsError("Invalid ElevenLabs API key (401).")
        if response.status_code == 429:
            raise ElevenLabsError("ElevenLabs rate limit hit (429) — backing off.")
        if not response.ok:
            raise ElevenLabsError(
                f"ElevenLabs error {response.status_code}: {response.text[:300]}"
            )
        out_path.write_bytes(response.content)
        log.info("Saved audio: %s (%d bytes)", out_path.name, out_path.stat().st_size)
        return out_path

    def synthesize_scenes(
        self, narrator_lines: List[str], out_dir: Path, prefix: str = "scene"
    ) -> List[Path]:
        out_dir.mkdir(parents=True, exist_ok=True)
        paths: List[Path] = []
        for i, line in enumerate(narrator_lines, start=1):
            out_path = out_dir / f"{prefix}_{i:02d}.mp3"
            paths.append(self.synthesize(line, out_path))
        return paths
