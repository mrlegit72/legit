"""Render a finished YouTube thumbnail (1280x720) from a SeoBundle concept.

Pipeline: DALL-E generates the background → PIL overlays the headline
in big bold text with a contrast stroke. One file in `output/<slug>/`,
ready to upload.
"""
from __future__ import annotations

import logging
import textwrap
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from .image_gen import ImageGenerator

log = logging.getLogger("yt_factory.thumbnail")

THUMB_SIZE = (1280, 720)


def _find_bold_font() -> Optional[Path]:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return Path(path)
    return None


def _load_font(size: int) -> ImageFont.ImageFont:
    path = _find_bold_font()
    if path is None:
        log.warning("No bold TTF found; falling back to Pillow default font.")
        return ImageFont.load_default()
    return ImageFont.truetype(str(path), size=size)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> str:
    # Binary-search the largest wrap width that fits.
    for width in range(40, 6, -2):
        wrapped = textwrap.fill(text, width=width)
        bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=8)
        if bbox[2] - bbox[0] <= max_width:
            return wrapped
    return textwrap.fill(text, width=10)


def render(
    image_gen: ImageGenerator,
    headline: str,
    visual_description: str,
    out_path: Path,
) -> Path:
    """Generate a thumbnail PNG. Charges one DALL-E call."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    bg_path = out_path.with_suffix(".bg.png")
    image_gen.generate(
        prompt=(
            f"YouTube thumbnail background, no text, no letters: "
            f"{visual_description}. High contrast, dramatic lighting, "
            "leaving the left third visually quieter for text overlay."
        ),
        out_path=bg_path,
    )

    img = Image.open(bg_path).convert("RGB").resize(THUMB_SIZE)
    draw = ImageDraw.Draw(img)
    font = _load_font(size=110)
    text = _wrap(draw, headline.upper(), font, max_width=THUMB_SIZE[0] - 80)

    # Centered vertically on the left ~70% of the frame.
    bbox = draw.multiline_textbbox((0, 0), text, font=font, spacing=10)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = 40
    y = (THUMB_SIZE[1] - text_h) // 2

    draw.multiline_text(
        (x, y),
        text,
        font=font,
        fill=(255, 235, 59),  # YouTube-yellow
        stroke_width=8,
        stroke_fill=(0, 0, 0),
        spacing=10,
    )
    img.save(out_path, "PNG", optimize=True)
    bg_path.unlink(missing_ok=True)
    log.info("Saved thumbnail: %s", out_path)
    return out_path
