"""Render scene_NN.png + scene_NN.mp3 into a single MP4 via ffmpeg.

Each scene becomes a still-image clip with a slow Ken Burns zoom whose
duration matches the scene's audio. Clips are concatenated losslessly via
the ffmpeg concat demuxer.

Requires the `ffmpeg` binary on $PATH.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Tuple

log = logging.getLogger("yt_factory.video")

DEFAULT_SIZE = "1920x1080"
DEFAULT_FPS = 30


class FfmpegError(RuntimeError):
    pass


def _require_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise FfmpegError(
            "ffmpeg/ffprobe not found on PATH. Install ffmpeg first "
            "(macOS: `brew install ffmpeg`, Ubuntu: `apt install ffmpeg`)."
        )


def _run(cmd: List[str]) -> None:
    log.debug("$ %s", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise FfmpegError(
            f"ffmpeg failed (exit {proc.returncode}):\n{proc.stderr[-2000:]}"
        )


def _audio_duration(audio_path: Path) -> float:
    proc = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise FfmpegError(f"ffprobe failed: {proc.stderr}")
    return float(proc.stdout.strip())


def _render_scene(
    image_path: Path,
    audio_path: Path,
    out_path: Path,
    size: str = DEFAULT_SIZE,
    fps: int = DEFAULT_FPS,
) -> None:
    duration = _audio_duration(audio_path)
    total_frames = max(int(duration * fps), 1)
    # Slow zoom to 1.15x over the scene; held centered. Stillimage tune
    # eliminates wasted bits on a static image.
    zoom_filter = (
        f"scale=8000:-1,"
        f"zoompan=z='min(zoom+0.00015,1.15)':d={total_frames}:"
        f"s={size}:fps={fps},format=yuv420p"
    )
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(image_path),
        "-i", str(audio_path),
        "-filter_complex", f"[0:v]{zoom_filter}[v]",
        "-map", "[v]", "-map", "1:a",
        "-c:v", "libx264", "-tune", "stillimage", "-preset", "medium",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(out_path),
    ]
    _run(cmd)


def assemble(
    scenes: List[Tuple[Path, Path]],
    out_path: Path,
    size: str = DEFAULT_SIZE,
    fps: int = DEFAULT_FPS,
) -> Path:
    """Render and concatenate scenes into a single MP4.

    `scenes` is a list of (image_path, audio_path) pairs in order.
    Returns the path to the final MP4.
    """
    _require_ffmpeg()
    if not scenes:
        raise ValueError("No scenes to assemble.")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        clip_paths: List[Path] = []
        for i, (img, audio) in enumerate(scenes, start=1):
            clip = tmp_dir / f"clip_{i:02d}.mp4"
            log.info("Rendering scene %d/%d", i, len(scenes))
            _render_scene(img, audio, clip, size=size, fps=fps)
            clip_paths.append(clip)

        concat_list = tmp_dir / "concat.txt"
        concat_list.write_text(
            "\n".join(f"file '{p}'" for p in clip_paths) + "\n",
            encoding="utf-8",
        )
        log.info("Concatenating %d clips → %s", len(clip_paths), out_path.name)
        _run([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",
            str(out_path),
        ])

    return out_path


def burn_subtitles(video_in: Path, srt: Path, video_out: Path) -> Path:
    """Re-encode `video_in` with `srt` burned in as hard subtitles."""
    _require_ffmpeg()
    video_out.parent.mkdir(parents=True, exist_ok=True)
    style = (
        "FontName=Arial,FontSize=22,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,"
        "Alignment=2,MarginV=60"
    )
    # Escape for ffmpeg filter syntax — colons and backslashes need it.
    srt_arg = str(srt).replace(":", r"\:").replace("'", r"\'")
    _run([
        "ffmpeg", "-y",
        "-i", str(video_in),
        "-vf", f"subtitles='{srt_arg}':force_style='{style}'",
        "-c:a", "copy",
        str(video_out),
    ])
    return video_out


def extract_audio(video: Path, out_path: Path) -> Path:
    """Pull a single audio track out of an MP4 — used to feed Whisper."""
    _require_ffmpeg()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _run([
        "ffmpeg", "-y",
        "-i", str(video),
        "-vn", "-acodec", "libmp3lame", "-q:a", "2",
        str(out_path),
    ])
    return out_path
