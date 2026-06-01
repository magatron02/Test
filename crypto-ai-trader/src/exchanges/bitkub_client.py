import hashlib
import hmac
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional

import aiohttp

from .base import Balance, BaseExchange, OHLCV, Order, Ticker
from ..core.config import settings

logger = logging.getLogger(__name__)

BITKUB_BASE = "https://api.bitkub.com"

SYMBOL_MAP = {
    "BTC/THB": "THB_BTC",
    "ETH/THB": "THB_ETH",
    "BNB/THB": "THB_BNB",
    "XRP/THB": "THB_XRP",
    "SOL/THB": "THB_SOL",
    "USDT/THB": "THB_USDT",
}


class BitkubExchange(BaseExchange):
    name = "bitkub"
    quote_currency = "THB"

    def __init__(self):
        cfg = settings.get("exchanges", "bitkub") or {}
        self._api_key = cfg.get("api_key", "")
        self._api_secret = cfg.get("api_secret", "")
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"X-BTK-APIKEY": self._api_key},
                timeout=aiohttp.ClientTimeout(total=10),
            )
        return self._session

    def _sign(self, payload: dict) -> str:
        body = "&".join(f"{k}={v}" for k, v in sorted(payload.items()))
        return hmac.new(self._api_secret.encode(), body.encode(), hashlib.sha256).hexdigest()

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def get_ticker(self, symbol: str) -> Ticker:
        mkt = SYMBOL_MAP.get(symbol, f"THB_{symbol.split('/')[0]}")
        session = await self._get_session()
        async with session.get(f"{BITKUB_BASE}/api/market/ticker", params={"sym": mkt}) as r:
            data = await r.json()

        if "error" in data and data["error"] != 0:
            raise ValueError(f"Bitkub error: {data}")

        result = data.get("result", {}).get(mkt, {})
        return Ticker(
            symbol=symbol,
            price=float(result.get("last", 0)),
            change_24h=float(result.get("percentChange", 0)),
            volume_24h=float(result.get("baseVolume", 0)),
            high_24h=float(result.get("highestBid", 0)),
            low_24h=float(result.get("lowestAsk", 0)),
        )

    async def get_ohlcv(self, symbol: str, timeframe: str = "5m", limit: int = 100) -> List[OHLCV]:
        mkt = SYMBOL_MAP.get(symbol, f"THB_{symbol.split('/')[0]}")
        tf_map = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}
        resolution = tf_map.get(timeframe, 300)
        end = int(time.time())
        start = end - resolution * limit

        session = await self._get_session()
        async with session.get(
            f"{BITKUB_BASE}/tradingview/history",
            params={"symbol": mkt, "resolution": resolution, "from": start, "to": end}
        ) as r:
            data = await r.json()

        if data.get("s") != "ok":
            return []

        return [
            OHLCV(
                timestamp=datetime.fromtimestamp(data["t"][i]),
                open=data["o"][i],
                high=data["h"][i],
                low=data["l"][i],
                close=data["c"][i],
                volume=data["v"][i],
            )
            for i in range(len(data["t"]))
        ]

    async def get_balance(self) -> Dict[str, Balance]:
        ts = int(time.time() * 1000)
        payload = {"ts": ts}
        sig = self._sign(payload)
        payload["sig"] = sig

        session = await self._get_session()
        async with session.post(f"{BITKUB_BASE}/api/market/wallet", json=payload) as r:
            data = await r.json()

        if data.get("error", 0) != 0:
            raise ValueError(f"Bitkub balance error: {data}")

        result = data.get("result", {})
        return {
            cur: Balance(cur, float(amt), 0.0, float(amt))
            for cur, amt in result.items()
            if float(amt) > 0
        }

    async def create_order(self, symbol: str, side: str, amount: float, price: Optional[float] = None) -> Order:
        mkt = SYMBOL_MAP.get(symbol, f"THB_{symbol.split('/')[0]}")
        ts = int(time.time() * 1000)
        payload = {"sym": mkt, "amt": amount, "rat": price or 0, "typ": "market", "ts": ts}
        sig = self._sign(payload)
        payload["sig"] = sig

        endpoint = "buy" if side == "buy" else "sell"
        session = await self._get_session()
        async with session.post(f"{BITKUB_BASE}/api/market/{endpoint}", json=payload) as r:
            data = await r.json()

        if data.get("error", 0) != 0:
            raise ValueError(f"Bitkub order error: {data}")

        result = data["result"]
        return Order(
            id=str(result.get("id", "")),
            symbol=symbol,
            side=side,
            type="market",
            price=float(result.get("rat", 0)),
            amount=float(result.get("amt", amount)),
            cost=float(result.get("rec", 0)),
            status="closed",
        )
