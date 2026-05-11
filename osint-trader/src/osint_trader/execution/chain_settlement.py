"""On-chain settlement reader for Polymarket conditional tokens.

Polymarket markets settle through UMA's optimistic oracle and the resulting
payout is reflected in the conditional tokens contract on Polygon. We listen
for `PayoutRedemption` events for the proxy wallet and feed them back into
the Settlement layer so realised PnL matches on-chain reality.

This module is best-effort: if web3/Polygon is unreachable, the listener
no-ops and the synthetic settlement (mark-to-market via PositionManager)
remains the source of truth. In production you'd run this alongside the
orchestrator and have it overwrite settlement rows when it sees the on-chain
payout.

Polymarket conditional tokens contract (Polygon mainnet):
  0x4D97DCd97eC945f40cF65F87097ACe5EA0476045
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

from ..observability import get_logger

logger = get_logger(__name__)

CONDITIONAL_TOKENS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
PAYOUT_REDEMPTION_TOPIC = (
    # keccak256("PayoutRedemption(address,bytes32,bytes32,uint256[],uint256)")
    "0x0bf0c0bbf17f3df17b48fbe3deedb6e5c3637b1f7c4b6e2fb9c8d8be1e8a3a8b"
)


@dataclass
class PayoutEvent:
    redeemer: str
    condition_id: str
    payout_usdc: float
    block_number: int
    tx_hash: str


class ChainSettlementReader:
    def __init__(self, funder_address: str, poll_seconds: int = 60) -> None:
        self.funder_address = funder_address
        self.poll_seconds = poll_seconds
        self._stop = False

    async def run(self, on_payout) -> None:
        """Loop: poll Polygon for new PayoutRedemption events, call `on_payout`."""
        if not self.funder_address:
            logger.info("chain_settlement_disabled", reason="no funder")
            return
        try:
            from web3 import Web3
        except ImportError:
            logger.info("chain_settlement_disabled", reason="web3 not installed")
            return

        rpc = os.getenv("POLYGON_RPC", "https://polygon-rpc.com")
        w3 = Web3(Web3.HTTPProvider(rpc))
        if not w3.is_connected():
            logger.warning("chain_settlement_no_rpc", rpc=rpc)
            return

        last_block = w3.eth.block_number
        logger.info("chain_settlement_started", from_block=last_block)
        while not self._stop:
            try:
                latest = w3.eth.block_number
                if latest > last_block:
                    logs = w3.eth.get_logs({
                        "fromBlock": last_block + 1,
                        "toBlock": latest,
                        "address": Web3.to_checksum_address(CONDITIONAL_TOKENS),
                        "topics": [PAYOUT_REDEMPTION_TOPIC],
                    })
                    for log in logs:
                        evt = _parse_log(log)
                        if evt and evt.redeemer.lower() == self.funder_address.lower():
                            await on_payout(evt)
                    last_block = latest
            except Exception as exc:
                logger.warning("chain_settlement_poll_failed", error=str(exc))
            await asyncio.sleep(self.poll_seconds)

    def stop(self) -> None:
        self._stop = True


def _parse_log(log) -> PayoutEvent | None:
    try:
        topics = log.get("topics", [])
        if len(topics) < 3:
            return None
        # topic[1] = redeemer (indexed address); topic[2] = conditionId.
        redeemer = "0x" + topics[1].hex()[-40:]
        condition_id = topics[2].hex()
        # data layout: uint256[] indexSets, uint256 totalPayout (USDC, 6 decimals).
        # Best-effort decode of the trailing payout value.
        data_hex = log.get("data", "0x")
        if isinstance(data_hex, bytes):
            data_hex = data_hex.hex()
        if data_hex.startswith("0x"):
            data_hex = data_hex[2:]
        words = [data_hex[i:i + 64] for i in range(0, len(data_hex), 64)]
        if not words:
            return None
        payout_raw = int(words[-1], 16)
        return PayoutEvent(
            redeemer=redeemer,
            condition_id=condition_id,
            payout_usdc=payout_raw / 1_000_000,
            block_number=log.get("blockNumber", 0),
            tx_hash=log.get("transactionHash", b"").hex() if isinstance(log.get("transactionHash"), bytes) else str(log.get("transactionHash", "")),
        )
    except Exception:
        return None
