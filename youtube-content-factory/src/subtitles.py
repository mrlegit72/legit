"""Generate burned-in subtitles via OpenAI Whisper.

`whisper-1` returns SRT-formatted output natively when `response_format="srt"`.
The result file feeds straight into `video_assembler.burn_subtitles`.
"""
from __future__ import annotations

import logging
from pathlib import Path

from openai import OpenAI

log = logging.getLogger("yt_factory.subtitles")


class SubtitleGenerator:
    def __init__(self, api_key: str, model: str = "whisper-1"):
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def transcribe_to_srt(self, audio_path: Path, out_path: Path) -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        log.info("Transcribing %s with Whisper...", audio_path.name)
        with audio_path.open("rb") as f:
            srt_text = self._client.audio.transcriptions.create(
                model=self._model,
                file=f,
                response_format="srt",
            )
        # The SDK returns either a str or an object with .text depending on
        # response_format; "srt" returns the raw string.
        if not isinstance(srt_text, str):
            srt_text = getattr(srt_text, "text", str(srt_text))
        out_path.write_text(srt_text, encoding="utf-8")
        log.info("Wrote SRT: %s (%d chars)", out_path.name, len(srt_text))
        return out_path
