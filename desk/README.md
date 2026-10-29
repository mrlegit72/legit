# Solana memecoin desk

Six agents with hard handoffs: SCOUT → FILTER → ANALYST → EXECUTOR → RISK, and LOGGER recording all of it.
Paper mode needs only Python 3.9+. Live mode also needs `pip install -r desk/requirements.txt`.

```bash
python3 -m desk.desk --mode paper --balance 1000 --until 07:00   # run overnight, recap at 7am
python3 -m unittest discover -s desk/tests -t .                  # tests (offline)
```

Logs go to `desk_logs/<mode>/`: `kills.jsonl` (each kill and the rule that killed it), `trades.jsonl` (entry, size, score, score breakdown, exit, reason), `recap.md` (the morning recap).
Ctrl-C stops early and still writes the recap. `state.json` holds open positions, so restarting picks them back up.

At the `--until` time the desk stops buying and writes the recap. It keeps watching any open positions until their stop or trail closes them.

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

## Live mode (real money)
```bash
pip install -r desk/requirements.txt
solana-keygen new -o ~/desk-keypair.json      # a NEW wallet used only for this
# fund it: USDC is the trading balance, plus ~0.05 SOL for fees
export SOLANA_KEYPAIR=~/desk-keypair.json
export HELIUS_API_KEY=...                     # or SOLANA_RPC_URL=...
python3 -m desk.desk --mode live --confirm-live --until 07:00
```
- **Same rules.** Paper and live share one frozen rule set, and only the broker differs.
- **Balance** is the wallet's USDC, read at startup. Each trade uses 8% of it.
- **Swaps** go through Jupiter (`lite-api.jup.ag`, override with `JUP_API_URL` / `JUP_API_KEY`). They're signed locally, and the key never leaves your machine.
- **Fills are measured from the wallet.** What a trade cost and what it returned comes from the token and USDC balances before and after, not from the quote. So a swap that landed after its confirmation timed out is still recorded correctly.
- **Entry guard:** if Jupiter's quote would fill more than 3% above the DexScreener price, the buy is skipped and logged as `buy_failed`. Exits have no such guard, because getting out matters more.
- **A failed sell** is logged as `sell_failed`. The position stays open, and the next price check (every 15 s) tries again if the price is still below the stop.
- **Startup refuses** if `--confirm-live` is missing, the keypair or RPC isn't set, the wallet has no USDC, or it has less than 0.02 SOL.
- **Use a dedicated wallet holding only what you're willing to lose.** `.gitignore` excludes `*keypair*.json` and `id.json`. Never commit a key.
