"""Main loop: SCOUT -> FILTER -> ANALYST -> EXECUTOR -> RISK, LOGGER watching all."""
import argparse
import datetime as dt
import signal
import time

from .agents import Analyst, Executor, Filter, LiveBroker, Logger, PaperBroker, Risk, Scout
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
    ap.add_argument("--balance", type=float, default=1000.0, help="starting paper balance, USD")
    ap.add_argument("--hours", type=float, default=8.0)
    ap.add_argument("--until", help="local HH:MM to stop and write the recap, e.g. 07:00")
    ap.add_argument("--logs", default="desk_logs")
    ap.add_argument("--smart-wallets", default="smart_wallets.txt")
    args = ap.parse_args(argv)

    rt = Runtime()
    broker = PaperBroker(rt.paper_slippage_pct) if args.mode == "paper" else LiveBroker()
    logger = Logger(args.logs, args.mode)
    desk = Desk(LiveMarket(args.smart_wallets), logger, broker, args.balance, rt)
    end = _deadline(args)
    stop = {"now": False}
    signal.signal(signal.SIGINT, lambda *_: stop.update(now=True))
    signal.signal(signal.SIGTERM, lambda *_: stop.update(now=True))

    next_scan = 0.0
    while time.time() < end and not stop["now"]:
        try:
            if time.time() >= next_scan:
                desk.scan()
                next_scan = time.time() + rt.scan_every_s
            desk.manage()
        except Exception as e:  # a bad API response must not kill the night
            print(f"[warn] cycle error: {e!r}")
        time.sleep(rt.position_poll_s)

    # Open positions are left to their stops; the recap marks them at last price.
    print(desk.recap())


if __name__ == "__main__":
    main()
