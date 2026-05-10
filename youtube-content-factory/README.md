# YouTube Content Factory

A scalable pipeline that turns a niche into a finished, subtitled, music-mixed, thumbnailed YouTube video — uploaded with SEO conditioned on real channel analytics and live YouTube search data.

```
                  YouTube analytics  ─┐
                  YouTube search.list ─┴─► context
                                             │
niche  ──────────────────────────────────────▼
  └─► Claude (script_generator)              → structured plan + per-scene script
        ├─► ElevenLabs (voiceover)           → one MP3 per scene  (cloned voice optional)
        ├─► OpenAI DALL-E 3 (image_gen)      → one 16:9 PNG per scene
        ├─► Claude (seo_generator)           → titles, description, tags, thumbnail concepts
        ├─► Claude (affiliate_finder)        → affiliate program suggestions
        ├─► DALL-E + Pillow (thumbnail)      → finished thumbnail PNG (1280x720)
        ├─► ffmpeg (video_assembler)         → scenes muxed into final.mp4 (Ken Burns)
        ├─► Whisper (subtitles)              → SRT → burned into final.subbed.mp4
        ├─► Pixabay + ffmpeg (music)         → music bed sidechain-ducked under VO
        └─► YouTube Data API (upload)        → uploaded video, thumbnail set, returns URL
```

---

## 1. Project layout

```
youtube-content-factory/
├── pipeline.py              # CLI entry point
├── config.py                # env loader + validation
├── requirements.txt
├── .env.example             # copy to .env
├── client_secrets.json      # (you create this — see §2d)
├── src/
│   ├── script_generator.py  # Claude — structured plan + script
│   ├── voiceover.py         # ElevenLabs TTS + cloned voice listing
│   ├── image_gen.py         # OpenAI DALL-E 3
│   ├── seo_generator.py     # Claude — SEO bundle
│   ├── affiliate_finder.py  # Claude — affiliate research
│   ├── thumbnail.py         # DALL-E + Pillow text overlay
│   ├── video_assembler.py   # ffmpeg mux + concat + subtitle burn
│   ├── subtitles.py         # Whisper API → SRT
│   ├── music.py             # Pixabay search + sidechain duck-mix
│   ├── keyword_research.py  # YouTube search.list + videos.list
│   ├── analytics.py         # YouTube Analytics API feedback loop
│   ├── youtube_upload.py    # YouTube Data API v3 (OAuth)
│   ├── cost_estimator.py    # itemized spend + approval prompt
│   └── utils.py             # logging, slugs, JSON I/O
└── output/
    ├── metadata/
    │   ├── plan-<niche>.json
    │   ├── analytics.json     # written by `analytics-pull`
    │   └── keywords-<q>.json  # written by `research`
    └── <video-slug>/
        ├── script.json
        ├── audio/scene_NN.mp3
        ├── images/scene_NN.png
        ├── seo.json
        ├── affiliates.json
        ├── thumbnail.png
        ├── final.mp4
        ├── final.srt
        ├── final.subbed.mp4
        └── final.mixed.mp4    # if music bed applied
```

---

## 2. Get the API keys (and what they cost)

### a) Anthropic (Claude) — script + SEO + affiliate research
1. https://console.anthropic.com → Settings → **API Keys** → Create.
2. Add $5 under **Plans & Billing**.

**Cost** (Opus 4.7 with prompt caching wired in): **~$0.10–$0.30 per video.**

### b) ElevenLabs — voiceover (with optional voice cloning)
1. https://elevenlabs.io → Profile → **API Key**.
2. **VoiceLab → Voice Library** → click any voice → copy the **Voice ID** for `ELEVENLABS_VOICE_ID`.

**Voice cloning**: clone your own voice in the ElevenLabs UI (Creator tier+, $22/mo), then run `python pipeline.py voices` to find its ID and paste into `.env`. Pipeline transparently uses it.

**Cost**: Free 10k chars/mo · **Starter $5/mo** (~4 videos) · **Creator $22/mo** (~15 videos + cloning + commercial license).

### c) OpenAI — DALL-E 3 + Whisper subtitles
1. https://platform.openai.com → **API keys** → Create + add $5.

**Cost per video**: 12 scene images × $0.080 + 1 thumbnail × $0.080 + Whisper × $0.006/min ≈ **$1.05 for an 8-min video**.

### d) YouTube Data API v3 + Analytics API — upload + feedback loop (free)

In Google Cloud Console:
1. Create a project → **APIs & Services → Library** → enable **both**:
   - YouTube Data API v3
   - YouTube Analytics API
2. **OAuth consent screen** → External → fill in app name + your email → add yourself as a test user.
3. **Credentials → Create Credentials → OAuth client ID** → **Desktop app** → Download JSON → save as `client_secrets.json` next to `pipeline.py`.
4. **Credentials → Create Credentials → API key** → copy into `.env` as `YOUTUBE_API_KEY` (this enables read-only keyword research, separate from OAuth).

The pipeline keeps **two separate token caches**: one for upload, one for analytics. Granting analytics read-only doesn't grant upload permission.

**Quotas (free)**:
- Data API v3: 10,000 units/day. Upload = 1,600. `search.list` = 100. `videos.list` = 1.
- Analytics API: 720 queries/min. Plenty.

### e) Pixabay — free CC0 music (optional)
1. https://pixabay.com/api/docs/ → register → copy your key.
2. Set `PIXABAY_API_KEY` in `.env`. Without it, `--music-query` is unavailable but `--music-file PATH` still works.

### f) ffmpeg — local binary (free, required)
```bash
brew install ffmpeg                 # macOS
sudo apt install ffmpeg             # Ubuntu/Debian
winget install ffmpeg               # Windows
```

### Per-video cost breakdown

| Stage | Cost |
|---|---|
| Claude (script + SEO + affiliates, with caching) | $0.10 – $0.30 |
| DALL-E 3 HD scene images (~12) | $0.96 |
| DALL-E 3 thumbnail | $0.08 |
| Whisper subtitles (8 min) | $0.05 |
| ElevenLabs (Starter, amortized) | $0.20 |
| YouTube keyword research, analytics, upload, music | free |
| **Total** | **~$1.40** |

---

## 3. Install

Requires Python 3.10+ and ffmpeg.

```bash
cd youtube-content-factory
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill in keys; YOUTUBE_API_KEY and PIXABAY_API_KEY are optional
# drop client_secrets.json next to pipeline.py if you'll be uploading
```

---

## 4. Run it

### One-shot end-to-end with the works

```bash
python pipeline.py full \
  --niche "AI Tools for Productivity" \
  --market US \
  --minutes 8 \
  --music-query "uplifting corporate" \
  --upload --upload-privacy unlisted
```

Cost gate → live keyword research → analytics-aware plan → script → audio + images → SEO → affiliates → thumbnail → final.mp4 → subtitles → music duck-mix → upload.

Skip stages: `--no-subtitles`, `--no-thumbnail`, omit `--upload`, omit both `--music-*` flags.

### Per stage

```bash
# Optional: fresh research before generating anything
python pipeline.py research --query "ai productivity tools" --region US
python pipeline.py analytics-pull --days 28   # needs prior uploads

# Plan + script (auto-load research + analytics if available)
python pipeline.py plan --niche "AI Tools for Productivity"
python pipeline.py script --niche "AI Tools for Productivity" --idea-index 1 --minutes 8

# Production
python pipeline.py produce --video-dir output/<slug>
python pipeline.py seo --video-dir output/<slug> --keywords "ai productivity"
python pipeline.py affiliates --video-dir output/<slug> --niche "AI productivity"
python pipeline.py thumbnail --video-dir output/<slug>

# Editing
python pipeline.py assemble --video-dir output/<slug>
python pipeline.py subtitle --video-dir output/<slug>
python pipeline.py music --video-dir output/<slug> --music-query "lo-fi"
# Or with your own track:
python pipeline.py music --video-dir output/<slug> --music-file ~/music/track.mp3

# Publish
python pipeline.py upload --video-dir output/<slug> --privacy unlisted
```

### Voice cloning workflow

```bash
# 1. Clone in the ElevenLabs UI (Creator tier required).
# 2. Find your new voice's ID:
python pipeline.py voices
# 3. Paste it into ELEVENLABS_VOICE_ID in .env.
# 4. Run normally — pipeline transparently uses your cloned voice.
```

### Feedback loop

```bash
# Run nightly via cron after you've published a few videos:
python pipeline.py analytics-pull --days 28

# All future plan/script/seo runs will see "what worked" and
# "what underperformed" in the prompt context — automatically.
```

### Cost gate

`full` always shows an itemized estimate before charging. In a non-interactive shell, pass `--approve`.

---

## 5. Why this is a "10/10" pipeline

What you get from one command:

- **Real video file out**: 1080p MP4 with Ken Burns motion.
- **Subtitles burned in**: Whisper-perfect captions, the single biggest Shorts-retention lever.
- **Music bed with sidechain ducking**: music auto-drops 12 dB when the narrator speaks, rises in pauses.
- **Finished thumbnail**: DALL-E background + Pillow text overlay in YouTube-yellow.
- **Live keyword research**: YouTube `search.list` data feeds real top-performing titles into the SEO prompt.
- **Analytics feedback loop**: separate OAuth scope pulls past video CTR/AVD/views; "what's winning on this channel" goes into the next prompt.
- **Voice cloning**: drop the cloned voice ID into `.env`; the rest is automatic.
- **Auto-upload**: official Data API, with title/description/tags/thumbnail wired in.
- **Cost gate**: itemized estimate + `y/N` before any spend.
- **Resumable**: every stage saves JSON; a failed `upload` doesn't force you to regenerate audio.

Each stage is independent, so when (not if) one provider's pricing or API changes, you swap that one module.

---

## 6. Troubleshooting

| Symptom | Fix |
|---|---|
| `ConfigError: Missing required environment variable` | Copy `.env.example → .env` and fill in keys. |
| `ffmpeg/ffprobe not found on PATH` | Install ffmpeg (§2f). |
| `Missing client_secrets.json` | Download from Google Cloud Console (§2d). |
| First `upload` shows OAuth verification warning | Add yourself as a test user under OAuth consent screen, or publish the app. |
| `analytics-pull` says "no videos found" | Upload some videos first; fresh uploads can take ~24h to appear in Analytics. |
| `research` returns empty list | Either YouTube quota exhausted (10k units/day) or query is too narrow. Try a broader query. |
| Pixabay search fails | Set `PIXABAY_API_KEY` or pass `--music-file` to a local audio file. |
| OpenAI `billing_hard_limit_reached` | Add credit at platform.openai.com/account/billing. |
| ElevenLabs `401` | Wrong API key, or voice ID isn't accessible to your tier. |
| Claude `rate_limit_error` | SDK auto-retries; raise your usage tier in Console if it persists. |
| Thumbnail uses Pillow default font | Install a TTF: `apt install fonts-dejavu` or copy Arial Bold into `~/.fonts/`. |
| `subtitles` filter fails on Windows paths | Use forward slashes in `--video-dir`. |
| Music sidechain too aggressive | Lower `duck_db` in `src/music.py:mix_under_video` (default 12). |
