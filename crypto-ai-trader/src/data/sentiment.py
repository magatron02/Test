"""
On-chain & sentiment data layer.

Sources (all free, no API key required):
  • Fear & Greed Index  — alternative.me/fng
  • Funding rate        — ccxt exchange.fetchFundingRate()
  • Open Interest       — Binance futures API (public, no key needed)
  • Long/Short ratio    — Binance futures data (public)
  • Taker buy/sell flow — Binance futures data (public)

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
_BINANCE_LS_URL = "https://fapi.binance.com/futures/data/globalLongShortAccountRatio"
_BINANCE_TAKER_URL = "https://fapi.binance.com/futures/data/takerlongshortRatio"

# In-memory cache: (value, expires_at)
_cache: dict = {}
_CACHE_TTL = {
    "fng": 3600,       # 1 h — index updates once per day
    "funding": 60,     # 1 min — funding updates every 8 h but we poll more often
    "oi": 60,          # 1 min
    "ls": 300,         # 5 min — long/short ratio bucket period
    "taker": 300,      # 5 min — taker buy/sell volume bucket period
}

# OI samples kept for change-over-time computation: symbol → list[(ts, contracts)]
_oi_history: dict = {}
_OI_WINDOW_SEC = 900   # compare against the oldest sample within 15 min


@dataclass
class SentimentSnapshot:
    fear_greed_value: Optional[int] = None        # 0–100
    fear_greed_label: Optional[str] = None        # "Extreme Fear" … "Extreme Greed"
    funding_rate: Optional[float] = None          # raw rate, e.g. 0.0001 = 0.01%
    funding_symbol: Optional[str] = None
    open_interest_usdt: Optional[float] = None   # total OI in USDT
    open_interest_symbol: Optional[str] = None
    oi_change_pct: Optional[float] = None         # OI % change over ~15 min
    long_short_ratio: Optional[float] = None      # global account long/short ratio
    taker_buy_sell_ratio: Optional[float] = None  # taker buy vol / sell vol
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

    @property
    def derivatives_bias(self) -> str:
        """Directional hint from the derivatives book (label only)."""
        return derivatives_bias(
            self.long_short_ratio,
            self.taker_buy_sell_ratio,
            self.oi_change_pct,
            self.funding_rate,
        )[0]

    @property
    def derivatives_score(self) -> float:
        """Numeric derivatives bias in [-1, 1] (>0 bullish, <0 bearish)."""
        return derivatives_bias(
            self.long_short_ratio,
            self.taker_buy_sell_ratio,
            self.oi_change_pct,
            self.funding_rate,
        )[1]


def derivatives_bias(
    long_short_ratio: Optional[float],
    taker_buy_sell_ratio: Optional[float],
    oi_change_pct: Optional[float],
    funding_rate: Optional[float],
) -> tuple:
    """Combine derivatives signals into a contrarian-aware bias.

    Pure function (easy to unit-test). Returns ``(label, score)`` where
    ``score`` is clamped to [-1, 1]; positive = bullish lean, negative =
    bearish lean. Labels reuse the Fear & Greed vocabulary so the engine can
    treat both biases the same way.

    Logic:
      • Crowded retail longs (high L/S ratio) → contrarian bearish, and vice versa.
      • Aggressive taker buying (taker ratio > 1) → momentum-bullish.
      • Stretched funding (longs paying shorts heavily) → contrarian bearish.
      • Rising open interest amplifies the dominant lean (conviction), it does
        not set direction on its own.
    """
    score = 0.0

    if long_short_ratio is not None:
        if long_short_ratio >= 2.0:
            score -= 0.4
        elif long_short_ratio >= 1.5:
            score -= 0.2
        elif long_short_ratio <= 0.5:
            score += 0.4
        elif long_short_ratio <= 0.7:
            score += 0.2

    if taker_buy_sell_ratio is not None:
        if taker_buy_sell_ratio >= 1.2:
            score += 0.2
        elif taker_buy_sell_ratio <= 0.8:
            score -= 0.2

    if funding_rate is not None:
        if funding_rate >= 0.0005:      # > 0.05% — crowded longs
            score -= 0.2
        elif funding_rate <= -0.0005:   # < -0.05% — crowded shorts
            score += 0.2

    # Rising OI scales conviction of an existing lean (not direction).
    if oi_change_pct is not None and oi_change_pct > 0.05 and score != 0.0:
        score *= 1.2

    score = max(-1.0, min(1.0, score))

    if score >= 0.4:
        label = "CONTRARIAN_BUY"
    elif score >= 0.2:
        label = "CAUTIOUS_BUY"
    elif score <= -0.4:
        label = "CONTRARIAN_SELL"
    elif score <= -0.2:
        label = "CAUTIOUS_SELL"
    else:
        label = "NEUTRAL"

    return label, round(score, 3)


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


def _record_oi(symbol: str, contracts: float) -> Optional[float]:
    """Append an OI sample and return % change vs the oldest sample in window."""
    if contracts is None:
        return None
    now = time.time()
    hist = _oi_history.setdefault(symbol, [])
    hist.append((now, contracts))
    cutoff = now - _OI_WINDOW_SEC
    # Drop samples older than the window, but always keep at least one anchor.
    while len(hist) > 1 and hist[0][0] < cutoff:
        hist.pop(0)
    base = hist[0][1]
    if base and base > 0 and len(hist) >= 2:
        return round((contracts - base) / base, 4)
    return None


async def get_long_short_ratio(symbol: str = "BTCUSDT", period: str = "5m") -> dict:
    """Global account long/short ratio from Binance futures. Cached 5 min.

    Ratio > 1 means more accounts net-long. Extreme values are a contrarian tell.
    """
    cache_key = f"ls:{symbol}:{period}"
    cached = _cached(cache_key, _CACHE_TTL["ls"])
    if cached is not None:
        return cached
    try:
        url = f"{_BINANCE_LS_URL}?symbol={symbol}&period={period}&limit=1"
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(url) as resp:
                data = await resp.json(content_type=None)
        if not isinstance(data, list) or not data:
            return {"symbol": symbol, "long_short_ratio": None, "error": "unexpected response"}
        entry = data[-1]
        result = {
            "symbol": symbol,
            "long_short_ratio": float(entry["longShortRatio"]),
            "long_account": float(entry.get("longAccount", 0)) or None,
            "short_account": float(entry.get("shortAccount", 0)) or None,
        }
        _store(cache_key, result, _CACHE_TTL["ls"])
        return result
    except Exception as e:
        logger.warning("Long/short ratio fetch failed for %s: %s", symbol, e)
        return {"symbol": symbol, "long_short_ratio": None, "error": str(e)[:160]}


async def get_taker_ratio(symbol: str = "BTCUSDT", period: str = "5m") -> dict:
    """Taker buy/sell volume ratio from Binance futures. Cached 5 min.

    Ratio > 1 means aggressive market buying dominates (momentum-bullish).
    """
    cache_key = f"taker:{symbol}:{period}"
    cached = _cached(cache_key, _CACHE_TTL["taker"])
    if cached is not None:
        return cached
    try:
        url = f"{_BINANCE_TAKER_URL}?symbol={symbol}&period={period}&limit=1"
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(url) as resp:
                data = await resp.json(content_type=None)
        if not isinstance(data, list) or not data:
            return {"symbol": symbol, "taker_buy_sell_ratio": None, "error": "unexpected response"}
        entry = data[-1]
        result = {
            "symbol": symbol,
            "taker_buy_sell_ratio": float(entry["buySellRatio"]),
        }
        _store(cache_key, result, _CACHE_TTL["taker"])
        return result
    except Exception as e:
        logger.warning("Taker ratio fetch failed for %s: %s", symbol, e)
        return {"symbol": symbol, "taker_buy_sell_ratio": None, "error": str(e)[:160]}


async def get_snapshot(exchange=None, symbol: str = "BTC/USDT") -> SentimentSnapshot:
    """Gather all sentiment data concurrently and return a unified snapshot."""
    binance_symbol = symbol.replace("/", "")  # BTC/USDT → BTCUSDT

    fng_task = get_fear_greed()
    funding_task = get_funding_rate(exchange, symbol) if exchange else None
    oi_task = get_open_interest(binance_symbol)
    ls_task = get_long_short_ratio(binance_symbol)
    taker_task = get_taker_ratio(binance_symbol)

    tasks = [fng_task]
    if funding_task is not None:
        tasks.append(funding_task)
    tasks += [oi_task, ls_task, taker_task]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    def _ok(r):
        return r if not isinstance(r, Exception) else {}

    idx = 0
    fng_data = _ok(results[idx]); idx += 1
    funding_data = {}
    if funding_task is not None:
        funding_data = _ok(results[idx]); idx += 1
    oi_data = _ok(results[idx]); idx += 1
    ls_data = _ok(results[idx]); idx += 1
    taker_data = _ok(results[idx]); idx += 1

    oi_change = _record_oi(binance_symbol, oi_data.get("open_interest_contracts"))

    return SentimentSnapshot(
        fear_greed_value=fng_data.get("value"),
        fear_greed_label=fng_data.get("label"),
        funding_rate=funding_data.get("funding_rate"),
        funding_symbol=funding_data.get("symbol"),
        open_interest_usdt=oi_data.get("open_interest_usdt"),
        open_interest_symbol=oi_data.get("symbol"),
        oi_change_pct=oi_change,
        long_short_ratio=ls_data.get("long_short_ratio"),
        taker_buy_sell_ratio=taker_data.get("taker_buy_sell_ratio"),
    )
