# osint-trader

AI-driven OSINT pipeline that watches Middle-East news 24/7, asks Claude
whether each event materially shifts the truth probability of specific
[Polymarket](https://polymarket.com) prediction markets, sizes a position
with fractional Kelly, and (optionally) places it on the CLOB.

It's a 10x rebuild of the workflow described in
[the n8n + Claude + Polymarket article](https://x.com/ridark_eth/status/2050199909324698106)
— same idea, but a real production-shaped system instead of a tutorial graph.

## What's different vs the article

| Article | This project |
|---|---|
| Single source (Telegram only) | Telegram + RSS (Reuters/BBC/AJ/ToI) + GDELT 2.0 + optional Nitter |
| n8n GUI workflow | Pure async-Python service, no n8n process required |
| One-shot Claude prompt | Pre-filter → corroboration → Claude → strict-JSON parse → post-hoc guards |
| Hardcoded API keys & hash in source | `.env` + `pydantic-settings`, nothing checked in |
| No deduplication | Hash + rapidfuzz fuzzy dedup with sliding window |
| No corroboration logic | Cross-source corroboration boost (multi-outlet > single rumor) |
| Manual sizing | Fractional-Kelly sizing with confidence/edge floors and bankroll caps |
| No live market data | Polymarket Gamma API snapshots; live edge recomputed before sizing |
| No persistence | SQLite store of every event/signal/trade for audit + backtest |
| No backtesting | `osint-backtest events.jsonl` replays through the full pipeline |
| No risk controls | Daily loss circuit breaker + error cooldown |
| No tests | 18 unit tests across pricing, sizing, dedup, corroboration, persistence |

## Quick start

```bash
cd osint-trader
python -m venv .venv && . .venv/bin/activate
pip install -e .
cp .env.example .env   # then fill in your keys

# 1. Sanity-check Polymarket connectivity & your slugs
python -m osint_trader.scripts.refresh_markets

# 2. Try the Claude pipeline against historical events without real money
osint-backtest examples/sample_events.jsonl

# 3. Run the live pipeline (defaults to TRADE_MODE=dry_run)
osint-trader
```

## Configuration

- **Environment variables** — `.env.example` documents every key.
  `TRADE_MODE` is the master switch: `dry_run` (log only) → `paper` (simulate
  fills, persist) → `live` (real Polymarket orders).
- **`config/markets.yaml`** — the markets the analyst is allowed to act on.
  Edit slugs/keywords here; everything else flows from there.
- **`config/sources.yaml`** — Telegram channels, RSS feeds, GDELT query.
  Each source has a credibility weight that feeds corroboration scoring.
- **`config/prompts/analyst.md`** — the analyst system prompt.
  Strict JSON contract, no markdown.

## Architecture

```
            ┌──────────────┐
Telegram ──▶│              │
RSS feeds ─▶│   sources/   │── NewsEvent ──▶ asyncio.Queue
GDELT API ─▶│              │
            └──────────────┘
                                       │
                                       ▼
                       ┌──────────────────────────────┐
                       │ Deduper (hash + rapidfuzz)   │
                       │ Pre-filter (keyword/title)   │
                       │ Corroboration (window x src) │
                       └──────────────────────────────┘
                                       │
                                       ▼
                       ┌──────────────────────────────┐
                       │ ClaudeAnalyst                │
                       │  - opus-4-7 (configurable)   │
                       │  - strict JSON               │
                       │  - retry/repair on bad JSON  │
                       └──────────────────────────────┘
                                       │
                                       ▼
                       ┌──────────────────────────────┐
                       │ Risk: confidence/edge floors │
                       │ Fractional Kelly sizing      │
                       │ Bankroll cap + breaker       │
                       └──────────────────────────────┘
                                       │
                                       ▼
                       ┌──────────────────────────────┐
                       │ PolymarketClient             │
                       │  read: gamma-api             │
                       │  write: py-clob-client       │
                       │ Telegram alerts              │
                       │ SQLite store                 │
                       └──────────────────────────────┘
```

## Risk math

For a binary YES/NO market priced at `p` per share that pays $1 if right:

- **Edge (YES)** = `prob_true - p`  (NO edge is the symmetric inverse)
- **Decimal odds** = `1/p`, payoff per $1 staked = `1/p - 1` = `b`
- **Kelly fraction** = `(b·q - (1-q)) / b`  with `q = prob_true`

`size_trade()` applies:
1. Confidence floor scaled by corroboration multiplier.
2. Live edge floor (re-checked against the current Polymarket snapshot).
3. `kelly · KELLY_FRACTION · (confidence/100)`, capped at `MAX_POSITION_PCT`.
4. Cap by free bankroll (no double-spending across simultaneous signals).

Test it:

```bash
PYTHONPATH=src python -m pytest tests/ -q
```

## Live trading

Live trading is opt-in via `TRADE_MODE=live` AND `pip install -e ".[trade]"`
to pull in `py-clob-client`. You also need:

- `POLYMARKET_PRIVATE_KEY` for an EOA holding USDC on Polygon.
- `POLYMARKET_FUNDER` set to your proxy wallet address.

The system defaults to `dry_run` so you can always sanity-check signal
quality and Telegram alerts before risking USDC.

## Backtest format

`osint-backtest` reads JSONL where each line is one historical event
plus an optional snapshot of Polymarket prices at that instant:

```json
{"text":"Reuters: Israeli airstrike hits Kharg Island oil terminal","source_kind":"rss","source_handle":"reuters.com","credibility":0.92,"language":"en","published_at":"2024-06-24T03:14:00Z","snapshots":{"kharg-island-control":{"yes_price":0.07,"no_price":0.93}}}
```

See `examples/sample_events.jsonl` for a runnable sample.

## Security notes

- **No credentials in source.** The article pasted a Telegram `API_HASH` — that
  hash and the matching `API_ID` are now public. Don't reuse them. Generate
  fresh credentials at <https://my.telegram.org>.
- The `.env` file is gitignored; the only place keys live is your local disk
  (or your secret manager of choice).
- `TRADE_MODE=live` is gated behind a separate optional install. You can't
  accidentally place real orders by running `python -m osint_trader.main`.

## License

MIT. Use at your own risk; prediction-market trading is volatile.
