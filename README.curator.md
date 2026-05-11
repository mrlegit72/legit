# Zero-Cost Autonomous Curation Agent

A single Python script that:

1. **Strategist** — pulls Google News RSS (`feedparser`).
2. **Researcher** — picks the top unseen trending stories.
3. **Editor** — uses LangChain + Claude to compose a minimalist X post
   (3 sentences max, blank-line spacing, no hashtags or emojis).
4. **Database** — dedupes via local SQLite so the same story is never posted
   twice.
5. **Connector** — posts with `tweepy` against the X Free Tier.

Designed to run for free on GitHub Actions on an hourly cron.

## Files

| File                              | Purpose                                  |
| --------------------------------- | ---------------------------------------- |
| `curator.py`                      | Single-script agent                      |
| `requirements.txt`                | Python deps                              |
| `.github/workflows/curator.yml`   | Hourly GitHub Actions job                |
| `.env.example`                    | Template for local secrets               |

## Local run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in real values
CURATOR_DRY_RUN=true python curator.py   # safe — prints, does not post
python curator.py                        # live
```

## GitHub Actions

Add these repository secrets (Settings -> Secrets and variables -> Actions):

- `ANTHROPIC_API_KEY`
- `X_API_KEY`
- `X_API_SECRET`
- `X_ACCESS_TOKEN`
- `X_ACCESS_TOKEN_SECRET`
- `X_BEARER_TOKEN` (optional)

The workflow commits the updated `curator_state.sqlite3` back to the branch on
each run so dedup state persists across runs. Trigger manually from the Actions
tab (with optional `dry_run=true`) or wait for the hourly cron.

## X Free Tier note

The Free Tier of the X API allows a small number of writes per month. Tune
`CURATOR_MAX_POSTS` (default `3`) and the cron schedule so you stay inside the
quota.

## Security

Never commit `.env` or paste raw API keys into chat. If a key is exposed,
rotate it immediately from the X developer portal.
