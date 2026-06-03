"""
On-chain & sentiment data layer.

Sources (all free, no API key required):
  • Fear & Greed Index  — alternative.me/fng
  • Funding rate        — ccxt exchange.fetchFundingRate()
  • Open Interest       — Binance futures API (public, no key needed)

Results are cached in-process to avoid hammering public endpoints.
"""
import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

_FNG_URL = "https://api.alternative.me/fng/?limit=1&format=json"
_BINANCE_OI_URL = "https://fapi.binance.com/fapi/v1/openInterest"

# In-memory cache: (value, expires_at)
_cache: dict = {}
_CACHE_TTL = {
    "fng": 3600,       # 1 h — index updates once per day
    "funding": 60,     # 1 min — funding updates every 8 h but we poll more often
    "oi": 60,          # 1 min
}


@dataclass
class SentimentSnapshot:
    fear_greed_value: Optional[int] = None        # 0–100
    fear_greed_label: Optional[str] = None        # "Extreme Fear" … "Extreme Greed"
    funding_rate: Optional[float] = None          # raw rate, e.g. 0.0001 = 0.01%
    funding_symbol: Optional[str] = None
    open_interest_usdt: Optional[float] = None   # total OI in USDT
    open_interest_symbol: Optional[str] = None
    error: Optional[str] = None
    ts: float = field(default_factory=time.time)

    @property
    def market_sentiment(self) -> str:
        """Human label: Extreme Fear | Fear | Neutral | Greed | Extreme Greed."""
        if self.fear_greed_value is None:
            return "Unknown"
        v = self.fear_greed_value
        if v <= 25:
            return "Extreme Fear"
        if v <= 45:
            return "Fear"
        if v <= 55:
            return "Neutral"
        if v <= 75:
            return "Greed"
        return "Extreme Greed"

    @property
    def trading_bias(self) -> str:
        """Quick directional hint for the trading engine."""
        s = self.market_sentiment
        if s == "Extreme Fear":
            return "CONTRARIAN_BUY"   # historically best time to accumulate
        if s in ("Fear",):
            return "CAUTIOUS_BUY"
        if s == "Neutral":
            return "NEUTRAL"
        if s == "Greed":
            return "CAUTIOUS_SELL"
        if s == "Extreme Greed":
            return "CONTRARIAN_SELL"  # markets historically overstretched
        return "NEUTRAL"


def _cached(key: str, ttl: int):
    """Return cached value or None if stale/missing."""
    entry = _cache.get(key)
    if entry and time.time() < entry[1]:
        return entry[0]
    return None


def _store(key: str, value, ttl: int):
    _cache[key] = (value, time.time() + ttl)


async def get_fear_greed() -> dict:
    """Return Fear & Greed index. Cached 1 h."""
    cached = _cached("fng", _CACHE_TTL["fng"])
    if cached is not None:
        return cached
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(_FNG_URL) as resp:
                data = await resp.json(content_type=None)
        entry = data["data"][0]
        result = {
            "value": int(entry["value"]),
            "label": entry["value_classification"],
            "timestamp": entry.get("timestamp"),
        }
        _store("fng", result, _CACHE_TTL["fng"])
        return result
    except Exception as e:
        logger.warning("Fear & Greed fetch failed: %s", e)
        return {"value": None, "label": None, "error": str(e)}


async def get_funding_rate(exchange, symbol: str = "BTC/USDT") -> dict:
    """Return funding rate for symbol via ccxt. Cached 60 s."""
    cache_key = f"funding:{symbol}"
    cached = _cached(cache_key, _CACHE_TTL["funding"])
    if cached is not None:
        return cached
    try:
        raw = await exchange.fetchFundingRate(symbol)
        rate = raw.get("fundingRate") if isinstance(raw, dict) else None
        result = {
            "symbol": symbol,
            "funding_rate": float(rate) if rate is not None else None,
            "funding_rate_pct": round(float(rate) * 100, 4) if rate is not None else None,
            "next_funding_time": raw.get("nextFundingTime") if isinstance(raw, dict) else None,
        }
        _store(cache_key, result, _CACHE_TTL["funding"])
        return result
    except Exception as e:
        logger.warning("Funding rate fetch failed for %s: %s", symbol, e)
        return {"symbol": symbol, "funding_rate": None, "error": str(e)}


async def get_open_interest(symbol: str = "BTCUSDT", mark_price: Optional[float] = None) -> dict:
    """Return open interest from Binance futures (public endpoint). Cached 60 s.

    The /fapi/v1/openInterest endpoint returns OI in *base-asset contracts*
    (e.g. BTC), not USDT. Pass ``mark_price`` to convert to a USDT notional;
    otherwise only the contract count is returned.
    """
    cache_key = f"oi:{symbol}"
    cached = _cached(cache_key, _CACHE_TTL["oi"])
    if cached is not None:
        # Recompute USDT if a price is now available and wasn't cached, then persist it
        if mark_price is not None and cached.get("open_interest_contracts") and cached.get("open_interest_usdt") is None:
            cached = {**cached, "open_interest_usdt": float(cached["open_interest_contracts"]) * mark_price}
            _store(cache_key, cached, _CACHE_TTL["oi"])
        return cached
    try:
        url = f"{_BINANCE_OI_URL}?symbol={symbol}"
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(url) as resp:
                data = await resp.json(content_type=None)
        # Binance error responses carry a non-zero code / msg and omit openInterest
        if "openInterest" not in data:
            msg = data.get("msg", "unexpected response")
            logger.warning("Open interest unavailable for %s: %s", symbol, msg)
            return {"symbol": symbol, "open_interest_contracts": None,
                    "open_interest_usdt": None, "error": msg[:160]}
        contracts = float(data["openInterest"])
        usdt = contracts * mark_price if mark_price is not None else None
        result = {
            "symbol": symbol,
            "open_interest_contracts": contracts,
            "open_interest_usdt": usdt,
            "time": data.get("time"),
        }
        _store(cache_key, result, _CACHE_TTL["oi"])
        return result
    except Exception as e:
        logger.warning("Open interest fetch failed for %s: %s", symbol, e)
        return {"symbol": symbol, "open_interest_contracts": None,
                "open_interest_usdt": None, "error": str(e)[:160]}


async def get_snapshot(exchange=None, symbol: str = "BTC/USDT") -> SentimentSnapshot:
    """Gather all sentiment data concurrently and return a unified snapshot."""
    binance_symbol = symbol.replace("/", "")  # BTC/USDT → BTCUSDT

    tasks = [get_fear_greed()]
    if exchange:
        tasks.append(get_funding_rate(exchange, symbol))
    tasks.append(get_open_interest(binance_symbol))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    fng_data = results[0] if not isinstance(results[0], Exception) else {}
    funding_data = results[1] if exchange and not isinstance(results[1], Exception) else {}
    oi_data = results[-1] if not isinstance(results[-1], Exception) else {}

    return SentimentSnapshot(
        fear_greed_value=fng_data.get("value"),
        fear_greed_label=fng_data.get("label"),
        funding_rate=funding_data.get("funding_rate"),
        funding_symbol=funding_data.get("symbol"),
        open_interest_usdt=oi_data.get("open_interest_usdt"),
        open_interest_symbol=oi_data.get("symbol"),
    )
