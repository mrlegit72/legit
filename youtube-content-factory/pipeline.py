"""End-to-end CLI orchestrator.

Subcommands:
  plan             niche -> 10 video ideas
  script           plan + idea_index -> structured shooting script
  produce          script -> voiceover MP3s + DALL-E images per scene
  seo              script -> titles, description, tags, thumbnail concepts
  affiliates       script -> affiliate program suggestions
  thumbnail        render the thumbnail PNG from the SEO bundle
  assemble         ffmpeg-mux scene assets into final.mp4
  subtitle         Whisper transcribe -> SRT -> burned subtitles
  music            mix a music bed under the final video (sidechain ducking)
  upload           push the finished video to YouTube
  voices           list ElevenLabs voices (find your cloned voice's ID)
  research         live keyword research via YouTube Data API
  analytics-pull   pull recent channel performance for SEO feedback loop
  full             everything end-to-end with a cost-approval gate

Outputs land under ./output/<video-slug>/ organized per video.
Channel-wide artifacts (analytics, keyword reports) live in ./output/metadata/.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

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
from src.voiceover import Voiceover, list_voices
# YouTubeUploader, KeywordResearch, analytics, and music are lazy-imported in
# their command handlers — their deps (google-auth, ffmpeg) shouldn't be
# required for the rest of the pipeline.


# ------------------------------ paths ------------------------------ #

def _plan_path(config: Config, niche: str) -> Path:
    return config.output_dir / "metadata" / f"plan-{slugify(niche)}.json"


def _video_dir(config: Config, video_title: str) -> Path:
    return config.output_dir / slugify(video_title)


def _analytics_path(config: Config) -> Path:
    return config.output_dir / "metadata" / "analytics.json"


def _keywords_path(config: Config, query: str) -> Path:
    return config.output_dir / "metadata" / f"keywords-{slugify(query)}.json"


def _load_script(video_dir: Path) -> VideoScript:
    return VideoScript.model_validate(read_json(video_dir / "script.json"))


def _load_seo(video_dir: Path) -> SeoBundle:
    return SeoBundle.model_validate(read_json(video_dir / "seo.json"))


# ----------------------- context aggregation ----------------------- #

def _build_context(
    config: Config,
    log,
    keyword_query: str = "",
    include_analytics: bool = True,
) -> str:
    """Concatenate all available "what's working right now" context blocks."""
    blocks: List[str] = []

    if keyword_query and config.youtube_api_key:
        try:
            from src.keyword_research import KeywordResearch
            report = KeywordResearch(config.youtube_api_key).research(
                keyword_query, region_code=config.default_market
            )
            blocks.append(report.to_prompt_context())
            write_json(_keywords_path(config, keyword_query), report.model_dump())
        except Exception as e:  # API failure shouldn't break the pipeline
            log.warning("Keyword research failed (continuing without): %s", e)

    if include_analytics:
        try:
            from src.analytics import load_or_none
            report = load_or_none(_analytics_path(config))
            if report is not None:
                blocks.append(report.to_prompt_context())
        except Exception as e:
            log.warning("Analytics load failed (continuing without): %s", e)

    return "\n\n".join(blocks)


# ------------------------------ stages ------------------------------ #

def cmd_plan(args, config, log) -> int:
    extra = _build_context(config, log, keyword_query=args.niche, include_analytics=True)
    gen = ScriptGenerator(config.anthropic_api_key)
    plan = gen.plan(args.niche, args.market, num_videos=args.count, extra_context=extra)
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
    extra = _build_context(
        config, log, keyword_query=idea.target_keyword, include_analytics=True
    )
    gen = ScriptGenerator(config.anthropic_api_key)
    script = gen.script(idea, target_minutes=args.minutes, extra_context=extra)
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
    extra = _build_context(
        config, log, keyword_query=keywords[0], include_analytics=True
    )
    bundle = seo.generate(
        script.title, keywords=keywords, summary=summary, extra_context=extra
    )
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


def cmd_music(args, config, log) -> int:
    from src.music import mix_under_video, resolve_music_source

    video_dir = Path(args.video_dir).resolve()
    video_in = video_dir / args.input_file
    if not video_in.exists():
        log.error("No %s in %s — run `assemble` (and `subtitle`) first.",
                  args.input_file, video_dir)
        return 1
    music_path = resolve_music_source(
        args.music_file or None,
        args.music_query or None,
        cache_dir=config.output_dir / "metadata",
    )
    if music_path is None:
        log.error("Pass --music-file PATH or --music-query 'genre' "
                  "(requires PIXABAY_API_KEY).")
        return 1
    out = video_dir / args.output_file
    mix_under_video(video_in, music_path, out)
    log.info("Music-mixed video: %s", out)
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


def cmd_voices(args, config, log) -> int:
    voices = list_voices(config.elevenlabs_api_key)
    voices.sort(key=lambda v: (v.category != "cloned", v.name))
    print()
    print(f"  {'CATEGORY':<14} {'VOICE_ID':<24} NAME")
    print(f"  {'-' * 14} {'-' * 24} {'-' * 24}")
    for v in voices:
        marker = " ★" if v.category == "cloned" else "  "
        print(f"{marker}{v.category:<14} {v.voice_id:<24} {v.name}")
    print()
    print("Paste the voice_id you want into ELEVENLABS_VOICE_ID in .env.")
    return 0


def cmd_research(args, config, log) -> int:
    if not config.youtube_api_key:
        log.error("YOUTUBE_API_KEY not set in .env.")
        return 1
    from src.keyword_research import KeywordResearch
    kr = KeywordResearch(config.youtube_api_key)
    report = kr.research(args.query, region_code=args.region, max_results=args.max_results)
    out = _keywords_path(config, args.query)
    write_json(out, report.model_dump())
    print(report.to_prompt_context())
    log.info("Saved report: %s", out)
    return 0


def cmd_analytics_pull(args, config, log) -> int:
    from src.analytics import fetch_recent, save
    secrets = Path(args.client_secrets).resolve()
    if not secrets.exists():
        log.error("Missing %s. See README §2d.", secrets)
        return 1
    report = fetch_recent(secrets, period_days=args.days, max_videos=args.max_videos)
    out = _analytics_path(config)
    save(report, out)
    log.info("Saved %d videos of analytics: %s", len(report.videos), out)
    if report.videos:
        print(report.to_prompt_context())
    else:
        print("(no videos found — upload some first)")
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

    final_file = "final.subbed.mp4" if not args.no_subtitles else "final.mp4"

    if args.music_file or args.music_query:
        args.input_file = final_file
        args.output_file = "final.mixed.mp4"
        rc = cmd_music(args, config, log)
        if rc:
            return rc
        final_file = "final.mixed.mp4"

    if args.upload:
        args.title = ""
        args.video_file = final_file
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

    sp = sub.add_parser("music", help="Mix a music bed under the video (sidechain duck).")
    sp.add_argument("--video-dir", required=True)
    sp.add_argument("--music-file", default="", help="Local audio file path.")
    sp.add_argument("--music-query", default="", help="Pixabay search query.")
    sp.add_argument("--input-file", default="final.subbed.mp4")
    sp.add_argument("--output-file", default="final.mixed.mp4")
    sp.set_defaults(func=cmd_music)

    sp = sub.add_parser("upload", help="Upload to YouTube via Data API v3.")
    sp.add_argument("--video-dir", required=True)
    sp.add_argument("--client-secrets", default="client_secrets.json")
    sp.add_argument("--video-file", default="final.subbed.mp4")
    sp.add_argument("--privacy", choices=["private", "unlisted", "public"], default="private")
    sp.add_argument("--title", default="")
    sp.set_defaults(func=cmd_upload)

    sp = sub.add_parser("voices", help="List ElevenLabs voices (find your cloned ID).")
    sp.set_defaults(func=cmd_voices)

    sp = sub.add_parser("research", help="Live YouTube keyword research.")
    sp.add_argument("--query", required=True)
    sp.add_argument("--region", default="US")
    sp.add_argument("--max-results", type=int, default=15)
    sp.set_defaults(func=cmd_research)

    sp = sub.add_parser("analytics-pull",
                        help="Pull recent channel analytics for SEO feedback.")
    sp.add_argument("--client-secrets", default="client_secrets.json")
    sp.add_argument("--days", type=int, default=28)
    sp.add_argument("--max-videos", type=int, default=25)
    sp.set_defaults(func=cmd_analytics_pull)

    sp = sub.add_parser("full", help="Plan -> script -> assets -> SEO -> MP4 -> (upload).")
    sp.add_argument("--niche", required=True)
    sp.add_argument("--market", default="US")
    sp.add_argument("--count", type=int, default=10)
    sp.add_argument("--minutes", type=int, default=8)
    sp.add_argument("--scenes-estimate", type=int, default=12,
                    help="Used only by the cost estimator (real count set by Claude).")
    sp.add_argument("--no-subtitles", action="store_true")
    sp.add_argument("--no-thumbnail", action="store_true")
    sp.add_argument("--approve", action="store_true",
                    help="Skip the cost-confirmation prompt.")
    sp.add_argument("--music-file", default="")
    sp.add_argument("--music-query", default="")
    sp.add_argument("--upload", action="store_true")
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
