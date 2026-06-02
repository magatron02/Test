"""
External market sentiment signals — Fear & Greed Index + Funding Rates.
Both use free public APIs with no key required.
Results are cached 1 hour to avoid hammering APIs every cycle.

Fear & Greed (0–100):
  0–24   Extreme Fear  → historically good BUY zone
  25–44  Fear
  45–55  Neutral
  56–75  Greed
  76–100 Extreme Greed → historically good SELL / caution zone

Funding Rate (%):
  Positive → longs paying shorts → market overleveraged long → bearish lean
  Negative → shorts paying longs → market overleveraged short → bullish lean
  |rate| > 0.05% → extreme positioning, strong signal
"""
import logging
import time
from typing import Dict, Optional

import aiohttp

logger = logging.getLogger(__name__)

_FEAR_GREED_URL = "https://api.alternative.me/fng/?limit=1"
_BINANCE_PREMIUM = "https://fapi.binance.com/fapi/v1/premiumIndex"

_CACHE_TTL = 3600  # seconds (1 hour)
_cache: Dict[str, dict] = {}

_FUTURES_MAP = {
    "BTC/USDT": "BTCUSDT",
    "ETH/USDT": "ETHUSDT",
    "SOL/USDT": "SOLUSDT",
    "BNB/USDT": "BNBUSDT",
    "XRP/USDT": "XRPUSDT",
}


def _cache_get(key: str):
    entry = _cache.get(key)
    if entry and (time.time() - entry["ts"]) < _CACHE_TTL:
        return entry["value"]
    return None


def _cache_set(key: str, value):
    _cache[key] = {"ts": time.time(), "value": value}


async def get_fear_greed() -> Optional[dict]:
    """
    Returns {value: 0-100, label: str} or None on failure.
    Cached for 1 hour.
    """
    cached = _cache_get("fear_greed")
    if cached is not None:
        return cached
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
            async with session.get(_FEAR_GREED_URL) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
                fng = data["data"][0]
                result = {
                    "value": int(fng["value"]),
                    "label": fng["value_classification"],
                }
                _cache_set("fear_greed", result)
                logger.info(f"Fear & Greed: {result['value']} ({result['label']})")
                return result
    except Exception as e:
        logger.debug(f"Fear & Greed fetch failed: {e}")
        return None


async def get_funding_rates(symbols: list) -> Dict[str, float]:
    """
    Returns {symbol → funding_rate_%} for each symbol.
    E.g. {"BTC/USDT": 0.0120, "ETH/USDT": -0.0050}
    Cached for 1 hour.
    """
    cached = _cache_get("funding_rates")
    if cached is not None:
        return cached
    result: Dict[str, float] = {}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            for sym in symbols:
                futures_sym = _FUTURES_MAP.get(sym)
                if not futures_sym:
                    continue
                try:
                    async with session.get(_BINANCE_PREMIUM, params={"symbol": futures_sym}) as resp:
                        if resp.status == 200:
                            data = await resp.json(content_type=None)
                            rate = float(data.get("lastFundingRate", 0)) * 100
                            result[sym] = round(rate, 4)
                except Exception:
                    pass
        _cache_set("funding_rates", result)
        logger.info(f"Funding rates: {result}")
    except Exception as e:
        logger.debug(f"Funding rates fetch failed: {e}")
    return result


def fear_greed_bias(value: int) -> float:
    """
    Returns a multiplier applied to buy/sell scores:
    +value → boost BUY (fear = opportunity)
    -value → boost SELL (greed = caution)

    Range: -0.12 to +0.12 additive bonus on confidence score.
    """
    if value <= 20:    return +0.12   # Extreme Fear → strong BUY bias
    if value <= 35:    return +0.07   # Fear → moderate BUY bias
    if value <= 45:    return +0.03   # Slight Fear → small BUY bias
    if value >= 80:    return -0.12   # Extreme Greed → strong SELL bias
    if value >= 65:    return -0.07   # Greed → moderate SELL bias
    if value >= 55:    return -0.03   # Slight Greed → small SELL bias
    return 0.0                        # Neutral → no adjustment


def funding_bias(rate_pct: float) -> float:
    """
    Returns an additive bias on confidence:
    Positive rate (longs overleveraged) → SELL bias (negative return)
    Negative rate (shorts overleveraged) → BUY bias (positive return)

    Binance lastFundingRate is already multiplied by 100 before being passed here,
    so rate_pct is in %, e.g. 0.01 = 0.01% per 8h (normal baseline).
    Thresholds calibrated so normal rates (~0.01%) produce no bias;
    only extreme rates (>= 0.05%) trigger signals.
    """
    if rate_pct >= 0.10:    return -0.10  # Very high positive → strong SELL bias
    if rate_pct >= 0.05:    return -0.05  # High positive → moderate SELL bias
    if rate_pct >= 0.02:    return -0.02  # Moderate positive → small SELL bias
    if rate_pct <= -0.10:   return +0.10  # Very negative → strong BUY bias
    if rate_pct <= -0.05:   return +0.05  # Negative → moderate BUY bias
    if rate_pct <= -0.02:   return +0.02  # Slightly negative → small BUY bias
    return 0.0


def cache_status() -> dict:
    """Return cache ages for monitoring."""
    now = time.time()
    result = {}
    for key, entry in _cache.items():
        age = int(now - entry["ts"])
        result[key] = {"age_sec": age, "expires_in": max(0, _CACHE_TTL - age)}
    return result
