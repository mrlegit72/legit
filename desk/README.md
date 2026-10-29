# Solana memecoin desk

Six agents with hard handoffs: SCOUT → FILTER → ANALYST → EXECUTOR → RISK, and LOGGER recording all of it.
Python 3.9+, standard library only.

```bash
python3 -m desk.desk --mode paper --balance 1000 --until 07:00   # run overnight, recap at 7am
python3 -m unittest discover -s desk/tests -t .                  # tests (offline)
```

Logs go to `desk_logs/`: `kills.jsonl` (each kill and the rule that killed it), `trades.jsonl` (entry, size, score, score breakdown, exit, reason), `recap.md` (the morning recap).
Ctrl-C stops early and still writes the recap.

## Rules
Every rule is in `config.py` as a frozen dataclass, and no CLI flag changes them. Paper and live use the same object.

| Agent | Behaviour |
|---|---|
| Scout | Finds coins via the DexScreener profile/boost/CTO feeds and GeckoTerminal new pools. Watches each coin until it's 30 min to 72 h old with a $300k–$20M mcap on Raydium/PumpSwap/Pump.fun. |
| Filter | Applies the 8 kill rules in order, stopping at the first hit. **Data it can't verify counts as a hit.** A coin that's killed is never evaluated again. |
| Analyst | Scores 0–100: momentum 20, buyers 15, buy/sell 20, holder growth 15, liq/mcap 15, smart wallets 15. It waits 5 min for a second holder count and re-runs the filter on fresh data. Under 70 dies. |
| Executor | Puts 8% of free cash into each trade. One entry per coin, and it never adds to a position. When nothing passes, it does nothing. |
| Risk | Sets the stop at −6% from the fill price before the position is recorded. At +12% it switches to a trailing stop 6% below the peak. The stop only ratchets up. |

## Data sources and known gaps
- **RugCheck** (`/v1/tokens/{mint}/report`): mint/freeze authority, LP lock %, top holders (AMM/locker accounts excluded), dev balance, rug history, holder count.
- **trench.bot**: bundle %. If it's unreachable or returns no data, rule 7 kills everything. The kill logs will show `bundle data unverified`.
- **Unique buyers** is approximated by the 1h buy *transaction* count from DexScreener, which doesn't expose unique wallets.
- **Smart wallets** needs `smart_wallets.txt` (one address per line) plus `HELIUS_API_KEY` or `SOLANA_RPC_URL`. Without them this component scores 0, which only makes the desk stricter.
- The field names for RugCheck and trench.bot were written without live access to those APIs. Run paper mode first and read `kills.jsonl`. If one rule is killing 100% of coins with "unverified", a field name needs fixing.
- Paper fills assume 1% slippage on each side. Stops are checked every 15 s, so a fast dump can exit well below the stop. The logs record the real exit price, not the stop price.

## Live mode
`--mode live` refuses to start: `LiveBroker` is deliberately unimplemented. Once the paper logs look clean, implement `buy`/`sell` (for example with the Jupiter swap API and a dedicated hot wallet holding only the trading balance) behind the same interface.
Note that the process stops at `--until`; open positions are then no longer managed. For live trading, either keep it running or close positions before stopping.
