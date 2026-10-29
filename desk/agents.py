"""The six desk agents. Each one only talks to the next one in line."""
import json
import os
import time
from collections import Counter
from dataclasses import dataclass, asdict
from typing import Optional

from .config import RULES, KILL_RULES, Rules, Runtime
from .data import Pair, Security


def _clip(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


# ---------------------------------------------------------------- SCOUT
class Scout:
    def __init__(self, rules: Rules = RULES):
        self.r = rules

    def in_window(self, p: Pair, now: float) -> bool:
        age = p.age_min(now)
        return (self.r.min_age_min <= age <= self.r.max_age_h * 60
                and self.r.min_mcap <= p.mcap <= self.r.max_mcap
                and any(d in p.dex for d in self.r.dexes))

    def too_old(self, p: Pair, now: float) -> bool:
        return p.age_min(now) > self.r.max_age_h * 60


# ---------------------------------------------------------------- FILTER
class Filter:
    """Returns (rule_number, detail) for the first rule hit, or None if clean.
    Unknown data counts as a hit: we only buy what we could verify."""

    def __init__(self, rules: Rules = RULES):
        self.r = rules

    def check(self, p: Pair, s: Security):
        r = self.r
        if s.mint_revoked is None or s.freeze_revoked is None:
            return 1, "authority status unverified"
        if not s.mint_revoked or not s.freeze_revoked:
            return 1, f"mint_revoked={s.mint_revoked} freeze_revoked={s.freeze_revoked}"
        if s.lp_safe_pct is None:
            return 2, "LP lock/burn status unverified"
        if s.lp_safe_pct < 95:
            return 2, f"only {s.lp_safe_pct:.1f}% of LP burned/locked"
        if p.liquidity < r.min_liquidity:
            return 3, f"liquidity ${p.liquidity:,.0f}"
        if p.vol_1h < r.min_vol_1h:
            return 4, f"1h volume ${p.vol_1h:,.0f}"
        if s.top10_pct is None:
            return 5, "holder distribution unverified"
        if s.top10_pct > r.max_top10_pct:
            return 5, f"top10 own {s.top10_pct:.1f}%"
        if s.dev_pct is None or s.dev_past_rugs is None:
            return 6, "dev wallet unverified"
        if s.dev_pct > r.max_dev_pct:
            return 6, f"dev holds {s.dev_pct:.1f}%"
        if s.dev_past_rugs:
            return 6, "dev has past rugs"
        if s.bundled_pct is None:
            return 7, "bundle data unverified"
        if s.bundled_pct > r.max_bundled_pct:
            return 7, f"{s.bundled_pct:.1f}% bundled"
        if p.change_1h >= r.max_change_1h_pct:
            return 8, f"up {p.change_1h:.0f}% in 1h"
        return None


# ---------------------------------------------------------------- ANALYST
class Analyst:
    WEIGHTS = {"momentum": 20, "unique_buyers": 15, "buy_sell": 20,
               "holder_growth": 15, "liq_mcap": 15, "smart_wallets": 15}

    def __init__(self, rules: Rules = RULES):
        self.r = rules

    def score(self, p: Pair, holders_then: Optional[int], holders_now: Optional[int],
              minutes: float, smart: int):
        w = self.WEIGHTS
        c = p.change_1h
        mom = 0.0 if c <= 0 else _clip(c / 40)
        if p.change_5m < 0:
            mom *= 0.5
        # DexScreener gives buy txn count, not unique wallets: used as the proxy.
        buyers = _clip(p.buys_1h / 400)
        ratio = p.buys_1h / max(p.sells_1h, 1)
        bs = _clip(ratio - 1.0)  # 1.0 -> 0, 2.0+ -> full
        growth = 0.0
        if holders_then and holders_now and minutes > 0:
            per_hour = (holders_now - holders_then) / holders_then * 100 * 60 / minutes
            growth = _clip(per_hour / 30)  # +30% holders/hour -> full
        lm = _clip(((p.liquidity / p.mcap if p.mcap else 0) - 0.03) / 0.12)
        sw = 0.0 if smart <= 0 else (8 / 15 if smart == 1 else 1.0)
        parts = {"momentum": mom, "unique_buyers": buyers, "buy_sell": bs,
                 "holder_growth": growth, "liq_mcap": lm, "smart_wallets": sw}
        breakdown = {k: round(v * w[k], 1) for k, v in parts.items()}
        return round(sum(breakdown.values())), breakdown

    def passes(self, score: int) -> bool:
        return score >= self.r.min_score


# ---------------------------------------------------------------- RISK
@dataclass
class Position:
    mint: str
    symbol: str
    pair_address: str
    entry: float
    qty: float
    cost: float
    score: int
    stop: float
    peak: float
    trailing: bool
    opened: float


class Risk:
    def __init__(self, rules: Rules = RULES):
        self.r = rules

    def initial_stop(self, entry: float) -> float:
        return entry * (1 + self.r.stop_pct / 100)

    def update(self, pos: Position, price: float) -> Optional[str]:
        """Ratchet the stop, then say whether to exit. The stop never moves down."""
        pos.peak = max(pos.peak, price)
        if not pos.trailing and pos.peak >= pos.entry * (1 + self.r.trail_trigger_pct / 100):
            pos.trailing = True
        if pos.trailing:
            pos.stop = max(pos.stop, pos.peak * (1 - self.r.trail_distance_pct / 100))
        if price <= pos.stop:
            return "trailing stop" if pos.trailing else "stop -6%"
        return None


# ---------------------------------------------------------------- EXECUTOR
class PaperBroker:
    def __init__(self, slippage_pct: float):
        self.slip = slippage_pct / 100

    def buy(self, p: Pair, usd: float):
        fill = p.price * (1 + self.slip)
        return fill, usd / fill, usd

    def sell(self, pos: Position, price: float):
        fill = price * (1 - self.slip)
        return fill, pos.qty * fill


class Executor:
    def __init__(self, broker, risk: Risk, logger, rules: Rules = RULES):
        self.broker, self.risk, self.log, self.r = broker, risk, logger, rules
        self.cash = 0.0
        self.positions = {}
        self.traded = set()

    def try_enter(self, p: Pair, score: int, breakdown: dict, now: float) -> bool:
        if p.mint in self.traded or p.mint in self.positions:
            return False  # one entry per coin, never average down
        usd = self.cash * self.r.max_trade_pct / 100
        if usd <= 0 or p.price <= 0:
            return False
        self.traded.add(p.mint)  # one shot per coin, even if the order fails
        res = self.broker.buy(p, usd)
        if not res:
            self.log.failed("buy", p, usd)
            return False
        fill, qty, spent = res
        # Stop is set from the real fill before the position is tracked.
        stop = self.risk.initial_stop(fill)
        self.cash -= spent
        pos = Position(p.mint, p.symbol, p.pair_address, fill, qty, spent, score,
                       stop, fill, False, now)
        self.positions[p.mint] = pos
        self.log.entry(pos, breakdown)
        return True

    def mark(self, mint: str, price: float, now: float):
        pos = self.positions.get(mint)
        if not pos or price <= 0:
            return
        reason = self.risk.update(pos, price)
        if reason:
            res = self.broker.sell(pos, price)
            if not res:
                self.log.failed("sell", pos, pos.cost)
                return  # still open; the stop says exit again on the next check
            fill, proceeds = res
            self.cash += proceeds
            del self.positions[mint]
            self.log.exit(pos, fill, proceeds, reason, now)

    def equity(self, prices: dict) -> float:
        return self.cash + sum(p.qty * prices.get(m, p.entry) for m, p in self.positions.items())


# ---------------------------------------------------------------- LOGGER
class Logger:
    def __init__(self, log_dir: str, mode: str, quiet: bool = False):
        os.makedirs(log_dir, exist_ok=True)
        self.dir, self.mode, self.quiet = log_dir, mode, quiet
        self.scanned = set()
        self.kills = Counter()
        self.trades = []

    def _write(self, name, rec):
        rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": self.mode, **rec}
        with open(os.path.join(self.dir, name), "a") as f:
            f.write(json.dumps(rec) + "\n")
        if not self.quiet:
            print(f"[{rec['ts']}] {name[:-6]}: " + json.dumps({k: v for k, v in rec.items()
                                                                 if k not in ("ts", "mode")}))

    def scan(self, mint):
        self.scanned.add(mint)

    def kill(self, p: Pair, rule, detail: str):
        key = rule if isinstance(rule, int) else str(rule)
        self.kills[key] += 1
        label = KILL_RULES.get(rule, rule)
        self._write("kills.jsonl", {"mint": p.mint, "symbol": p.symbol, "rule": rule,
                                    "rule_text": label, "detail": detail})

    def failed(self, side: str, coin, usd: float):
        self._write("trades.jsonl", {"event": f"{side}_failed", "mint": coin.mint,
                                     "symbol": coin.symbol, "size_usd": round(usd, 2)})

    def entry(self, pos: Position, breakdown: dict):
        self._write("trades.jsonl", {"event": "entry", "mint": pos.mint, "symbol": pos.symbol,
                                     "entry": pos.entry, "size_usd": round(pos.cost, 2),
                                     "score": pos.score, "breakdown": breakdown,
                                     "stop": pos.stop})

    def exit(self, pos: Position, fill: float, proceeds: float, reason: str, now: float):
        pnl = proceeds - pos.cost
        t = {"event": "exit", "mint": pos.mint, "symbol": pos.symbol, "entry": pos.entry,
             "exit": fill, "size_usd": round(pos.cost, 2), "score": pos.score,
             "pnl_usd": round(pnl, 2), "pnl_pct": round(pnl / pos.cost * 100, 2),
             "reason": reason, "held_min": round((now - pos.opened) / 60, 1)}
        self.trades.append(t)
        self._write("trades.jsonl", t)

    def recap(self, start_balance: float, executor: Executor, prices: dict) -> str:
        wins = [t for t in self.trades if t["pnl_usd"] > 0]
        losses = [t for t in self.trades if t["pnl_usd"] <= 0]
        best = max(self.trades, key=lambda t: t["pnl_pct"], default=None)
        worst = min(self.trades, key=lambda t: t["pnl_pct"], default=None)
        final = executor.equity(prices)
        lines = [f"# Morning recap ({self.mode}) {time.strftime('%Y-%m-%d %H:%M')}", "",
                 f"- Scanned: {len(self.scanned)} coins",
                 f"- Killed: {sum(self.kills.values())}"]
        for rule in list(KILL_RULES) + ["analyst <70"]:
            n = self.kills.get(rule if isinstance(rule, int) else str(rule), 0)
            label = f"rule {rule}: {KILL_RULES[rule]}" if isinstance(rule, int) else rule
            lines.append(f"  - {label}: {n}")
        lines += [f"- Traded: {len(executor.traded)} (closed {len(self.trades)}, "
                  f"still open {len(executor.positions)})",
                  f"- W/L: {len(wins)}/{len(losses)}",
                  f"- Best: {best['symbol']} {best['pnl_pct']:+.1f}%" if best else "- Best: n/a",
                  f"- Worst: {worst['symbol']} {worst['pnl_pct']:+.1f}%" if worst else "- Worst: n/a",
                  f"- Balance: ${start_balance:,.2f} -> ${final:,.2f} "
                  f"({(final / start_balance - 1) * 100:+.2f}%)"]
        for pos in executor.positions.values():
            lines.append(f"  - open: {pos.symbol} entry {pos.entry:.8g} stop {pos.stop:.8g}")
        text = "\n".join(lines) + "\n"
        with open(os.path.join(self.dir, "recap.md"), "w") as f:
            f.write(text)
        return text
