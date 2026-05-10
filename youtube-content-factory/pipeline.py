"""End-to-end CLI orchestrator.

Subcommands:
  plan        — niche -> 10 video ideas (saved as JSON)
  script      — plan + idea_index -> structured shooting script
  produce     — script -> voiceover MP3s + DALL-E images per scene
  seo         — script -> titles, description, tags, thumbnail concepts
  affiliates  — script -> affiliate program suggestions
  thumbnail   — render the actual thumbnail PNG from the SEO bundle
  assemble    — ffmpeg-mux scene assets into final.mp4
  subtitle    — Whisper transcribe -> SRT -> burn into final.subbed.mp4
  upload      — push the finished video to YouTube
  full        — everything end-to-end with a cost-approval gate

Outputs land under ./output/<video-slug>/ organized per video.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

from config import Config, ConfigError
from src.affiliate_finder import AffiliateFinder
from src.cost_estimator import confirm, estimate_full_run
from src.image_gen import ImageGenerator
from src.script_generator import ContentPlan, ScriptGenerator, VideoScript
from src.seo_generator import SeoBundle, SeoGenerator
from src.subtitles import SubtitleGenerator
from src.thumbnail import render as render_thumbnail
from src.utils import read_json, setup_logging, slugify, write_json
from src.video_assembler import assemble, burn_subtitles, extract_audio
from src.voiceover import Voiceover
# YouTubeUploader is lazy-imported in cmd_upload — its google-auth deps shouldn't
# be required for the rest of the pipeline.


def _plan_path(config: Config, niche: str) -> Path:
    return config.output_dir / "metadata" / f"plan-{slugify(niche)}.json"


def _video_dir(config: Config, video_title: str) -> Path:
    return config.output_dir / slugify(video_title)


def _load_script(video_dir: Path) -> VideoScript:
    return VideoScript.model_validate(read_json(video_dir / "script.json"))


def _load_seo(video_dir: Path) -> SeoBundle:
    return SeoBundle.model_validate(read_json(video_dir / "seo.json"))


# ------------------------------ stages ------------------------------ #

def cmd_plan(args, config, log) -> int:
    gen = ScriptGenerator(config.anthropic_api_key)
    plan = gen.plan(args.niche, args.market, num_videos=args.count)
    out = _plan_path(config, args.niche)
    write_json(out, plan.model_dump())
    log.info("Wrote plan with %d ideas: %s", len(plan.ideas), out)
    for i, idea in enumerate(plan.ideas, start=1):
        log.info("  [%d] %s", i, idea.title)
    return 0


def cmd_script(args, config, log) -> int:
    plan_path = _plan_path(config, args.niche)
    if not plan_path.exists():
        log.error("No plan found at %s — run `plan` first.", plan_path)
        return 1
    plan = ContentPlan.model_validate(read_json(plan_path))
    if args.idea_index < 1 or args.idea_index > len(plan.ideas):
        log.error("idea-index out of range (1..%d)", len(plan.ideas))
        return 1
    idea = plan.ideas[args.idea_index - 1]
    gen = ScriptGenerator(config.anthropic_api_key)
    script = gen.script(idea, target_minutes=args.minutes)
    video_dir = _video_dir(config, script.title)
    video_dir.mkdir(parents=True, exist_ok=True)
    write_json(video_dir / "script.json", script.model_dump())
    write_json(video_dir / "idea.json", idea.model_dump())
    log.info("Wrote script with %d scenes: %s", len(script.scenes), video_dir / "script.json")
    return 0


def cmd_produce(args, config, log) -> int:
    video_dir = Path(args.video_dir).resolve()
    script = _load_script(video_dir)

    if not args.skip_audio:
        log.info("Generating voiceover for %d scenes...", len(script.scenes))
        vo = Voiceover(
            api_key=config.elevenlabs_api_key,
            voice_id=config.elevenlabs_voice_id,
            model_id=config.elevenlabs_model_id,
        )
        vo.synthesize_scenes([s.narrator for s in script.scenes], video_dir / "audio")

    if not args.skip_images:
        log.info("Generating images for %d scenes...", len(script.scenes))
        img = ImageGenerator(api_key=config.openai_api_key)
        img.generate_batch([s.image_prompt for s in script.scenes], video_dir / "images")

    log.info("Production assets ready in %s", video_dir)
    return 0


def cmd_seo(args, config, log) -> int:
    video_dir = Path(args.video_dir).resolve()
    script = _load_script(video_dir)
    seo = SeoGenerator(config.anthropic_api_key)
    summary = script.hook + " " + " ".join(s.narrator for s in script.scenes[:3])
    keywords = args.keywords.split(",") if args.keywords else [script.title]
    bundle = seo.generate(script.title, keywords=keywords, summary=summary)
    write_json(video_dir / "seo.json", bundle.model_dump())
    log.info("Wrote SEO bundle: %s", video_dir / "seo.json")
    return 0


def cmd_affiliates(args, config, log) -> int:
    video_dir = Path(args.video_dir).resolve()
    script = _load_script(video_dir)
    tools = args.tools.split(",") if args.tools else _guess_tools(script)
    finder = AffiliateFinder(config.anthropic_api_key)
    report = finder.find(tools_mentioned=tools, niche=args.niche)
    write_json(video_dir / "affiliates.json", report.model_dump())
    log.info("Wrote affiliate report: %s", video_dir / "affiliates.json")
    return 0


def cmd_thumbnail(args, config, log) -> int:
    video_dir = Path(args.video_dir).resolve()
    seo = _load_seo(video_dir)
    if not seo.thumbnail_concepts:
        log.error("seo.json has no thumbnail concepts.")
        return 1
    concept = seo.thumbnail_concepts[args.concept_index - 1]
    img = ImageGenerator(api_key=config.openai_api_key)
    out = video_dir / "thumbnail.png"
    render_thumbnail(img, concept.headline_text, concept.visual_description, out)
    return 0


def cmd_assemble(args, config, log) -> int:
    video_dir = Path(args.video_dir).resolve()
    script = _load_script(video_dir)
    audio_dir = video_dir / "audio"
    image_dir = video_dir / "images"
    pairs = []
    for i in range(1, len(script.scenes) + 1):
        img = image_dir / f"scene_{i:02d}.png"
        aud = audio_dir / f"scene_{i:02d}.mp3"
        if not img.exists() or not aud.exists():
            log.error("Missing asset: %s or %s", img, aud)
            return 1
        pairs.append((img, aud))
    out = video_dir / "final.mp4"
    assemble(pairs, out)
    log.info("Final video: %s", out)
    return 0


def cmd_subtitle(args, config, log) -> int:
    video_dir = Path(args.video_dir).resolve()
    final = video_dir / "final.mp4"
    if not final.exists():
        log.error("Run `assemble` first — no final.mp4 in %s", video_dir)
        return 1
    audio = video_dir / "final.audio.mp3"
    extract_audio(final, audio)
    sub = SubtitleGenerator(api_key=config.openai_api_key)
    srt = sub.transcribe_to_srt(audio, video_dir / "final.srt")
    burned = burn_subtitles(final, srt, video_dir / "final.subbed.mp4")
    log.info("Subtitled video: %s", burned)
    return 0


def cmd_upload(args, config, log) -> int:
    from src.youtube_upload import YouTubeUploader  # lazy: needs google-auth

    video_dir = Path(args.video_dir).resolve()
    seo = _load_seo(video_dir)
    title = args.title or seo.titles[0]
    video_path = video_dir / args.video_file

    if not video_path.exists():
        log.error("Missing %s", video_path)
        return 1

    thumb = video_dir / "thumbnail.png"
    uploader = YouTubeUploader(Path(args.client_secrets).resolve())
    result = uploader.upload(
        video_path=video_path,
        title=title,
        description=seo.description,
        tags=seo.tags,
        privacy=args.privacy,
        thumbnail_path=thumb if thumb.exists() else None,
    )
    log.info("Uploaded: %s", result.url)
    print(result.url)
    return 0


def cmd_full(args, config, log) -> int:
    estimate = estimate_full_run(
        num_scenes=args.scenes_estimate,
        target_minutes=args.minutes,
        include_subtitles=not args.no_subtitles,
        include_thumbnail=not args.no_thumbnail,
    )
    if not confirm(estimate, auto_approve=args.approve):
        log.info("Aborted by user.")
        return 0

    rc = cmd_plan(args, config, log)
    if rc:
        return rc
    args.idea_index = 1
    rc = cmd_script(args, config, log)
    if rc:
        return rc

    plan = ContentPlan.model_validate(read_json(_plan_path(config, args.niche)))
    video_dir = _video_dir(config, plan.ideas[0].title)
    args.video_dir = str(video_dir)
    args.skip_audio = False
    args.skip_images = False
    args.keywords = plan.ideas[0].target_keyword
    args.tools = ""

    for fn in (cmd_produce, cmd_seo, cmd_affiliates):
        rc = fn(args, config, log)
        if rc:
            return rc

    if not args.no_thumbnail:
        args.concept_index = 1
        rc = cmd_thumbnail(args, config, log)
        if rc:
            return rc

    rc = cmd_assemble(args, config, log)
    if rc:
        return rc

    if not args.no_subtitles:
        rc = cmd_subtitle(args, config, log)
        if rc:
            return rc

    if args.upload:
        args.title = ""
        args.video_file = "final.subbed.mp4" if not args.no_subtitles else "final.mp4"
        args.client_secrets = args.client_secrets or "client_secrets.json"
        args.privacy = args.upload_privacy
        rc = cmd_upload(args, config, log)
        if rc:
            return rc

    log.info("Done — assets in %s", video_dir)
    return 0


# ------------------------------ helpers ------------------------------ #

def _guess_tools(script: VideoScript) -> List[str]:
    text = " ".join(s.narrator for s in script.scenes)
    candidates: List[str] = []
    for word in text.split():
        cleaned = word.strip(".,!?;:'\"()")
        if cleaned and cleaned[0].isupper() and len(cleaned) > 2:
            candidates.append(cleaned)
    seen, unique = set(), []
    for c in candidates:
        low = c.lower()
        if low not in seen:
            seen.add(low)
            unique.append(c)
    return unique[:10]


# ------------------------------ argparse ------------------------------ #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pipeline",
        description="YouTube content factory: niche -> script -> assets -> SEO -> MP4 -> upload.",
    )
    p.add_argument("--log-level", default="INFO")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("plan", help="Generate niche content plan.")
    sp.add_argument("--niche", required=True)
    sp.add_argument("--market", default="US")
    sp.add_argument("--count", type=int, default=10)
    sp.set_defaults(func=cmd_plan)

    sp = sub.add_parser("script", help="Generate script for one idea in a plan.")
    sp.add_argument("--niche", required=True)
    sp.add_argument("--idea-index", type=int, required=True)
    sp.add_argument("--minutes", type=int, default=8)
    sp.set_defaults(func=cmd_script)

    sp = sub.add_parser("produce", help="Generate audio + images for a script.")
    sp.add_argument("--video-dir", required=True)
    sp.add_argument("--skip-audio", action="store_true")
    sp.add_argument("--skip-images", action="store_true")
    sp.set_defaults(func=cmd_produce)

    sp = sub.add_parser("seo", help="Generate titles, description, thumbnails.")
    sp.add_argument("--video-dir", required=True)
    sp.add_argument("--keywords", default="")
    sp.set_defaults(func=cmd_seo)

    sp = sub.add_parser("affiliates", help="Suggest affiliate programs.")
    sp.add_argument("--video-dir", required=True)
    sp.add_argument("--niche", required=True)
    sp.add_argument("--tools", default="")
    sp.set_defaults(func=cmd_affiliates)

    sp = sub.add_parser("thumbnail", help="Render the thumbnail PNG from seo.json.")
    sp.add_argument("--video-dir", required=True)
    sp.add_argument("--concept-index", type=int, default=1)
    sp.set_defaults(func=cmd_thumbnail)

    sp = sub.add_parser("assemble", help="ffmpeg-mux scenes into final.mp4.")
    sp.add_argument("--video-dir", required=True)
    sp.set_defaults(func=cmd_assemble)

    sp = sub.add_parser("subtitle", help="Whisper -> SRT -> burned-in subtitles.")
    sp.add_argument("--video-dir", required=True)
    sp.set_defaults(func=cmd_subtitle)

    sp = sub.add_parser("upload", help="Upload to YouTube via Data API v3.")
    sp.add_argument("--video-dir", required=True)
    sp.add_argument("--client-secrets", default="client_secrets.json")
    sp.add_argument("--video-file", default="final.subbed.mp4",
                    help="MP4 inside --video-dir to upload (default: subtitled).")
    sp.add_argument("--privacy", choices=["private", "unlisted", "public"], default="private")
    sp.add_argument("--title", default="", help="Override SEO title pick.")
    sp.set_defaults(func=cmd_upload)

    sp = sub.add_parser("full", help="Plan -> script -> assets -> SEO -> MP4 -> (upload).")
    sp.add_argument("--niche", required=True)
    sp.add_argument("--market", default="US")
    sp.add_argument("--count", type=int, default=10)
    sp.add_argument("--minutes", type=int, default=8)
    sp.add_argument("--scenes-estimate", type=int, default=12,
                    help="Used only by the cost estimator (real count is set by Claude).")
    sp.add_argument("--no-subtitles", action="store_true")
    sp.add_argument("--no-thumbnail", action="store_true")
    sp.add_argument("--approve", action="store_true",
                    help="Skip the cost-confirmation prompt.")
    sp.add_argument("--upload", action="store_true", help="Upload the result to YouTube.")
    sp.add_argument("--upload-privacy", choices=["private", "unlisted", "public"],
                    default="private")
    sp.add_argument("--client-secrets", default="client_secrets.json")
    sp.set_defaults(func=cmd_full)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    log = setup_logging(args.log_level)
    try:
        config = Config.load()
    except ConfigError as e:
        log.error(str(e))
        return 2
    config.ensure_dirs()
    return args.func(args, config, log)


if __name__ == "__main__":
    sys.exit(main())
