"""End-to-end CLI orchestrator.

Subcommands:
  plan        — niche -> 10 video ideas (saved as JSON)
  script      — plan + idea_index -> structured shooting script
  produce     — script -> voiceover MP3s + DALL-E images per scene
  seo         — script -> titles, description, tags, thumbnail concepts
  affiliates  — script -> affiliate program suggestions
  full        — niche -> first idea fully produced (script + assets + SEO + affiliates)

Outputs land under ./output/ organized by video slug.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

from config import Config, ConfigError
from src.affiliate_finder import AffiliateFinder
from src.image_gen import ImageGenerator
from src.script_generator import ContentPlan, ScriptGenerator, VideoScript
from src.seo_generator import SeoGenerator
from src.utils import read_json, setup_logging, slugify, write_json
from src.voiceover import Voiceover


def _plan_path(config: Config, niche: str) -> Path:
    return config.output_dir / "metadata" / f"plan-{slugify(niche)}.json"


def _video_dir(config: Config, video_title: str) -> Path:
    return config.output_dir / slugify(video_title)


def cmd_plan(args, config: Config, log) -> int:
    gen = ScriptGenerator(config.anthropic_api_key)
    plan = gen.plan(args.niche, args.market, num_videos=args.count)
    out = _plan_path(config, args.niche)
    write_json(out, plan.model_dump())
    log.info("Wrote plan with %d ideas: %s", len(plan.ideas), out)
    for i, idea in enumerate(plan.ideas, start=1):
        log.info("  [%d] %s", i, idea.title)
    return 0


def cmd_script(args, config: Config, log) -> int:
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
    log.info("Wrote script with %d scenes: %s", len(script.scenes), video_dir / "script.json")
    return 0


def _load_script(video_dir: Path) -> VideoScript:
    return VideoScript.model_validate(read_json(video_dir / "script.json"))


def cmd_produce(args, config: Config, log) -> int:
    video_dir = Path(args.video_dir).resolve()
    script = _load_script(video_dir)

    if not args.skip_audio:
        log.info("Generating voiceover for %d scenes...", len(script.scenes))
        vo = Voiceover(
            api_key=config.elevenlabs_api_key,
            voice_id=config.elevenlabs_voice_id,
            model_id=config.elevenlabs_model_id,
        )
        vo.synthesize_scenes(
            [s.narrator for s in script.scenes],
            video_dir / "audio",
        )

    if not args.skip_images:
        log.info("Generating images for %d scenes...", len(script.scenes))
        img = ImageGenerator(api_key=config.openai_api_key)
        img.generate_batch(
            [s.image_prompt for s in script.scenes],
            video_dir / "images",
        )

    log.info("Production assets ready in %s", video_dir)
    return 0


def cmd_seo(args, config: Config, log) -> int:
    video_dir = Path(args.video_dir).resolve()
    script = _load_script(video_dir)
    seo = SeoGenerator(config.anthropic_api_key)
    summary = script.hook + " " + " ".join(s.narrator for s in script.scenes[:3])
    keywords = args.keywords.split(",") if args.keywords else [script.title]
    bundle = seo.generate(script.title, keywords=keywords, summary=summary)
    write_json(video_dir / "seo.json", bundle.model_dump())
    log.info("Wrote SEO bundle: %s", video_dir / "seo.json")
    return 0


def cmd_affiliates(args, config: Config, log) -> int:
    video_dir = Path(args.video_dir).resolve()
    script = _load_script(video_dir)
    tools = args.tools.split(",") if args.tools else _guess_tools(script)
    finder = AffiliateFinder(config.anthropic_api_key)
    report = finder.find(tools_mentioned=tools, niche=args.niche)
    write_json(video_dir / "affiliates.json", report.model_dump())
    log.info("Wrote affiliate report: %s", video_dir / "affiliates.json")
    return 0


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


def cmd_full(args, config: Config, log) -> int:
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
    rc = cmd_produce(args, config, log)
    if rc:
        return rc
    rc = cmd_seo(args, config, log)
    if rc:
        return rc
    return cmd_affiliates(args, config, log)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pipeline",
        description="YouTube content factory: niche -> script -> assets -> SEO.",
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

    sp = sub.add_parser("full", help="Plan -> first script -> all assets -> SEO + affiliates.")
    sp.add_argument("--niche", required=True)
    sp.add_argument("--market", default="US")
    sp.add_argument("--count", type=int, default=10)
    sp.add_argument("--minutes", type=int, default=8)
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
