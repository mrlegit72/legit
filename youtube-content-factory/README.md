# YouTube Content Factory

A scalable pipeline that turns a niche into a fully scripted, voiced, illustrated, and SEO-optimized YouTube video.

```
niche
  └─► Claude (script_generator)        → structured JSON plan + per-scene script
        ├─► ElevenLabs (voiceover)     → one MP3 per scene
        ├─► OpenAI DALL-E 3 (image_gen)→ one 16:9 PNG per scene
        ├─► Claude (seo_generator)     → titles, description, tags, thumbnails
        └─► Claude (affiliate_finder)  → affiliate program suggestions
                                         (drag the assets into Premiere Pro)
```

---

## 1. Project layout

```
youtube-content-factory/
├── pipeline.py              # CLI entry point
├── config.py                # env loader + validation
├── requirements.txt
├── .env.example             # copy to .env
├── src/
│   ├── script_generator.py  # Claude — structured plan + script
│   ├── voiceover.py         # ElevenLabs TTS with retries
│   ├── image_gen.py         # OpenAI DALL-E 3 (modern SDK)
│   ├── seo_generator.py     # Claude — SEO bundle
│   ├── affiliate_finder.py  # Claude — affiliate research
│   └── utils.py             # logging, slugs, JSON I/O
└── output/
    ├── metadata/            # plans
    └── <video-slug>/        # one folder per video
        ├── script.json
        ├── audio/scene_01.mp3 ...
        ├── images/scene_01.png ...
        ├── seo.json
        └── affiliates.json
```

---

## 2. Get the API keys (and what they cost)

You need three accounts. All three have free tiers or trial credits, so a first end-to-end run costs roughly **$1–$3**.

### a) Anthropic (Claude) — script + SEO + affiliate research

1. Go to https://console.anthropic.com → sign up.
2. Settings → **API Keys** → **Create Key**. Copy the `sk-ant-...` value.
3. Add credit under **Plans & Billing** ($5 minimum is plenty to start).

**Cost** (Claude Opus 4.7, the model used here):
- Input: $5 per 1M tokens • Output: $25 per 1M tokens
- Prompt caching (already wired in) cuts repeat input cost by ~90%.
- A typical 8-minute script + SEO + affiliate research costs about **$0.10–$0.30**.

> Want it cheaper? Swap the `MODEL = "claude-opus-4-7"` line in `src/script_generator.py`, `seo_generator.py`, and `affiliate_finder.py` to `claude-sonnet-4-6` ($3/$15 per 1M). Quality is still excellent for this workload.

### b) ElevenLabs — voiceover

1. Go to https://elevenlabs.io → sign up.
2. Profile → **API Key** → copy.
3. Pick a voice: **VoiceLab** → **Voice Library** → click any voice → copy its **Voice ID** (the part after `/voices/`). Default in the code is `pNInz6obpgDQGcFmaJgB` (Adam).

**Cost**:
- Free tier: 10,000 chars/month (≈10 minutes of audio).
- Starter ($5/mo): 30,000 chars (≈30 min) + commercial license.
- Creator ($22/mo): 100,000 chars (≈100 min) + higher quality models.

A typical 8-minute video script is ~1,200 words ≈ 6,500 chars, so ~4 videos/month on Starter or ~15/month on Creator.

### c) OpenAI — DALL-E 3 image generation

1. Go to https://platform.openai.com → sign up.
2. **API keys** → **Create new secret key** → copy.
3. Add credit under **Billing** ($5 minimum).

**Cost**:
- DALL-E 3 standard 1024×1024: $0.040/image
- DALL-E 3 HD 1792×1024 (the default here, 16:9): **$0.080/image**
- An 8-minute script with ~12 scenes ≈ **$0.96/video**.

> Want it free? The original guide notes Microsoft Designer is free. You'd lose programmatic generation — generate images by hand from the `image_prompt` field in `script.json` and drop them into `output/<slug>/images/`.

### Total per video (rough)

| Item | Cost |
|---|---|
| Claude (script + SEO + affiliates) | $0.10 – $0.30 |
| ElevenLabs (voiceover, on Starter) | included in $5/mo |
| DALL-E 3 HD (12 images) | ~$0.96 |
| **Per video** | **~$1.10 – $1.30** |

---

## 3. Install

Requires **Python 3.10+**.

```bash
cd youtube-content-factory
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# open .env and paste your three API keys
```

---

## 4. Run it

The pipeline is one CLI with five subcommands plus a `full` shortcut.

### a) Plan a niche (10 video ideas)

```bash
python pipeline.py plan --niche "AI Tools for Productivity" --market US --count 10
```

Writes `output/metadata/plan-ai-tools-for-productivity.json`.

### b) Pick one idea and write the script

```bash
python pipeline.py script \
  --niche "AI Tools for Productivity" \
  --idea-index 1 \
  --minutes 8
```

Writes `output/<video-slug>/script.json` with structured scenes (narrator + visual + image prompt).

### c) Produce the assets (audio + images)

```bash
python pipeline.py produce --video-dir output/<video-slug>
```

Generates `audio/scene_01.mp3 ...` and `images/scene_01.png ...`.

Skip a stage if you want: `--skip-audio` or `--skip-images`.

### d) SEO bundle

```bash
python pipeline.py seo --video-dir output/<video-slug> --keywords "ai productivity,chatgpt,notion ai"
```

Writes `seo.json` with 5 title variants, a description, 10 tags, and 5 thumbnail concepts.

### e) Affiliate suggestions

```bash
python pipeline.py affiliates --video-dir output/<video-slug> --niche "AI productivity tools"
```

Writes `affiliates.json`. **Always verify each program is currently open** — Claude is suggesting from training data, not browsing.

### f) Or do everything in one shot

```bash
python pipeline.py full --niche "AI Tools for Productivity" --market US --minutes 8
```

This plans, picks the first idea, writes the script, generates audio + images, and produces SEO + affiliate output.

### Then in Premiere Pro 2026

1. Drag the `output/<video-slug>/audio/` and `images/` folders into your project.
2. **Window → Text** → Premiere transcribes the voiceover; edit the video by editing the text.
3. Select audio → **Essential Sound → Enhance** for studio-grade voice cleanup.
4. Right-click the sequence → **Auto Reframe Sequence → Vertical** to spin off Shorts.

---

## 5. Upgrades worth adding next

The current pipeline covers the core guide. These are concrete add-ons, ranked by value:

1. **Auto-mux the timeline.** Add a stage that uses `ffmpeg` to stitch `scene_NN.mp3` over `scene_NN.png` (Ken Burns zoom optional) and concatenates them into a single MP4. Saves the Premiere step entirely for fast Shorts.
2. **Real keyword research instead of guessing.** Replace the static `--keywords` flag with a call to a YouTube data source (TubeBuddy/VidIQ APIs, or the free YouTube Data API v3 for autocomplete + view counts). Feed real top-CTR titles into the SEO prompt.
3. **Brand-consistent thumbnails.** After SEO generates the thumbnail concept, pipe each one back through DALL-E 3 with a fixed style suffix (e.g. *"bold yellow text, red arrow, surprised face cutout"*) so every thumbnail in the channel looks like one channel.
4. **Voice cloning.** Pay for ElevenLabs **Pro** ($99/mo) and clone your own voice — the voiceover stops sounding generic.
5. **Music + SFX layer.** Add a stage that pulls a royalty-free track (Pixabay Music API is free) and a per-scene whoosh/ding from Freesound, mixed at -18 LUFS under the VO.
6. **Subtitles burned in.** Run the final MP3 through OpenAI Whisper (`whisper-1` API, ~$0.006/min) for word-level SRT, then burn captions with `ffmpeg`. Shorts get massively higher retention with captions.
7. **Batch mode.** Loop `produce`/`seo`/`affiliates` over every idea in the plan to ship a whole month of videos in one run. The script generator's prompt cache will absorb most of the system-prompt cost across the batch.
8. **Approval gate before spend.** Add an `--approve` step that prints the plan + estimated cost in dollars and waits for `y/N` before calling DALL-E. Keeps you from accidentally spending $10 on a bad niche.
9. **YouTube auto-upload.** Use the YouTube Data API v3 `videos.insert` endpoint to upload the final MP4 with the SEO `title`/`description`/`tags` already filled in. Schedule weekly drops with a cron job.
10. **Switch to Claude Sonnet 4.6 for the SEO + affiliate stages.** Half the per-token cost of Opus and indistinguishable quality on those shorter prompts. (Keep Opus for script generation — that's where the reasoning depth pays off.)

---

## 6. Troubleshooting

| Symptom | Fix |
|---|---|
| `ConfigError: Missing required environment variable` | You haven't copied `.env.example → .env` or a key is blank. |
| ElevenLabs `401` | Wrong API key, or the voice ID isn't accessible to your tier. |
| OpenAI `billing_hard_limit_reached` | Add credit at https://platform.openai.com/account/billing. |
| Claude `rate_limit_error` | The SDK retries automatically; if you see it repeatedly, raise your usage tier in Console. |
| Empty `parsed_output` | Claude refused or hit the schema. Check `stop_reason` in the logged usage line; rerun with `--log-level DEBUG`. |
