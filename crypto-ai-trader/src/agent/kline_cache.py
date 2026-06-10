"""
Parquet-backed kline cache for backtesting.

Saves Binance klines to data/kline_cache/<symbol>_<tf>m.parquet so repeated
backtest runs skip the API call. Cache is considered fresh when the last stored
candle is within one interval of now.

Usage
-----
from .kline_cache import KlineCache
cache = KlineCache()
candles = await cache.get_or_fetch("BTC/USDT", days=90)
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "kline_cache"
_BINANCE_KLINES = "https://api.binance.com/api/v3/klines"


class KlineCache:
    def __init__(self, cache_dir: Optional[Path] = None):
        self._dir = Path(cache_dir or _DEFAULT_CACHE_DIR)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, symbol: str, tf_minutes: int) -> Path:
        sym = symbol.replace("/", "").upper()
        return self._dir / f"{sym}_{tf_minutes}m.parquet"

    def _is_fresh(self, candles: List[dict], tf_minutes: int) -> bool:
        if not candles:
            return False
        last_ts = candles[-1]["ts"]
        if isinstance(last_ts, str):
            last_ts = datetime.fromisoformat(last_ts)
        age = datetime.utcnow() - last_ts
        return age < timedelta(minutes=tf_minutes * 2)

    def _load(self, path: Path) -> List[dict]:
        try:
            import pandas as pd
            df = pd.read_parquet(path)
            records = df.to_dict("records")
            for r in records:
                if not isinstance(r["ts"], datetime):
                    r["ts"] = pd.Timestamp(r["ts"]).to_pydatetime()
            return records
        except Exception as exc:
            logger.debug("kline_cache: load failed %s — %s", path, exc)
            return []

    def _save(self, path: Path, candles: List[dict]) -> None:
        try:
            import pandas as pd
            df = pd.DataFrame(candles)
            df.to_parquet(path, index=False)
        except Exception as exc:
            logger.warning("kline_cache: save failed — %s", exc)

    async def get_or_fetch(
        self,
        symbol: str,
        days: int,
        tf_minutes: int = 60,
        force_refresh: bool = False,
    ) -> List[dict]:
        path = self._path(symbol, tf_minutes)
        needed = days * 24 * 60 // tf_minutes

        if not force_refresh and path.exists():
            cached = self._load(path)
            if len(cached) >= needed and self._is_fresh(cached, tf_minutes):
                logger.debug("kline_cache: hit %s (%d bars)", symbol, len(cached))
                return cached[-needed:]

        candles = await _fetch_binance(symbol, needed, tf_minutes)
        if candles:
            existing = self._load(path) if path.exists() else []
            merged = _merge(existing, candles)
            self._save(path, merged)
            return merged[-needed:]
        return []

    def invalidate(self, symbol: str, tf_minutes: int = 60) -> None:
        p = self._path(symbol, tf_minutes)
        if p.exists():
            p.unlink()
            logger.info("kline_cache: invalidated %s", p.name)


# ── Fetch helpers ─────────────────────────────────────────────────────────────

async def _fetch_binance(symbol: str, needed: int, tf_minutes: int) -> List[dict]:
    import aiohttp
    binance_sym = symbol.replace("/", "")
    interval_map = {1: "1m", 5: "5m", 15: "15m", 60: "1h", 240: "4h", 1440: "1d"}
    interval = interval_map.get(tf_minutes, "1h")
    out: List[dict] = []
    end_time: Optional[int] = None

    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        ) as session:
            while len(out) < needed:
                limit = min(1000, needed - len(out))
                params: Dict = {"symbol": binance_sym, "interval": interval, "limit": limit}
                if end_time is not None:
                    params["endTime"] = end_time
                async with session.get(_BINANCE_KLINES, params=params) as resp:
                    resp.raise_for_status()
                    raw = await resp.json()
                if not raw:
                    break
                chunk = [
                    {
                        "ts":     datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc).replace(tzinfo=None),
                        "open":   float(row[1]),
                        "high":   float(row[2]),
                        "low":    float(row[3]),
                        "close":  float(row[4]),
                        "volume": float(row[5]),
                        "sim_regime": "LIVE",
                    }
                    for row in raw
                ]
                out = chunk + out
                end_time = raw[0][0] - 1
                if len(raw) < limit:
                    break
    except Exception as exc:
        logger.warning("kline_cache: fetch failed for %s — %s", symbol, exc)

    return out


def _merge(existing: List[dict], fresh: List[dict]) -> List[dict]:
    if not existing:
        return fresh
    if not fresh:
        return existing
    last_existing = existing[-1]["ts"]
    new_only = [c for c in fresh if c["ts"] > last_existing]
    return existing + new_only
