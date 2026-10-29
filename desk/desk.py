"""Main loop: SCOUT -> FILTER -> ANALYST -> EXECUTOR -> RISK, LOGGER watching all."""
import argparse
import datetime as dt
import json
import os
import signal
import time
from dataclasses import asdict

from .agents import Analyst, Executor, Filter, Logger, PaperBroker, Position, Risk, Scout
from .config import Runtime
from .data import DexScreener, GeckoTerminal, Http, RugCheck, SmartWallets, TrenchBot


class LiveMarket:
    """Adapter over the real data sources. Tests swap in a fake with the same methods."""

    def __init__(self, smart_wallets_path: str):
        http = Http()
        self.dex, self.gecko = DexScreener(http), GeckoTerminal(http)
        self.rug, self.trench = RugCheck(http), TrenchBot(http)
        self.smart = SmartWallets(http, smart_wallets_path)

    def discover(self):
        return self.dex.discover_mints() | self.gecko.discover_mints()

    def pairs(self, mints):
        return self.dex.pairs_for(mints)

    def security(self, mint):
        s = self.rug.security(mint)
        s.bundled_pct = self.trench.bundled_pct(mint)
        return s

    def smart_holders(self, mint):
        return self.smart.holders_of(mint)


class Desk:
    def __init__(self, market, logger: Logger, broker, balance: float,
                 runtime: Runtime = Runtime(), clock=time.time):
        self.m, self.log, self.rt, self.clock = market, logger, runtime, clock
        self.scout, self.filter, self.analyst, self.risk = Scout(), Filter(), Analyst(), Risk()
        self.ex = Executor(broker, self.risk, logger)
        self.ex.cash = self.start_balance = balance
        self.watch = set()   # mints seen but not yet in the scout window
        self.dead = set()    # one hit = dead, never re-evaluated
        self.pending = {}    # mint -> (holders_at_filter, time) awaiting analyst
        self.prices = {}

    def scan(self):
        now = self.clock()
        self.watch |= self.m.discover()
        self.watch -= self.dead | self.ex.traded
        pairs = self.m.pairs(self.watch | set(self.pending))
        for mint in list(self.watch):
            p = pairs.get(mint)
            if p is None:
                continue
            if self.scout.too_old(p, now):
                self.watch.discard(mint)
                continue
            if mint in self.pending or not self.scout.in_window(p, now):
                continue
            self.watch.discard(mint)
            self.log.scan(mint)
            sec = self.m.security(mint)
            if self._killed(p, sec):
                continue
            self.pending[mint] = (sec.holders, now)
        self._analyze(pairs, now)

    def _killed(self, p, sec) -> bool:
        hit = self.filter.check(p, sec)
        if hit:
            self.dead.add(p.mint)
            self.pending.pop(p.mint, None)
            self.log.kill(p, *hit)
        return bool(hit)

    def _analyze(self, pairs, now):
        ready = [m for m, (_, t) in self.pending.items()
                 if (now - t) / 60 >= self.rt.holder_resample_min]
        scored = []
        for mint in ready:
            p = pairs.get(mint)
            holders_then, t0 = self.pending[mint]
            if p is None:
                continue
            sec = self.m.security(mint)  # fresh look: a coin can go bad while waiting
            if self._killed(p, sec):
                continue
            del self.pending[mint]
            score, breakdown = self.analyst.score(
                p, holders_then, sec.holders, (now - t0) / 60, self.m.smart_holders(mint))
            if self.analyst.passes(score):
                scored.append((score, p, breakdown))
            else:
                self.dead.add(mint)
                self.log.kill(p, "analyst <70", f"score {score} {breakdown}")
        for score, p, breakdown in sorted(scored, key=lambda x: -x[0]):
            self.ex.try_enter(p, score, breakdown, now)

    def manage(self):
        if not self.ex.positions:
            return
        pairs = self.m.pairs(set(self.ex.positions))
        now = self.clock()
        for mint in list(self.ex.positions):
            p = pairs.get(mint)
            if p and p.price > 0:
                self.prices[mint] = p.price
                self.ex.mark(mint, p.price, now)

    def recap(self) -> str:
        return self.log.recap(self.start_balance, self.ex, self.prices)

    # State survives a crash or restart, so open positions are never orphaned.
    def save(self, path: str):
        state = {"cash": self.ex.cash, "start_balance": self.start_balance,
                 "traded": sorted(self.ex.traded), "dead": sorted(self.dead),
                 "positions": [asdict(p) for p in self.ex.positions.values()]}
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(state, f)
        os.replace(tmp, path)

    def load(self, path: str) -> bool:
        if not os.path.exists(path):
            return False
        with open(path) as f:
            st = json.load(f)
        self.ex.cash, self.start_balance = st["cash"], st["start_balance"]
        self.ex.traded, self.dead = set(st["traded"]), set(st["dead"])
        self.ex.positions = {p["mint"]: Position(**p) for p in st["positions"]}
        return True


def _deadline(args) -> float:
    if args.until:
        h, m = map(int, args.until.split(":"))
        now = dt.datetime.now()
        end = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if end <= now:
            end += dt.timedelta(days=1)
        return end.timestamp()
    return time.time() + args.hours * 3600


def main(argv=None):
    ap = argparse.ArgumentParser(description="Solana memecoin desk")
    ap.add_argument("--mode", choices=["paper", "live"], default="paper")
    ap.add_argument("--balance", type=float, default=1000.0,
                    help="starting paper balance, USD (live uses the wallet's USDC)")
    ap.add_argument("--hours", type=float, default=8.0)
    ap.add_argument("--until", help="local HH:MM to stop buying and write the recap, e.g. 07:00")
    ap.add_argument("--logs", default=None, help="default desk_logs/<mode>")
    ap.add_argument("--smart-wallets", default="smart_wallets.txt")
    ap.add_argument("--confirm-live", action="store_true",
                    help="required with --mode live: this trades real money")
    args = ap.parse_args(argv)

    rt = Runtime()
    log_dir = args.logs or os.path.join("desk_logs", args.mode)
    if args.mode == "live":
        if not args.confirm_live:
            raise SystemExit("--mode live trades real money. Add --confirm-live if you mean it.")
        from .live import LiveBroker
        broker = LiveBroker()
        info = broker.preflight()
        print(f"[live] wallet {info['wallet']}  USDC ${info['usdc']:,.2f}  SOL {info['sol']:.4f}")
        balance = info["usdc"]
    else:
        broker, balance = PaperBroker(rt.paper_slippage_pct), args.balance

    logger = Logger(log_dir, args.mode)
    desk = Desk(LiveMarket(args.smart_wallets), logger, broker, balance, rt)
    state_path = os.path.join(log_dir, "state.json")
    if desk.load(state_path):
        if args.mode == "live":
            desk.ex.cash = balance  # the wallet is the truth, not the saved number
        print(f"[desk] resumed: {len(desk.ex.positions)} open positions, cash ${desk.ex.cash:,.2f}")
    end = _deadline(args)
    stop = {"now": False}
    signal.signal(signal.SIGINT, lambda *_: stop.update(now=True))
    signal.signal(signal.SIGTERM, lambda *_: stop.update(now=True))

    def tick(scanning: bool, next_scan: float) -> float:
        try:
            if scanning and time.time() >= next_scan:
                desk.scan()
                next_scan = time.time() + rt.scan_every_s
            desk.manage()
            desk.save(state_path)
        except Exception as e:  # a bad API response must not kill the night
            print(f"[warn] cycle error: {e!r}")
        time.sleep(rt.position_poll_s)
        return next_scan

    next_scan = 0.0
    while time.time() < end and not stop["now"]:
        next_scan = tick(True, next_scan)
    print(desk.recap())

    # No new buys after the deadline, but open positions keep their stops
    # until the stop or trail says exit. Ctrl-C leaves them in state.json.
    if desk.ex.positions and not stop["now"]:
        print(f"[desk] no new entries; watching {len(desk.ex.positions)} open positions to exit")
        while desk.ex.positions and not stop["now"]:
            tick(False, 0)
        print(desk.recap())


if __name__ == "__main__":
    main()
