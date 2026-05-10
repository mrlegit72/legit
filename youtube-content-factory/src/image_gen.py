"""DALL-E 3 image generation via the modern OpenAI SDK.

The legacy `openai.Image.create(...)` shape from the original guide has been
deprecated. This uses `client.images.generate(...)` and downloads the bytes
to disk so the result is usable in Premiere immediately.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List

import requests
from openai import OpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

log = logging.getLogger("yt_factory.image")


class ImageGenerator:
    def __init__(
        self,
        api_key: str,
        model: str = "dall-e-3",
        size: str = "1792x1024",  # 16:9 — matches a YouTube frame
        quality: str = "hd",
        style: str = "vivid",
    ):
        self._client = OpenAI(api_key=api_key)
        self._model = model
        self._size = size
        self._quality = quality
        self._style = style

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def generate(self, prompt: str, out_path: Path) -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        response = self._client.images.generate(
            model=self._model,
            prompt=prompt,
            size=self._size,
            quality=self._quality,
            style=self._style,
            n=1,
        )
        url = response.data[0].url
        if not url:
            raise RuntimeError("OpenAI returned no image URL.")
        img = requests.get(url, timeout=60)
        img.raise_for_status()
        out_path.write_bytes(img.content)
        log.info("Saved image: %s (%d bytes)", out_path.name, out_path.stat().st_size)
        return out_path

    def generate_batch(
        self, prompts: List[str], out_dir: Path, prefix: str = "scene"
    ) -> List[Path]:
        out_dir.mkdir(parents=True, exist_ok=True)
        paths: List[Path] = []
        for i, prompt in enumerate(prompts, start=1):
            out_path = out_dir / f"{prefix}_{i:02d}.png"
            paths.append(self.generate(prompt, out_path))
        return paths
