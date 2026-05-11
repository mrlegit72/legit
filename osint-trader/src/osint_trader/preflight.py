"""Boot-time validation.

Checks before the orchestrator's main loop starts:
1. Every configured market slug resolves on Polymarket Gamma.
2. Anthropic API key is non-empty (cheap sanity, not a real call).
3. In live mode: USDC balance on the proxy wallet ≥ configured bankroll.

Failures raise PreflightError so systemd/PM2 see a non-zero exit.
"""
from __future__ import annotations

from .config import MarketConfig, Settings, TradeMode
from .markets import PolymarketClient
from .observability import get_logger

logger = get_logger(__name__)

USDC_POLYGON = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
USDC_DECIMALS = 6


class PreflightError(RuntimeError):
    pass


async def run_preflight(
    settings: Settings,
    markets: list[MarketConfig],
    poly: PolymarketClient,
) -> None:
    if not settings.anthropic_api_key:
        raise PreflightError("ANTHROPIC_API_KEY is empty")

    snapshots = await poly.refresh_snapshots(markets)
    missing = [m.market_id for m in markets if m.market_id not in snapshots]
    if missing:
        raise PreflightError(
            f"slugs failed to resolve on Polymarket Gamma: {missing}. "
            f"Edit config/markets.yaml or remove them."
        )

    failures = poly.last_validation_failures()
    if failures:
        raise PreflightError(f"Gamma response validation failed for: {list(failures.keys())}")

    if settings.trade_mode == TradeMode.LIVE:
        await _check_usdc_balance(settings)

    logger.info(
        "preflight_ok",
        markets_resolved=len(snapshots),
        mode=settings.trade_mode.value,
    )


async def _check_usdc_balance(settings: Settings) -> None:
    if not settings.polymarket_funder:
        raise PreflightError("TRADE_MODE=live but POLYMARKET_FUNDER is empty")
    try:
        from web3 import Web3
    except ImportError as exc:
        raise PreflightError(
            "TRADE_MODE=live requires `pip install -e \".[trade]\"` (web3 missing)"
        ) from exc

    rpc = settings.polymarket_clob_host  # placeholder; production uses POLYGON_RPC env
    import os
    rpc = os.getenv("POLYGON_RPC", "https://polygon-rpc.com")

    w3 = Web3(Web3.HTTPProvider(rpc))
    if not w3.is_connected():
        raise PreflightError(f"could not connect to Polygon RPC at {rpc}")

    erc20_abi = [
        {"constant": True, "inputs": [{"name": "_owner", "type": "address"}],
         "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}],
         "type": "function"},
    ]
    contract = w3.eth.contract(address=Web3.to_checksum_address(USDC_POLYGON), abi=erc20_abi)
    raw = contract.functions.balanceOf(Web3.to_checksum_address(settings.polymarket_funder)).call()
    balance = raw / (10 ** USDC_DECIMALS)
    logger.info("preflight_usdc_balance", funder=settings.polymarket_funder, balance=balance)
    if balance < settings.bankroll_usdc:
        raise PreflightError(
            f"USDC balance ${balance:.2f} on {settings.polymarket_funder} "
            f"is below configured bankroll ${settings.bankroll_usdc:.2f}"
        )
