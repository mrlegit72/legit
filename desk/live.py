"""Real-money execution: Jupiter swaps signed locally, USDC as the balance.

Ground truth is always the wallet. Every buy and sell is measured by the
change in token / USDC balances, never by what the quote promised, so a
swap whose confirmation timed out but actually landed is still recorded.

Env:
  SOLANA_KEYPAIR   path to a solana-keygen JSON keypair (use a dedicated wallet)
  SOLANA_RPC_URL   or HELIUS_API_KEY
  JUP_API_URL      default https://lite-api.jup.ag/swap/v1
  JUP_API_KEY      optional, sent as x-api-key
"""
import base64
import json
import os
import time
from typing import Optional

from .data import Http

USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
MIN_SOL_FOR_FEES = 0.02


class LiveError(RuntimeError):
    pass


def load_keypair(path: str):
    from solders.keypair import Keypair
    with open(os.path.expanduser(path)) as f:
        return Keypair.from_bytes(bytes(json.load(f)))


class LiveBroker:
    def __init__(self, keypair=None, rpc: Optional[str] = None, jup: Optional[str] = None,
                 http: Optional[Http] = None, max_entry_impact_pct: float = 3.0,
                 slippage_bps: int = 300, confirm_timeout_s: float = 90, sleep=time.sleep):
        if keypair is None:
            path = os.environ.get("SOLANA_KEYPAIR")
            if not path:
                raise LiveError("set SOLANA_KEYPAIR to the trading wallet's keypair file")
            keypair = load_keypair(path)
        key = os.environ.get("HELIUS_API_KEY")
        self.rpc = rpc or os.environ.get("SOLANA_RPC_URL") or (
            f"https://mainnet.helius-rpc.com/?api-key={key}" if key else None)
        if not self.rpc:
            raise LiveError("set SOLANA_RPC_URL or HELIUS_API_KEY")
        self.kp = keypair
        self.owner = str(keypair.pubkey())
        self.jup = (jup or os.environ.get("JUP_API_URL") or "https://lite-api.jup.ag/swap/v1").rstrip("/")
        jkey = os.environ.get("JUP_API_KEY")
        self.jup_headers = {"x-api-key": jkey} if jkey else None
        self.http = http or Http()
        self.max_impact = max_entry_impact_pct
        self.slippage_bps = slippage_bps
        self.confirm_timeout_s = confirm_timeout_s
        self.sleep = sleep

    # ------------------------------------------------------------ wallet
    def _rpc(self, method, params):
        res = self.http.get(self.rpc, host_interval=0.1,
                            body={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
        if not isinstance(res, dict) or "error" in res:
            raise LiveError(f"rpc {method} failed: {(res or {}).get('error') if isinstance(res, dict) else res}")
        return res.get("result")

    def token_balance(self, mint: str):
        """(raw_amount, ui_amount, decimals) summed over the wallet's accounts for this mint."""
        res = self._rpc("getTokenAccountsByOwner",
                        [self.owner, {"mint": mint}, {"encoding": "jsonParsed", "commitment": "confirmed"}])
        raw, ui, dec = 0, 0.0, None
        for acc in (res or {}).get("value") or []:
            amt = acc["account"]["data"]["parsed"]["info"]["tokenAmount"]
            raw += int(amt["amount"])
            ui += float(amt.get("uiAmount") or 0)
            dec = amt.get("decimals", dec)
        return raw, ui, dec

    def sol_balance(self) -> float:
        res = self._rpc("getBalance", [self.owner, {"commitment": "confirmed"}])
        return (res or {}).get("value", 0) / 1e9

    def cash_usd(self) -> float:
        return self.token_balance(USDC)[1]

    def preflight(self) -> dict:
        """Refuse to start unless the wallet can actually trade."""
        usdc, sol = self.cash_usd(), self.sol_balance()
        if usdc <= 0:
            raise LiveError(f"wallet {self.owner} has no USDC")
        if sol < MIN_SOL_FOR_FEES:
            raise LiveError(f"wallet {self.owner} has {sol:.4f} SOL, need {MIN_SOL_FOR_FEES} for fees")
        return {"wallet": self.owner, "usdc": usdc, "sol": sol}

    def _decimals(self, mint: str) -> int:
        res = self._rpc("getTokenSupply", [mint])
        return int(res["value"]["decimals"])

    # ------------------------------------------------------------ swaps
    def _quote(self, in_mint, out_mint, amount_raw: int):
        q = self.http.get(f"{self.jup}/quote?inputMint={in_mint}&outputMint={out_mint}"
                          f"&amount={amount_raw}&slippageBps={self.slippage_bps}"
                          f"&restrictIntermediateTokens=true",
                          host_interval=1.1, headers=self.jup_headers)
        if not isinstance(q, dict) or not q.get("outAmount"):
            raise LiveError(f"no route {in_mint} -> {out_mint}: {q}")
        return q

    def _swap(self, quote) -> str:
        from solders.transaction import VersionedTransaction
        res = self.http.get(f"{self.jup}/swap", host_interval=1.1, headers=self.jup_headers, body={
            "quoteResponse": quote, "userPublicKey": self.owner, "wrapAndUnwrapSol": True,
            "dynamicComputeUnitLimit": True,
            "prioritizationFeeLamports": {"priorityLevelWithMaxLamports":
                                          {"maxLamports": 1_000_000, "priorityLevel": "high"}}})
        if not isinstance(res, dict) or not res.get("swapTransaction"):
            raise LiveError(f"swap build failed: {res}")
        unsigned = VersionedTransaction.from_bytes(base64.b64decode(res["swapTransaction"]))
        signed = VersionedTransaction(unsigned.message, [self.kp])
        sig = self._rpc("sendTransaction", [base64.b64encode(bytes(signed)).decode(),
                                            {"encoding": "base64", "maxRetries": 3,
                                             "preflightCommitment": "confirmed"}])
        self._confirm(sig)
        return sig

    def _confirm(self, sig: str):
        deadline = time.time() + self.confirm_timeout_s
        while time.time() < deadline:
            st = (self._rpc("getSignatureStatuses", [[sig]]) or {}).get("value", [None])[0]
            if st:
                if st.get("err"):
                    raise LiveError(f"tx {sig} failed on chain: {st['err']}")
                if st.get("confirmationStatus") in ("confirmed", "finalized"):
                    return
            self.sleep(1.5)
        # Past ~90s the blockhash has expired, so the tx can no longer land late.
        # The balance delta right after this decides whether it did land.

    def buy(self, p, usd: float):
        """Returns (fill_price, qty, usd_spent) or None. Never raises."""
        try:
            usdc_before = self.token_balance(USDC)[1]
            tok_before = self.token_balance(p.mint)[0]
            amount = int(min(usd, usdc_before) * 1e6)
            if amount <= 0:
                raise LiveError("not enough USDC")
            q = self._quote(USDC, p.mint, amount)
            dec = self._decimals(p.mint)
            implied = (amount / 1e6) / (int(q["outAmount"]) / 10 ** dec)
            impact = (implied / p.price - 1) * 100 if p.price else 999
            if impact > self.max_impact:
                raise LiveError(f"entry would fill {impact:.1f}% above market, skipped")
            sig = self._swap(q)
            tok_raw, tok_ui, _ = self.token_balance(p.mint)
            got = (tok_raw - tok_before) / 10 ** dec
            spent = usdc_before - self.token_balance(USDC)[1]
            if got <= 0 or spent <= 0:
                raise LiveError(f"tx {sig} landed no tokens")
            print(f"[live] BUY {p.symbol} {got:.6g} for ${spent:.2f} tx {sig}")
            return spent / got, got, spent
        except Exception as e:
            print(f"[live] buy {p.symbol} failed: {e}")
            return None

    def sell(self, pos, price: float):
        """Sells the wallet's full balance of the coin. Returns (fill_price, usd_received) or None."""
        try:
            raw, ui, _ = self.token_balance(pos.mint)
            if raw <= 0:
                raise LiveError("no tokens in wallet to sell")
            usdc_before = self.token_balance(USDC)[1]
            sig = self._swap(self._quote(pos.mint, USDC, raw))
            left = self.token_balance(pos.mint)[0]
            got = self.token_balance(USDC)[1] - usdc_before
            if left >= raw or got <= 0:
                raise LiveError(f"tx {sig} did not sell")
            sold = ui * (raw - left) / raw
            print(f"[live] SELL {pos.symbol} {sold:.6g} for ${got:.2f} tx {sig}")
            return got / sold, got
        except Exception as e:
            print(f"[live] sell {pos.symbol} failed, will retry next check: {e}")
            return None
