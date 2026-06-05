"""
Order Book Microstructure analysis — F1.2 (Lunai v1.3.0 "Perception").

Computes bid/ask imbalance and wall detection from the Binance public
depth endpoint (no API key required, up to 1200 req/min).

Imbalance  >0.60 with no ask wall  → BULLISH
Imbalance  <0.40 with no bid wall  → BEARISH
Dominant bid wall (support)        → BULLISH
Dominant ask wall (resistance)     → BEARISH
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)

_BINANCE_DEPTH_URL = "https://api.binance.com/api/v3/depth"
_DEPTH_LIMIT       = 100   # number of price levels to fetch
_WALL_MULT         = 3.0   # entry > WALL_MULT × average qty → "wall"

_cache: Dict[str, tuple] = {}
_CACHE_TTL = 30            # order book changes fast — 30 s


# ── Data class ────────────────────────────────────────────────────────────────

@dataclass
class OrderBookSnapshot:
    symbol: str
    bid_ask_imbalance: Optional[float] = None   # [0,1] — >0.5 = more bid depth
    bid_wall_pct: Optional[float] = None        # largest bid / total bids
    ask_wall_pct: Optional[float] = None        # largest ask / total asks
    spread_bps: Optional[float] = None          # bid-ask spread in basis points
    signal: str = "NEUTRAL"                     # BULLISH | NEUTRAL | BEARISH
    error: Optional[str] = None
    ts: float = field(default_factory=time.time)


# ── Pure scoring ──────────────────────────────────────────────────────────────

def analyze_order_book(
    bids: List[List[float]],   # [[price, qty], ...] — best bid first (high→low)
    asks: List[List[float]],   # [[price, qty], ...] — best ask first (low→high)
) -> dict:
    """Pure function — compute microstructure metrics from raw order book levels.

    Returns a dict with keys: bid_ask_imbalance, bid_wall_pct, ask_wall_pct,
    spread_bps, signal.  Returns {"error": ...} if book is invalid.
    """
    if not bids or not asks:
        return {"error": "empty book"}

    bid_qtys  = [float(b[1]) for b in bids]
    ask_qtys  = [float(a[1]) for a in asks]
    total_bid = sum(bid_qtys)
    total_ask = sum(ask_qtys)

    if total_bid + total_ask == 0:
        return {"error": "zero depth"}

    # Bid/ask depth imbalance [0, 1]
    imbalance = total_bid / (total_bid + total_ask)

    # Wall detection — single level > WALL_MULT × average
    avg_bid = total_bid / len(bid_qtys)
    avg_ask = total_ask / len(ask_qtys)
    max_bid = max(bid_qtys)
    max_ask = max(ask_qtys)

    bid_wall_pct = max_bid / total_bid if total_bid else 0.0
    ask_wall_pct = max_ask / total_ask if total_ask else 0.0
    has_bid_wall = avg_bid > 0 and max_bid >= _WALL_MULT * avg_bid
    has_ask_wall = avg_ask > 0 and max_ask >= _WALL_MULT * avg_ask

    # Spread in basis points
    best_bid = float(bids[0][0])
    best_ask = float(asks[0][0])
    mid      = (best_bid + best_ask) / 2.0
    spread_bps = (best_ask - best_bid) / mid * 10_000 if mid > 0 else None

    # Signal
    if has_bid_wall and not has_ask_wall:
        signal = "BULLISH"   # strong support
    elif has_ask_wall and not has_bid_wall:
        signal = "BEARISH"   # strong resistance
    elif imbalance > 0.60:
        signal = "BULLISH"   # buyers dominate depth
    elif imbalance < 0.40:
        signal = "BEARISH"   # sellers dominate depth
    else:
        signal = "NEUTRAL"

    return {
        "bid_ask_imbalance": round(imbalance, 4),
        "bid_wall_pct":      round(bid_wall_pct, 4),
        "ask_wall_pct":      round(ask_wall_pct, 4),
        "spread_bps":        round(spread_bps, 2) if spread_bps is not None else None,
        "signal":            signal,
    }


# ── Async fetcher ─────────────────────────────────────────────────────────────

async def get_order_book(symbol: str = "BTCUSDT") -> OrderBookSnapshot:
    """Fetch Binance order book and return a microstructure snapshot.

    symbol should be in Binance format (no slash), e.g. BTCUSDT.
    Results cached for _CACHE_TTL seconds.
    """
    cache_key = f"ob:{symbol}"
    entry = _cache.get(cache_key)
    if entry and time.time() < entry[1]:
        return entry[0]

    snap = OrderBookSnapshot(symbol=symbol)
    try:
        params = {"symbol": symbol, "limit": _DEPTH_LIMIT}
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=8)
        ) as session:
            async with session.get(_BINANCE_DEPTH_URL, params=params) as resp:
                if resp.status != 200:
                    snap.error = f"HTTP {resp.status}"
                    return snap
                data = await resp.json(content_type=None)

        bids = [[float(p), float(q)] for p, q in data.get("bids", [])]
        asks = [[float(p), float(q)] for p, q in data.get("asks", [])]
        metrics = analyze_order_book(bids, asks)

        if "error" in metrics:
            snap.error = metrics["error"]
        else:
            snap.bid_ask_imbalance = metrics["bid_ask_imbalance"]
            snap.bid_wall_pct      = metrics["bid_wall_pct"]
            snap.ask_wall_pct      = metrics["ask_wall_pct"]
            snap.spread_bps        = metrics["spread_bps"]
            snap.signal            = metrics["signal"]

    except Exception as e:
        logger.warning("Order book fetch failed for %s: %s", symbol, e)
        snap.error = str(e)

    _cache[cache_key] = (snap, time.time() + _CACHE_TTL)
    return snap
