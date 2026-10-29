"""On-chain / market data sources. Stdlib only.

Every field the filter depends on may come back missing. Missing data is
reported as None, and the filter treats None as a kill (fail closed).
"""
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

UA = {"User-Agent": "memedesk/1.0", "Accept": "application/json"}


class Http:
    def __init__(self, min_interval_s: float = 0.25):
        self.min_interval_s = min_interval_s
        self._last = {}

    def get(self, url: str, host_interval: Optional[float] = None, body=None):
        host = url.split("/")[2]
        gap = host_interval if host_interval is not None else self.min_interval_s
        wait = self._last.get(host, 0) + gap - time.time()
        if wait > 0:
            time.sleep(wait)
        data = json.dumps(body).encode() if body is not None else None
        headers = dict(UA, **({"Content-Type": "application/json"} if data else {}))
        req = urllib.request.Request(url, data=data, headers=headers)
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=20) as r:
                    self._last[host] = time.time()
                    return json.loads(r.read().decode())
            except urllib.error.HTTPError as e:
                self._last[host] = time.time()
                if e.code == 429:
                    time.sleep(5 * (attempt + 1))
                    continue
                if e.code == 404:
                    return None
                raise
            except (urllib.error.URLError, TimeoutError):
                time.sleep(2 * (attempt + 1))
        return None


@dataclass
class Pair:
    mint: str
    pair_address: str
    symbol: str
    dex: str
    created_ms: int
    mcap: float
    liquidity: float
    vol_1h: float
    change_1h: float
    change_5m: float
    buys_1h: int
    sells_1h: int
    price: float

    def age_min(self, now: float) -> float:
        return (now * 1000 - self.created_ms) / 60_000


@dataclass
class Security:
    mint_revoked: Optional[bool] = None
    freeze_revoked: Optional[bool] = None
    lp_safe_pct: Optional[float] = None    # % of LP burned or locked (best market)
    top10_pct: Optional[float] = None      # excludes AMM / locker accounts
    dev_pct: Optional[float] = None
    dev_past_rugs: Optional[bool] = None
    bundled_pct: Optional[float] = None
    holders: Optional[int] = None
    notes: list = field(default_factory=list)


def _f(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


class DexScreener:
    BASE = "https://api.dexscreener.com"

    def __init__(self, http: Http):
        self.http = http

    def discover_mints(self) -> set:
        """Fresh Solana mints from the profile / boost feeds."""
        mints = set()
        for path in ("/token-profiles/latest/v1", "/token-boosts/latest/v1",
                     "/community-takeovers/latest/v1"):
            rows = self.http.get(self.BASE + path, host_interval=1.1) or []
            for row in rows if isinstance(rows, list) else []:
                if row.get("chainId") == "solana" and row.get("tokenAddress"):
                    mints.add(row["tokenAddress"])
        return mints

    def pairs_for(self, mints) -> dict:
        """mint -> best (deepest liquidity) Solana pair on an allowed dex."""
        mints = list(mints)
        best = {}
        for i in range(0, len(mints), 30):
            chunk = ",".join(mints[i:i + 30])
            rows = self.http.get(f"{self.BASE}/tokens/v1/solana/{chunk}", host_interval=0.25) or []
            for p in rows if isinstance(rows, list) else []:
                pair = self._parse(p)
                if pair and (pair.mint not in best or pair.liquidity > best[pair.mint].liquidity):
                    best[pair.mint] = pair
        return best

    @staticmethod
    def _parse(p) -> Optional[Pair]:
        if p.get("chainId") != "solana" or not p.get("pairCreatedAt"):
            return None
        base = p.get("baseToken") or {}
        tx = (p.get("txns") or {}).get("h1") or {}
        pc = p.get("priceChange") or {}
        return Pair(
            mint=base.get("address", ""),
            pair_address=p.get("pairAddress", ""),
            symbol=base.get("symbol", "?"),
            dex=(p.get("dexId") or "").lower(),
            created_ms=int(p["pairCreatedAt"]),
            mcap=_f(p.get("marketCap") or p.get("fdv")),
            liquidity=_f((p.get("liquidity") or {}).get("usd")),
            vol_1h=_f((p.get("volume") or {}).get("h1")),
            change_1h=_f(pc.get("h1")),
            change_5m=_f(pc.get("m5")),
            buys_1h=int(_f(tx.get("buys"))),
            sells_1h=int(_f(tx.get("sells"))),
            price=_f(p.get("priceUsd")),
        )


class GeckoTerminal:
    """Second discovery feed: newest Solana pools."""
    BASE = "https://api.geckoterminal.com/api/v2"

    def __init__(self, http: Http, pages: int = 5):
        self.http, self.pages = http, pages

    def discover_mints(self) -> set:
        mints = set()
        for page in range(1, self.pages + 1):
            res = self.http.get(f"{self.BASE}/networks/solana/new_pools?page={page}", host_interval=2.1)
            for pool in (res or {}).get("data", []):
                rel = ((pool.get("relationships") or {}).get("base_token") or {}).get("data") or {}
                tid = rel.get("id", "")
                if tid.startswith("solana_"):
                    mints.add(tid[len("solana_"):])
        return mints


class RugCheck:
    BASE = "https://api.rugcheck.xyz/v1"
    SAFE_ACCOUNT_TYPES = {"AMM", "LOCKER"}

    def __init__(self, http: Http):
        self.http = http

    def security(self, mint: str) -> Security:
        r = self.http.get(f"{self.BASE}/tokens/{mint}/report", host_interval=1.5)
        return self.parse(r)

    @classmethod
    def parse(cls, r) -> Security:
        s = Security()
        if not r:
            s.notes.append("rugcheck report unavailable")
            return s
        token = r.get("token") or {}
        if "mintAuthority" in r or "mintAuthority" in token:
            s.mint_revoked = (r.get("mintAuthority") or token.get("mintAuthority")) is None
        if "freezeAuthority" in r or "freezeAuthority" in token:
            s.freeze_revoked = (r.get("freezeAuthority") or token.get("freezeAuthority")) is None

        lp = [_f((m.get("lp") or {}).get("lpLockedPct"), None) for m in r.get("markets") or []]
        lp = [x for x in lp if x is not None]
        if lp:
            s.lp_safe_pct = max(lp)

        known = r.get("knownAccounts") or {}
        holders = r.get("topHolders")
        if isinstance(holders, list):
            real = [h for h in holders
                    if (known.get(h.get("owner")) or known.get(h.get("address")) or {}).get("type")
                    not in cls.SAFE_ACCOUNT_TYPES]
            s.top10_pct = sum(_f(h.get("pct")) for h in real[:10])

        supply = _f(token.get("supply"), None)
        if r.get("creatorBalance") is not None and supply:
            s.dev_pct = _f(r["creatorBalance"]) / supply * 100
        risk_names = " ".join((x.get("name") or "").lower() for x in r.get("risks") or [])
        s.dev_past_rugs = bool(r.get("rugged")) or ("creator" in risk_names and "rug" in risk_names)

        if r.get("totalHolders") is not None:
            s.holders = int(_f(r["totalHolders"]))
        return s


class TrenchBot:
    """Bundle detection. If this is unreachable, rule 7 fails closed."""
    BASE = "https://trench.bot/api/bundle/bundle_advanced"

    def __init__(self, http: Http):
        self.http = http

    def bundled_pct(self, mint: str) -> Optional[float]:
        r = self.http.get(f"{self.BASE}/{mint}", host_interval=1.5)
        if not isinstance(r, dict):
            return None
        for key in ("total_percentage_bundled", "total_bundle_percentage"):
            if r.get(key) is not None:
                return _f(r[key])
        return None


class SmartWallets:
    """Checks whether wallets from smart_wallets.txt hold the token.

    Needs HELIUS_API_KEY (or SOLANA_RPC_URL). Without either, every coin gets
    0 on this component, which only makes the analyst stricter.
    """

    def __init__(self, http: Http, path: str):
        self.http = http
        key = os.environ.get("HELIUS_API_KEY")
        self.rpc = os.environ.get("SOLANA_RPC_URL") or (
            f"https://mainnet.helius-rpc.com/?api-key={key}" if key else None)
        self.wallets = []
        if os.path.exists(path):
            with open(path) as f:
                self.wallets = [w.strip() for w in f if w.strip() and not w.startswith("#")]

    @property
    def enabled(self) -> bool:
        return bool(self.rpc and self.wallets)

    def holders_of(self, mint: str) -> int:
        if not self.enabled:
            return 0
        n = 0
        for w in self.wallets:
            body = {"jsonrpc": "2.0", "id": 1, "method": "getTokenAccountsByOwner",
                    "params": [w, {"mint": mint}, {"encoding": "jsonParsed"}]}
            res = self.http.get(self.rpc, host_interval=0.1, body=body) or {}
            for acc in ((res.get("result") or {}).get("value") or []):
                amt = (((acc.get("account") or {}).get("data") or {}).get("parsed") or {}) \
                    .get("info", {}).get("tokenAmount", {}).get("uiAmount") or 0
                if amt > 0:
                    n += 1
                    break
        return n
