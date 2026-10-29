import json
import os
import tempfile
import unittest
from dataclasses import replace

from desk.agents import Analyst, Filter, Logger, PaperBroker, Position, Risk
from desk.config import Runtime
from desk.data import Pair, RugCheck, Security
from desk.desk import Desk

NOW = 1_800_000_000.0


def pair(**kw):
    base = dict(mint="M1", pair_address="P1", symbol="GOOD", dex="raydium",
                created_ms=int((NOW - 3 * 3600) * 1000), mcap=1_000_000, liquidity=150_000,
                vol_1h=200_000, change_1h=30, change_5m=3, buys_1h=600, sells_1h=250, price=1.0)
    base.update(kw)
    return Pair(**base)


def clean_sec(**kw):
    base = dict(mint_revoked=True, freeze_revoked=True, lp_safe_pct=100, top10_pct=15,
                dev_pct=1, dev_past_rugs=False, bundled_pct=3, holders=1000)
    base.update(kw)
    return Security(**base)


class FilterTest(unittest.TestCase):
    def test_clean_passes(self):
        self.assertIsNone(Filter().check(pair(), clean_sec()))

    def test_each_rule(self):
        cases = [
            (1, pair(), clean_sec(freeze_revoked=False)),
            (1, pair(), clean_sec(mint_revoked=None)),
            (2, pair(), clean_sec(lp_safe_pct=40)),
            (3, pair(liquidity=39_999), clean_sec()),
            (4, pair(vol_1h=49_000), clean_sec()),
            (5, pair(), clean_sec(top10_pct=25.1)),
            (6, pair(), clean_sec(dev_pct=3.5)),
            (6, pair(), clean_sec(dev_past_rugs=True)),
            (7, pair(), clean_sec(bundled_pct=11)),
            (7, pair(), clean_sec(bundled_pct=None)),
            (8, pair(change_1h=80), clean_sec()),
        ]
        for rule, p, s in cases:
            self.assertEqual(Filter().check(p, s)[0], rule, (rule, s))


class AnalystTest(unittest.TestCase):
    def test_strong_coin_scores_high_even_without_smart_wallets(self):
        score, parts = Analyst().score(pair(), 1000, 1050, 5, smart=0)
        self.assertGreaterEqual(score, 70, parts)

    def test_weak_coin_dies(self):
        weak = pair(change_1h=-5, buys_1h=100, sells_1h=120, liquidity=40_000, mcap=2_000_000)
        score, _ = Analyst().score(weak, 1000, 1000, 5, smart=0)
        self.assertLess(score, 70)


class RiskTest(unittest.TestCase):
    def pos(self):
        return Position("M", "S", "P", 1.0, 100, 100, 80, Risk().initial_stop(1.0), 1.0, False, NOW)

    def test_hard_stop(self):
        p = self.pos()
        self.assertAlmostEqual(p.stop, 0.94)
        self.assertIsNone(Risk().update(p, 0.95))
        self.assertEqual(Risk().update(p, 0.939), "stop -6%")

    def test_trail_arms_at_12_and_never_moves_down(self):
        p, r = self.pos(), Risk()
        r.update(p, 1.10)
        self.assertFalse(p.trailing)
        r.update(p, 1.12)
        self.assertTrue(p.trailing)
        r.update(p, 1.50)
        high_stop = p.stop
        self.assertAlmostEqual(high_stop, 1.41)
        r.update(p, 1.45)
        self.assertEqual(p.stop, high_stop)
        self.assertEqual(r.update(p, 1.40), "trailing stop")


class FakeMarket:
    def __init__(self, pairs, secs, smart=0):
        self._pairs, self._secs, self._smart = pairs, secs, smart

    def discover(self):
        return set(self._pairs)

    def pairs(self, mints):
        return {m: self._pairs[m] for m in mints if m in self._pairs}

    def security(self, mint):
        return replace(self._secs[mint])

    def smart_holders(self, mint):
        return self._smart


class DeskTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.t = [NOW]
        self.logger = Logger(self.tmp, "paper", quiet=True)

    def desk(self, market):
        return Desk(market, self.logger, PaperBroker(1.0), 1000.0, Runtime(), clock=lambda: self.t[0])

    def read(self, name):
        path = os.path.join(self.tmp, name)
        if not os.path.exists(path):
            return []
        with open(path) as f:
            return [json.loads(l) for l in f]

    def test_full_night(self):
        pairs = {
            "GOOD": pair(mint="GOOD", symbol="GOOD"),
            "RUG": pair(mint="RUG", symbol="RUG"),
            "YOUNG": pair(mint="YOUNG", symbol="YOUNG", created_ms=int((NOW - 600) * 1000)),
            "MEH": pair(mint="MEH", symbol="MEH", change_1h=-2, buys_1h=90, sells_1h=100),
        }
        secs = {"GOOD": clean_sec(), "RUG": clean_sec(dev_pct=12),
                "YOUNG": clean_sec(), "MEH": clean_sec()}
        m = FakeMarket(pairs, secs)
        d = self.desk(m)

        d.scan()  # filter pass; analyst waits for a second holder sample
        self.assertEqual(self.read("kills.jsonl")[0]["rule"], 6)
        self.assertEqual(d.ex.positions, {})

        secs["GOOD"] = clean_sec(holders=1080)
        self.t[0] += 6 * 60
        d.scan()
        self.assertIn("GOOD", d.ex.positions)
        self.assertAlmostEqual(d.ex.positions["GOOD"].cost, 80.0)  # 8% of 1000
        self.assertIn("MEH", d.dead)
        self.assertNotIn("YOUNG", self.logger.scanned)  # under 30 min, not scanned yet

        d.scan()  # same coin again: one entry only
        self.assertEqual(len([t for t in self.read("trades.jsonl") if t["event"] == "entry"]), 1)

        for price in (1.05, 1.20, 1.35, 1.30, 1.25):
            pairs["GOOD"] = replace(pairs["GOOD"], price=price)
            d.manage()
        self.assertNotIn("GOOD", d.ex.positions)
        exit_ = self.read("trades.jsonl")[-1]
        self.assertEqual(exit_["reason"], "trailing stop")
        self.assertGreater(exit_["pnl_usd"], 0)

        text = d.recap()
        self.assertIn("rule 6: dev wallet holds more than 3% or dev has past rugs: 1", text)
        self.assertIn("analyst <70: 1", text)
        self.assertIn("W/L: 1/0", text)

    def test_empty_night_does_nothing(self):
        m = FakeMarket({"RUG": pair(mint="RUG")}, {"RUG": Security()})  # nothing verifiable
        d = self.desk(m)
        d.scan()
        self.assertEqual(self.read("kills.jsonl")[0]["rule"], 1)
        self.assertEqual(d.ex.cash, 1000.0)
        self.assertIn("Balance: $1,000.00 -> $1,000.00", d.recap())


class FlakyBroker(PaperBroker):
    def __init__(self):
        super().__init__(0)
        self.sell_ok = False

    def sell(self, pos, price):
        return super().sell(pos, price) if self.sell_ok else None


class SafetyTest(DeskTest):
    def test_failed_sell_keeps_position_and_retries(self):
        pairs = {"GOOD": pair(mint="GOOD")}
        secs = {"GOOD": clean_sec()}
        d = Desk(FakeMarket(pairs, secs), self.logger, FlakyBroker(),
                 1000.0, Runtime(), clock=lambda: self.t[0])
        d.scan(); secs["GOOD"] = clean_sec(holders=1080); self.t[0] += 360; d.scan()
        pairs["GOOD"] = replace(pairs["GOOD"], price=0.9)
        d.manage()
        self.assertIn("GOOD", d.ex.positions)
        self.assertEqual(self.read("trades.jsonl")[-1]["event"], "sell_failed")
        d.ex.broker.sell_ok = True
        d.manage()
        self.assertNotIn("GOOD", d.ex.positions)

    def test_state_round_trip(self):
        pairs = {"GOOD": pair(mint="GOOD")}
        secs = {"GOOD": clean_sec()}
        d = self.desk(FakeMarket(pairs, secs))
        d.scan(); secs["GOOD"] = clean_sec(holders=1080); self.t[0] += 360; d.scan()
        path = os.path.join(self.tmp, "state.json")
        d.save(path)
        d2 = self.desk(FakeMarket(pairs, {"GOOD": clean_sec()}))
        self.assertTrue(d2.load(path))
        self.assertEqual(d2.ex.positions["GOOD"].stop, d.ex.positions["GOOD"].stop)
        self.assertAlmostEqual(d2.ex.cash, 920.0)
        d2.scan()  # already traded: no second entry after a restart
        self.assertEqual(len(d2.ex.positions), 1)

    def test_live_needs_confirmation(self):
        from desk.desk import main
        with self.assertRaises(SystemExit) as cm:
            main(["--mode", "live", "--logs", self.tmp])
        self.assertIn("--confirm-live", str(cm.exception))


class RugCheckParseTest(unittest.TestCase):
    def test_parse_excludes_amm_and_handles_missing(self):
        r = {"mintAuthority": None, "freezeAuthority": None,
             "token": {"supply": 1_000_000}, "creatorBalance": 20_000,
             "markets": [{"lp": {"lpLockedPct": 100}}],
             "knownAccounts": {"POOL": {"type": "AMM"}},
             "topHolders": [{"owner": "POOL", "pct": 40}, {"owner": "a", "pct": 5}, {"owner": "b", "pct": 4}],
             "risks": [], "totalHolders": 900}
        s = RugCheck.parse(r)
        self.assertTrue(s.mint_revoked and s.freeze_revoked)
        self.assertEqual(s.top10_pct, 9)
        self.assertAlmostEqual(s.dev_pct, 2.0)
        self.assertFalse(s.dev_past_rugs)
        self.assertIsNone(RugCheck.parse(None).mint_revoked)


if __name__ == "__main__":
    unittest.main()
