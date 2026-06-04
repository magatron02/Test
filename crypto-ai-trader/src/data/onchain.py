"""
On-chain metrics — F1.1 (Lunai v1.3.0 "Perception").

Data sources (all free, no API key required):
  • blockchain.com /stats  — BTC network stats (active addresses, tx count, etc.)
  • Returns None gracefully for non-BTC symbols.

Metrics surfaced:
  • active_addresses_change_pct — day-over-day active address growth
  • tx_count_change_pct         — day-over-day transaction count growth
  • hash_rate_change_pct        — miner activity proxy

Growing active addresses + tx count → network adoption → mildly bullish.
Falling addresses → network contraction → mildly bearish.
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

import aiohttp

logger = logging.getLogger(__name__)

_BLOCKCHAIN_STATS_URL = "https://api.blockchain.info/stats"
_CACHE_TTL = 600   # 10 min — daily-granularity data, no need to poll frequently
_cache: Dict[str, tuple] = {}

# History buffer: keep two consecutive snapshots to compute day-over-day change
_prev_stats: Dict[str, dict] = {}


# ── Data class ────────────────────────────────────────────────────────────────

@dataclass
class OnchainSnapshot:
    symbol: str
    active_addr_change_pct: Optional[float] = None  # positive = growing network
    tx_count_change_pct: Optional[float] = None
    hash_rate_change_pct: Optional[float] = None
    label: str = "NEUTRAL"
    score: float = 0.0                               # [-1, 1]
    error: Optional[str] = None
    ts: float = field(default_factory=time.time)


# ── Pure scoring ──────────────────────────────────────────────────────────────

def onchain_bias(
    active_addr_change_pct: Optional[float],
    tx_count_change_pct: Optional[float],
    hash_rate_change_pct: Optional[float] = None,
) -> Tuple[str, float]:
    """Pure function — combine on-chain growth metrics into a directional bias.

    Returns (label, score) where score ∈ [-1, 1].
    """
    score = 0.0

    # Active addresses: leading indicator of genuine network adoption
    if active_addr_change_pct is not None:
        if active_addr_change_pct >= 0.05:    # ≥5% growth
            score += 0.35
        elif active_addr_change_pct >= 0.02:  # 2–5%
            score += 0.15
        elif active_addr_change_pct <= -0.05:
            score -= 0.35
        elif active_addr_change_pct <= -0.02:
            score -= 0.15

    # Transaction count: measures economic throughput
    if tx_count_change_pct is not None:
        if tx_count_change_pct >= 0.10:
            score += 0.25
        elif tx_count_change_pct >= 0.03:
            score += 0.10
        elif tx_count_change_pct <= -0.10:
            score -= 0.25
        elif tx_count_change_pct <= -0.03:
            score -= 0.10

    # Hash rate: growing hash = miner confidence (long-term bullish signal)
    if hash_rate_change_pct is not None:
        if hash_rate_change_pct >= 0.10:
            score += 0.15
        elif hash_rate_change_pct <= -0.10:
            score -= 0.15

    score = max(-1.0, min(1.0, score))

    if score >= 0.30:
        label = "BULLISH_ONCHAIN"
    elif score >= 0.10:
        label = "MILD_BULLISH_ONCHAIN"
    elif score <= -0.30:
        label = "BEARISH_ONCHAIN"
    elif score <= -0.10:
        label = "MILD_BEARISH_ONCHAIN"
    else:
        label = "NEUTRAL"

    return label, round(score, 3)


# ── Async fetcher ─────────────────────────────────────────────────────────────

async def get_btc_onchain() -> OnchainSnapshot:
    """Fetch BTC on-chain metrics from blockchain.com/stats.

    Computes percentage changes by comparing the current snapshot against the
    previously cached one (_prev_stats). On the first call no change is
    available — returns NEUTRAL with raw metrics only.
    """
    cache_key = "onchain:BTC"
    entry = _cache.get(cache_key)
    if entry and time.time() < entry[1]:
        return entry[0]

    snap = OnchainSnapshot(symbol="BTC")
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10)
        ) as session:
            async with session.get(_BLOCKCHAIN_STATS_URL) as resp:
                if resp.status != 200:
                    snap.error = f"HTTP {resp.status}"
                    _cache[cache_key] = (snap, time.time() + _CACHE_TTL)
                    return snap
                data = await resp.json(content_type=None)

        current = {
            "n_unique_addresses": float(data.get("n_unique_addresses", 0) or 0),
            "n_transactions":     float(data.get("n_transactions",     0) or 0),
            "hash_rate":          float(data.get("hash_rate",          0) or 0),
        }

        prev = _prev_stats.get("BTC")

        def _pct_change(key: str) -> Optional[float]:
            if prev is None:
                return None
            old = prev.get(key, 0.0)
            new = current.get(key, 0.0)
            if old == 0:
                return None
            return (new - old) / old

        snap.active_addr_change_pct  = _pct_change("n_unique_addresses")
        snap.tx_count_change_pct     = _pct_change("n_transactions")
        snap.hash_rate_change_pct    = _pct_change("hash_rate")
        snap.label, snap.score       = onchain_bias(
            snap.active_addr_change_pct,
            snap.tx_count_change_pct,
            snap.hash_rate_change_pct,
        )

        _prev_stats["BTC"] = current

    except Exception as e:
        logger.warning("On-chain fetch failed: %s", e)
        snap.error = str(e)

    _cache[cache_key] = (snap, time.time() + _CACHE_TTL)
    return snap


async def get_onchain(symbol: str = "BTC/USDT") -> OnchainSnapshot:
    """Public entry point. Currently supports BTC; returns NEUTRAL for others."""
    base = symbol.split("/")[0].upper()
    if base == "BTC":
        return await get_btc_onchain()
    # On-chain data not yet available for non-BTC symbols
    return OnchainSnapshot(symbol=base, error=f"on-chain not available for {base}")
