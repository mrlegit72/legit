"""Music bed: optional Pixabay search + ffmpeg duck-mix under the VO.

Two paths:
  1. `--music PATH` — point at a local audio file you already trust.
  2. `--music-query "uplifting corporate"` + PIXABAY_API_KEY in env — pulls
     a CC0 track from Pixabay's free music endpoint.

The mix uses ffmpeg's `sidechaincompress` filter so the music *ducks* under
the voice automatically: as soon as the narrator speaks, music drops ~12dB;
when they pause, music rises back up. Far better than a static -18dB bed.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

import requests

log = logging.getLogger("yt_factory.music")

PIXABAY_MUSIC_ENDPOINT = "https://pixabay.com/api/music/"


class MusicError(RuntimeError):
    pass


def _require_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise MusicError("ffmpeg not found on PATH.")


def search_pixabay(
    query: str, out_path: Path, api_key: Optional[str] = None
) -> Path:
    """Download a CC0 music track matching `query` from Pixabay."""
    api_key = api_key or os.getenv("PIXABAY_API_KEY")
    if not api_key:
        raise MusicError(
            "PIXABAY_API_KEY not set — either set it in .env or pass a "
            "local file via --music."
        )
    params = {"key": api_key, "q": query, "per_page": 5}
    log.info("Searching Pixabay music: %r", query)
    r = requests.get(
        f"{PIXABAY_MUSIC_ENDPOINT}?{urlencode(params)}", timeout=30
    )
    if not r.ok:
        raise MusicError(f"Pixabay error {r.status_code}: {r.text[:300]}")
    data = r.json()
    hits = data.get("hits", [])
    if not hits:
        raise MusicError(f"No Pixabay results for {query!r}.")

    track = hits[0]
    download_url = (
        track.get("audio")
        or track.get("preview")
        or track.get("audio_preview")
    )
    if not download_url:
        raise MusicError("Pixabay result has no downloadable audio URL.")

    log.info("Downloading: %s", track.get("tags", "track"))
    audio = requests.get(download_url, timeout=60)
    audio.raise_for_status()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(audio.content)
    return out_path


def mix_under_video(
    video_in: Path,
    music_path: Path,
    video_out: Path,
    music_gain_db: float = -8.0,
    duck_db: float = 12.0,
) -> Path:
    """Mix `music_path` under `video_in`'s audio with sidechain ducking.

    music_gain_db: starting gain on the music track (negative = quieter).
    duck_db: how much extra to drop the music when the VO is loud.
    """
    _require_ffmpeg()
    video_out.parent.mkdir(parents=True, exist_ok=True)

    # Filter graph:
    #   [vo]  → split into [vo_play][vo_sidechain]
    #   [music] → volume → loop → trim
    #   sidechaincompress(music ← vo_sidechain) ducks music under VO
    #   amix(vo_play + ducked music) → final
    threshold = 0.05  # voice must exceed this to trigger ducking
    filter_complex = (
        f"[1:a]volume={music_gain_db}dB,aloop=loop=-1:size=2e9[bg];"
        f"[0:a]asplit=2[voa][void];"
        f"[bg][void]sidechaincompress="
        f"threshold={threshold}:ratio=8:attack=20:release=400:makeup=0:level_sc=1"
        f"[bgduck];"
        f"[bgduck]volume=-{duck_db}dB[bgquiet];"
        f"[voa][bgquiet]amix=inputs=2:duration=first:dropout_transition=0[a]"
    )
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_in),
        "-i", str(music_path),
        "-filter_complex", filter_complex,
        "-map", "0:v", "-map", "[a]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(video_out),
    ]
    log.info("Mixing music under VO → %s", video_out.name)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise MusicError(
            f"ffmpeg mix failed (exit {proc.returncode}):\n{proc.stderr[-2000:]}"
        )
    return video_out


def resolve_music_source(
    music_file: Optional[str],
    music_query: Optional[str],
    cache_dir: Path,
) -> Optional[Path]:
    """Return a usable music path, downloading from Pixabay if requested."""
    if music_file:
        path = Path(music_file).expanduser().resolve()
        if not path.exists():
            raise MusicError(f"--music file not found: {path}")
        return path
    if music_query:
        cache_dir.mkdir(parents=True, exist_ok=True)
        out = cache_dir / "music.mp3"
        return search_pixabay(music_query, out)
    return None
