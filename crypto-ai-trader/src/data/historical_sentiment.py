"""Historical Fear & Greed Index and funding-rate helpers for GBM training.

Provides date-keyed lookup tables that hourly_trainer joins to each candle
so the model sees macro-sentiment context without look-ahead bias.

Sources (free, no API key needed):
  • alternative.me/fng  — full F&G history
  • fapi.binance.com    — historical funding rates (BTCUSDT proxy)
"""
import logging
import time
from datetime import datetime, timedelta, timezone

import aiohttp

logger = logging.getLogger(__name__)

_FNG_URL = "https://api.alternative.me/fng/?limit=0&format=json"
_FUNDING_URL = "https://fapi.binance.com/fapi/v1/fundingRate"

# Module-level cache — refreshed once per day
_fng_cache: dict = {}
_fng_cache_ts: float = 0.0
_FNG_TTL = 82800  # 23 h


async def fetch_historical_fng(session: aiohttp.ClientSession) -> dict:
    """Return {YYYY-MM-DD: fng_value_int} for the full F&G history."""
    global _fng_cache, _fng_cache_ts
    now = time.monotonic()
    if _fng_cache and (now - _fng_cache_ts) < _FNG_TTL:
        return _fng_cache
    try:
        async with session.get(_FNG_URL, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)
        result: dict = {}
        for entry in data.get("data", []):
            ts = int(entry.get("timestamp", 0))
            val = int(entry.get("value", 50))
            date_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
            result[date_str] = val
        _fng_cache = result
        _fng_cache_ts = now
        logger.info("historical_sentiment: loaded %d F&G entries", len(result))
        return result
    except Exception as exc:
        logger.warning("historical_sentiment: F&G fetch failed — %s", exc)
        return _fng_cache


async def fetch_historical_funding(
    session: aiohttp.ClientSession,
    symbol: str = "BTCUSDT",
    limit: int = 500,
) -> dict:
    """Return {YYYY-MM-DD-HH: funding_rate} from Binance futures (proxy for all pairs)."""
    try:
        async with session.get(
            _FUNDING_URL,
            params={"symbol": symbol, "limit": limit},
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status != 200:
                return {}
            data = await resp.json()
        result: dict = {}
        for entry in data:
            ts = int(entry.get("fundingTime", 0)) // 1000
            rate = float(entry.get("fundingRate", 0.0))
            hour_key = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d-%H")
            result[hour_key] = rate
        logger.debug("historical_sentiment: loaded %d funding entries for %s", len(result), symbol)
        return result
    except Exception as exc:
        logger.warning("historical_sentiment: funding fetch failed (%s) — %s", symbol, exc)
        return {}


def fng_for_candle(fng_hist: dict, candle_ts: datetime) -> tuple:
    """(fng_normalised_0_1, fng_7d_momentum) — no look-ahead."""
    date_str = candle_ts.strftime("%Y-%m-%d")
    val = fng_hist.get(date_str, 50) / 100.0
    past_str = (candle_ts - timedelta(days=7)).strftime("%Y-%m-%d")
    past_val = fng_hist.get(past_str, 50) / 100.0
    return round(val, 4), round(val - past_val, 4)


def funding_for_candle(funding_hist: dict, candle_ts: datetime) -> float:
    """Nearest prior funding rate for a candle; falls back to 0.0."""
    for h in range(9):
        key = (candle_ts - timedelta(hours=h)).strftime("%Y-%m-%d-%H")
        if key in funding_hist:
            return funding_hist[key]
    return 0.0
