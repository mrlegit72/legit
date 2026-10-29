"""LiveBroker against a fake RPC + Jupiter. Signing uses real solders keys."""
import base64
import unittest

from solders.hash import Hash
from solders.keypair import Keypair
from solders.message import MessageV0
from solders.signature import Signature
from solders.transaction import VersionedTransaction

from desk.agents import Position
from desk.live import USDC, LiveBroker, LiveError
from desk.tests.test_desk import pair

MINT = "M1"


def unsigned_tx(payer):
    msg = MessageV0.try_compile(payer, [], [], Hash.default())
    return base64.b64encode(bytes(VersionedTransaction.populate(msg, [Signature.default()]))).decode()


class FakeChain:
    """Holds balances; a sent tx applies whatever swap was last quoted."""

    def __init__(self, kp, usdc=1000.0, sol=0.5, out_per_usd=1.0, land=True, err=None):
        self.kp = kp
        self.bal = {USDC: (int(usdc * 1e6), 6), MINT: (0, 6)}
        self.sol, self.rate, self.land, self.err = sol, out_per_usd, land, err
        self.quote, self.sent = None, []

    def get(self, url, host_interval=None, body=None, headers=None):
        if "/quote?" in url:
            q = dict(x.split("=") for x in url.split("?")[1].split("&"))
            amt = int(q["amount"])
            if q["inputMint"] == USDC:
                out = int(amt / 1e6 * self.rate * 1e6)
            else:
                out = int(amt / 1e6 / self.rate * 1e6)
            self.quote = {"inputMint": q["inputMint"], "outputMint": q["outputMint"],
                          "inAmount": str(amt), "outAmount": str(out)}
            return self.quote
        if url.endswith("/swap"):
            return {"swapTransaction": unsigned_tx(self.kp.pubkey())}
        m, params = body["method"], body["params"]
        if m == "getTokenAccountsByOwner":
            raw, dec = self.bal.get(params[1]["mint"], (0, 6))
            acc = {"account": {"data": {"parsed": {"info": {"tokenAmount": {
                "amount": str(raw), "decimals": dec, "uiAmount": raw / 10 ** dec}}}}}}
            return {"result": {"value": [acc] if raw else []}}
        if m == "getBalance":
            return {"result": {"value": int(self.sol * 1e9)}}
        if m == "getTokenSupply":
            return {"result": {"value": {"decimals": 6}}}
        if m == "sendTransaction":
            tx = VersionedTransaction.from_bytes(base64.b64decode(params[0]))
            assert tx.verify_with_results() == [True], "tx not signed by wallet"
            self.sent.append(tx)
            if self.land:
                q = self.quote
                i, o = q["inputMint"], q["outputMint"]
                self.bal[i] = (self.bal[i][0] - int(q["inAmount"]), 6)
                self.bal[o] = (self.bal[o][0] + int(q["outAmount"]), 6)
            return {"result": "SIG"}
        if m == "getSignatureStatuses":
            return {"result": {"value": [{"err": self.err, "confirmationStatus": "confirmed"}]}}
        raise AssertionError(m)


class LiveBrokerTest(unittest.TestCase):
    def broker(self, **kw):
        kp = Keypair()
        chain = FakeChain(kp, **kw)
        return LiveBroker(keypair=kp, rpc="https://rpc.test", jup="https://jup.test",
                          http=chain, confirm_timeout_s=1, sleep=lambda s: None), chain

    def test_preflight(self):
        b, _ = self.broker()
        self.assertEqual(b.preflight()["usdc"], 1000.0)
        b, _ = self.broker(sol=0.001)
        with self.assertRaises(LiveError):
            b.preflight()

    def test_buy_measures_fill_from_wallet_and_signs(self):
        b, chain = self.broker(out_per_usd=0.99)  # 1% worse than the 1.00 market price
        fill, qty, spent = b.buy(pair(mint=MINT, price=1.0), 80.0)
        self.assertAlmostEqual(spent, 80.0)
        self.assertAlmostEqual(qty, 79.2)
        self.assertAlmostEqual(fill, 80 / 79.2)
        self.assertEqual(len(chain.sent), 1)

    def test_buy_skipped_when_fill_too_far_above_market(self):
        b, chain = self.broker(out_per_usd=0.9)  # ~11% above market
        self.assertIsNone(b.buy(pair(mint=MINT, price=1.0), 80.0))
        self.assertEqual(chain.sent, [])

    def test_failed_tx_is_not_a_position(self):
        b, _ = self.broker(err={"InstructionError": [0, "SlippageToleranceExceeded"]}, land=False)
        self.assertIsNone(b.buy(pair(mint=MINT, price=1.0), 80.0))

    def test_sell_dumps_full_balance(self):
        b, chain = self.broker()
        b.buy(pair(mint=MINT, price=1.0), 80.0)
        pos = Position(MINT, "S", "P", 1.0, 80, 80, 80, 0.94, 1.0, False, 0)
        fill, got = b.sell(pos, 1.0)
        self.assertAlmostEqual(got, 80.0)
        self.assertEqual(chain.bal[MINT][0], 0)

    def test_sell_failure_returns_none(self):
        b, chain = self.broker()
        b.buy(pair(mint=MINT, price=1.0), 80.0)
        chain.land = False
        pos = Position(MINT, "S", "P", 1.0, 80, 80, 80, 0.94, 1.0, False, 0)
        self.assertIsNone(b.sell(pos, 0.9))


if __name__ == "__main__":
    unittest.main()
