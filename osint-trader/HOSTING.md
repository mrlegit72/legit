# Hosting osint-trader for free (or close to it)

You don't need a VPS. Here are real free-tier options ranked by how well they
fit a polling-based news pipeline.

> Anthropic does **not** sell always-on application hosting. "Run it on
> Claude" really means "use Claude as the brain and host the orchestration
> somewhere else." That somewhere can be free.

## TL;DR — the cheapest working path

| Component             | Service           | Free tier            | What it does                  |
| --------------------- | ----------------- | -------------------- | ----------------------------- |
| Orchestration         | GitHub Actions    | 2 000 min/mo (public)| Runs `osint-tick` every 10 min |
| State                 | Turso libSQL      | 9 GB                 | Cross-invocation SQLite        |
| Brain                 | Anthropic API     | pay-per-use          | Opus 4.7 + Batch API (-50 %)   |
| Alerts                | Telegram Bot API  | free                 | Notifications                  |
| Dashboard (optional)  | Render free Web   | sleeps after 15 min  | The FastAPI dashboard          |

**Total fixed cost: $0/month**. Variable cost is just Claude tokens —
typically ~$2–5/month at 10-min ticks if you turn on prompt caching + Batch
mode.

---

## Option 1 — GitHub Actions (recommended)

The repo ships `.github/workflows/osint-tick.yml`. Each run:

1. Acquires the leader lock (Actions' `concurrency` block also prevents overlap).
2. Restores SQLite state (from cache, or pulls Turso).
3. Polls RSS + GDELT, runs analyst, sizes & "trades" (dry_run by default).
4. Pushes state back.

### Setup
```bash
# 1. Fork the repo or push your copy
# 2. Add Actions secrets (Settings → Secrets and variables → Actions):
#       ANTHROPIC_API_KEY        (required)
#       TELEGRAM_BOT_TOKEN       (optional, for alerts)
#       TELEGRAM_ALERT_CHAT_ID   (optional)
#       TURSO_DATABASE_URL       (optional but recommended)
#       TURSO_AUTH_TOKEN         (optional)
# 3. Enable Actions on the repo. The cron starts firing within 10 min.
```

### State persistence

Two options inside the workflow:

| Method               | Pros                              | Cons                               |
| -------------------- | --------------------------------- | ---------------------------------- |
| Actions cache        | Default, zero setup               | ~5 GB/repo, sometimes evicted      |
| Turso libSQL         | True remote DB, multi-region      | One-time `turso db create` step    |

For Turso: `turso db create osint-trader && turso db tokens create osint-trader`, paste both into Actions secrets.

### Limits

- Min cron interval is **5 min**, not realtime. If you need Telegram
  realtime ingestion, run the full daemon on Option 2/3 instead.
- Public repos only for unlimited free minutes. Private repos get 2 000 min/mo.
- Telegram OSINT (Telethon) does **not** work here — it needs a persistent
  connection. RSS + GDELT do all the heavy lifting on the free path.

## Option 2 — Modal (best free-tier daemon)

Modal gives **$30/month** free credit which buys ~24/7 of a small CPU
container. Wrap the orchestrator in a `@modal.function(schedule=Period(...))`:

```python
import modal

app = modal.App("osint-trader")
image = modal.Image.debian_slim().pip_install_from_pyproject("pyproject.toml")
secrets = [modal.Secret.from_name("anthropic"), modal.Secret.from_name("telegram")]

@app.function(image=image, secrets=secrets, schedule=modal.Period(minutes=5))
def tick():
    from osint_trader.scripts.tick import tick as _tick
    import asyncio
    asyncio.run(_tick(window_minutes=10))
```

```bash
modal run -d osint_modal_app.py    # deploy persistent schedule
```

State lives in a Modal `Volume` mounted at `/data`.

## Option 3 — Fly.io (full daemon, $0–$5/mo)

Fly's free tier allows three shared-CPU 256 MB VMs. The full `osint-trader`
daemon fits comfortably (it idles at ~80 MB).

```bash
fly launch --no-deploy --name my-osint-trader
fly secrets set ANTHROPIC_API_KEY=sk-ant-... TELEGRAM_BOT_TOKEN=...
fly volumes create osint_data --size 1
fly deploy
```

Add to `fly.toml`:
```toml
[mounts]
  source = "osint_data"
  destination = "/data"

[env]
  DATABASE_URL = "sqlite+aiosqlite:////data/osint_trader.db"
```

This is the only option that supports Telegram realtime.

## Option 4 — Render / Railway free Web Service

These work for the **dashboard** (FastAPI on `:9109`) but the free tiers
sleep after 15 min of inactivity, so they're a bad fit for the orchestrator
itself. Recommended pairing: Actions/Modal/Fly for the daemon, Render for
the dashboard.

```yaml
# render.yaml
services:
  - type: web
    name: osint-dashboard
    runtime: python
    rootDir: osint-trader
    buildCommand: pip install -e ".[dashboard]"
    startCommand: uvicorn osint_trader.dashboard.app:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: ANTHROPIC_API_KEY
        sync: false
      - key: DATABASE_URL
        value: sqlite+aiosqlite:///osint_trader.db
```

## Option 5 — Self-host with docker-compose

If you have any always-on box (Raspberry Pi, old laptop, $5 home VPS):

```bash
git clone <your fork> && cd osint-trader
cp .env.example .env       # set ANTHROPIC_API_KEY etc.
docker compose up -d
```

Brings up trader (:9108 metrics), dashboard (:9109), Prometheus (:9090),
Grafana (:3000 anonymous viewer).

---

## Cost knobs (turn on to cut Claude tokens)

1. **Prompt caching** is already on. System prompt + market list become
   ~90 % cheaper after the first call.
2. **Batch API** (`BatchAnalyst`): 50 % discount for non-realtime
   processing. Set `ANALYST_MODE=batch` in env for the tick mode.
3. **Haiku fallback** kicks in automatically when Opus times out
   (`ANALYST_TIMEOUT_S=8`). For low-stakes runs you can flip the primary
   to Haiku too:
   ```bash
   ANTHROPIC_MODEL=claude-haiku-4-5-20251001
   ```
4. **Lower `min_confidence`** is cheaper at the *risk* level (more skips
   before fact-check spends another call). Defaults are safe but tighten
   the bar if you see noise.

## What you cannot do for free
- **Live trading with USDC on Polygon** needs gas (a few pennies/tx) +
  a funded proxy wallet. Stay in `dry_run` until you've watched it for a
  week. `TRADE_MODE=paper` records would-be fills without spending USDC.
- **Anthropic API access** itself is not free; you pay per token. Budget
  $3–15 USD/month at 10-min ticks; less with batch mode.

## Recommended starter stack

For someone who wants to "just run it":

1. Fork this repo (public).
2. Sign up for Anthropic, create an API key, put $20 on the account.
3. Add the key to Actions secrets as `ANTHROPIC_API_KEY`.
4. Sign up for Turso → `turso db create osint-trader` → add URL + token to
   Actions secrets.
5. Sign up for Telegram BotFather → `/newbot` → add token + chat id.
6. Enable Actions on your fork.

You'll have a 24/7 dry-run signal pipeline costing you under $5/month
including all Anthropic calls.
