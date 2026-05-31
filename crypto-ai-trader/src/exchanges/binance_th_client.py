import hashlib
import hmac
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urlencode

import aiohttp

from .base import Balance, BaseExchange, OHLCV, Order, Ticker
from ..core.config import settings

logger = logging.getLogger(__name__)

BINANCE_TH_BASE = "https://api.binance.th"


class BinanceTHExchange(BaseExchange):
    """Binance TH (Thailand) exchange client."""

    name = "binance_th"

    def __init__(self):
        cfg = settings.get("exchanges", "binance_th") or {}
        self._api_key = cfg.get("api_key", "")
        self._api_secret = cfg.get("api_secret", "")
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"X-MBX-APIKEY": self._api_key},
                timeout=aiohttp.ClientTimeout(total=10),
            )
        return self._session

    def _sign(self, params: dict) -> str:
        query = urlencode(params)
        return hmac.new(self._api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def get_ticker(self, symbol: str) -> Ticker:
        ccxt_sym = symbol.replace("/", "")
        session = await self._get_session()
        async with session.get(
            f"{BINANCE_TH_BASE}/api/v3/ticker/24hr",
            params={"symbol": ccxt_sym}
        ) as r:
            data = await r.json()

        return Ticker(
            symbol=symbol,
            price=float(data["lastPrice"]),
            change_24h=float(data["priceChangePercent"]),
            volume_24h=float(data["volume"]),
            high_24h=float(data["highPrice"]),
            low_24h=float(data["lowPrice"]),
        )

    async def get_ohlcv(self, symbol: str, timeframe: str = "5m", limit: int = 100) -> List[OHLCV]:
        ccxt_sym = symbol.replace("/", "")
        session = await self._get_session()
        async with session.get(
            f"{BINANCE_TH_BASE}/api/v3/klines",
            params={"symbol": ccxt_sym, "interval": timeframe, "limit": limit}
        ) as r:
            data = await r.json()

        return [
            OHLCV(datetime.fromtimestamp(row[0] / 1000), float(row[1]), float(row[2]),
                  float(row[3]), float(row[4]), float(row[5]))
            for row in data
        ]

    async def get_balance(self) -> Dict[str, Balance]:
        params = {"timestamp": int(time.time() * 1000)}
        params["signature"] = self._sign(params)
        session = await self._get_session()
        async with session.get(f"{BINANCE_TH_BASE}/api/v3/account", params=params) as r:
            data = await r.json()

        return {
            b["asset"]: Balance(b["asset"], float(b["free"]), float(b["locked"]),
                                float(b["free"]) + float(b["locked"]))
            for b in data.get("balances", [])
            if float(b["free"]) + float(b["locked"]) > 0
        }

    async def create_order(self, symbol: str, side: str, amount: float, price: Optional[float] = None) -> Order:
        params = {
            "symbol": symbol.replace("/", ""),
            "side": side.upper(),
            "type": "MARKET",
            "quantity": amount,
            "timestamp": int(time.time() * 1000),
        }
        params["signature"] = self._sign(params)
        session = await self._get_session()
        async with session.post(f"{BINANCE_TH_BASE}/api/v3/order", params=params) as r:
            data = await r.json()

        if "code" in data and data["code"] < 0:
            raise ValueError(f"Binance TH order error: {data['msg']}")

        exec_price = float(data.get("fills", [{}])[0].get("price", 0)) if data.get("fills") else 0
        return Order(
            id=str(data["orderId"]),
            symbol=symbol,
            side=side,
            type="market",
            price=exec_price,
            amount=float(data["executedQty"]),
            cost=float(data.get("cummulativeQuoteQty", 0)),
            status="closed" if data["status"] == "FILLED" else data["status"].lower(),
        )
