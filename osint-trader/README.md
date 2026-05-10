# osint-trader

AI-driven OSINT pipeline that watches Middle-East news 24/7, asks Claude
whether each event materially shifts the truth probability of specific
[Polymarket](https://polymarket.com) prediction markets, sizes a position
with fractional Kelly, manages exits with take-profit/stop-loss, and
(optionally) places orders on the CLOB.

It's a 10x rebuild of the workflow described in
[the n8n + Claude + Polymarket article](https://x.com/ridark_eth/status/2050199909324698106)
— same idea, but a real production-shaped system instead of a tutorial graph.

## Run with only the Claude API

```bash
cd osint-trader
python -m venv .venv && . .venv/bin/activate
pip install -e .
cp .env.example .env
# edit .env → set ANTHROPIC_API_KEY=sk-ant-...
osint-trader            # dry-run mode is the default
```

Everything else is optional. RSS (Reuters/BBC/AJ/ToI) and GDELT need *zero*
credentials; Telegram OSINT and Telegram alerts both no-op gracefully when
their env vars aren't set; live trading is gated behind `pip install -e ".[trade]"`.

## Architecture

```
            ┌──────────────┐
Telegram ──▶│              │
RSS feeds ─▶│   sources/   │── NewsEvent ──▶ asyncio.Queue ──▶ metrics.queue_depth
GDELT API ─▶│              │
            └──────────────┘
                                       │
                                       ▼
                       ┌──────────────────────────────┐
                       │ Deduper (hash + rapidfuzz)   │
                       │ Pre-filter (keyword/title)   │
                       │ Corroboration (decay × cred) │
                       │ Credibility (Beta-Bernoulli) │
                       └──────────────────────────────┘
                                       │
                                       ▼
                       ┌──────────────────────────────┐
                       │ ClaudeAnalyst (Opus 4.7)     │
                       │  - cached system + markets   │
                       │  - strict JSON               │
                       │  - retry/repair              │
                       │ FactChecker (Haiku, optional)│
                       └──────────────────────────────┘
                                       │
                                       ▼
                       ┌──────────────────────────────┐
                       │ Risk gauntlet                │
                       │  · circuit breaker           │
                       │  · per-market cooldown       │
                       │  · confidence floor          │
                       │  · live edge floor           │
                       │  · liquidity floor           │
                       │  · fractional Kelly + cap    │
                       │  · scenario bucket cap       │
                       │  · order-book slippage gate  │
                       └──────────────────────────────┘
                                       │
                                       ▼
                       ┌──────────────────────────────┐
                       │ PolymarketClient             │
                       │  read: gamma-api validated   │
                       │  write: py-clob-client       │
                       │ PositionManager (TP/SL/hold) │
                       │ OrderMonitor (cancel-replace)│
                       │ Settlement → Bankroll → CB   │
                       │ Telegram alerts (tiered)     │
                       │ KillSwitch (/halt /resume)   │
                       │ Prometheus :9108/metrics     │
                       │ SQLite store                 │
                       └──────────────────────────────┘
```

## What's different vs the article

| Article | This project |
|---|---|
| Single source (Telegram only) | Telegram + RSS + GDELT 2.0 + optional Nitter |
| n8n GUI workflow | Pure async-Python service |
| One-shot Claude prompt | Pre-filter → corroboration → cached Claude → fact-check → JSON |
| Hardcoded API keys | `.env` + `pydantic-settings` |
| No deduplication | Hash + rapidfuzz fuzzy dedup, sliding window |
| No corroboration | Cross-source corroboration with **graded recency decay** |
| Static credibility | **Beta-Bernoulli per-source learning** that updates on settlement |
| Manual sizing | Fractional Kelly + confidence floor + liquidity floor |
| No portfolio caps | **Scenario buckets** cap correlated exposure (e.g. all "de-escalation" markets share a budget) |
| No market data | Polymarket Gamma API snapshots, **Pydantic-validated** |
| No status filter | Closed/archived/paused markets are skipped |
| No order book / slippage | **CLOB book walked** for max-notional within slippage budget |
| No exits | **PositionManager** runs take-profit, stop-loss, max-hold flush |
| No order monitoring | **OrderMonitor** cancel-replaces drifted/timed-out limits |
| No PnL reconciliation | **Settlement** writes realised PnL → bankroll → circuit breaker |
| No kill switch | Telegram `/halt` and `/resume` from authorised chat |
| No metrics | Prometheus exporter on `:9108/metrics` |
| Manual sizing again | **Per-market cooldown** prevents re-firing the same trade |
| Static prompt every call | **Anthropic prompt caching** on system + market list |
| No alert tiers | `info` / `actionable` / `executed` / `position` levels |
| No persistence | SQLite store of every event/signal/trade/settlement |
| No backtesting | Backtest replays JSONL through the pipeline and computes hit-rate + PnL |
| No risk controls | Daily-loss circuit breaker + error cooldown |
| No tests | 38 unit tests across pricing, sizing, dedup, corroboration, scenarios, orderbook, cooldown, credibility, persistence, position management |

## Configuration

- **`.env`** — Anthropic API key (required); everything else optional.
  `TRADE_MODE` is the master switch: `dry_run` (log only) → `paper` (simulate
  fills, persist) → `live` (real Polymarket orders).
- **`config/markets.yaml`** — markets the analyst is allowed to act on.
- **`config/sources.yaml`** — Telegram channels, RSS feeds, GDELT query.
- **`config/scenarios.yaml`** — correlation buckets with aggregate caps.
- **`config/prompts/analyst.md`** — analyst system prompt (strict JSON contract).

## Operating it

```bash
# Sanity-check Polymarket connectivity & your slugs
python -m osint_trader.scripts.refresh_markets

# Replay sample events (offline; no real bets)
osint-backtest examples/sample_events.jsonl

# Live pipeline (defaults to TRADE_MODE=dry_run)
osint-trader

# Watch metrics
curl localhost:9108/metrics
```

While running, send `/halt` to your alert bot to halt trading, `/resume` to
re-enable, `/status` to query state.

## Risk math

For a binary YES/NO market priced at `p` per share that pays $1 if right:

- **Edge (YES)** = `prob_true - p`
- **Decimal odds** = `1/p`, payoff per $1 staked = `1/p - 1` = `b`
- **Kelly fraction** = `(b·q - (1-q)) / b`  with `q = prob_true`

`size_trade()` in order: circuit breaker → per-market cooldown → confidence
floor (corroboration-adjusted) → live edge floor → liquidity floor → Kelly ×
KELLY_FRACTION × (conf/100) capped at MAX_POSITION_PCT → free bankroll cap →
scenario bucket cap → CLOB book max-notional within slippage. Skip if any
gate fails.

## Testing

```bash
PYTHONPATH=src python -m pytest tests/ -q   # 38 tests
```

## Live trading

Live trading is opt-in via `TRADE_MODE=live` AND `pip install -e ".[trade]"`
to pull in `py-clob-client`. You also need:

- `POLYMARKET_PRIVATE_KEY` for an EOA holding USDC on Polygon.
- `POLYMARKET_FUNDER` set to your proxy wallet address.

The system defaults to `dry_run` so you can always sanity-check signal
quality and Telegram alerts before risking USDC.

## Security notes

- No credentials in source. The article pasted a Telegram `API_HASH` — that
  hash and the matching `API_ID` are now public. Don't reuse them. Generate
  fresh credentials at <https://my.telegram.org>.
- The `.env` file is gitignored.
- `TRADE_MODE=live` is gated behind a separate optional install.

## License

MIT. Use at your own risk; prediction-market trading is volatile.
