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

# Binance TH uses /api/v1/ (not v3 like global Binance)
BINANCE_TH_BASE = "https://api.binance.th"
API_V1 = f"{BINANCE_TH_BASE}/api/v1"

# Symbol mapping: our internal format → Binance TH format
# Binance TH trades against THB (e.g. BTCTHB, ETHTHB)
SYMBOL_MAP = {
    "BTC/THB":  "BTCTHB",
    "ETH/THB":  "ETHTHB",
    "BNB/THB":  "BNBTHB",
    "XRP/THB":  "XRPTHB",
    "SOL/THB":  "SOLTHB",
    "USDT/THB": "USDTTHB",
    "ADA/THB":  "ADATHB",
    "DOGE/THB": "DOGETHB",
    "MATIC/THB":"MATICTHB",
    "DOT/THB":  "DOTTHB",
}

TIMEFRAME_MAP = {
    "1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m",
    "30m": "30m", "1h": "1h", "2h": "2h", "4h": "4h",
    "6h": "6h", "12h": "12h", "1d": "1d", "1w": "1w",
}


def _to_th_symbol(symbol: str) -> str:
    """Convert 'BTC/THB' → 'BTCTHB'."""
    if symbol in SYMBOL_MAP:
        return SYMBOL_MAP[symbol]
    # Fallback: strip slash
    return symbol.replace("/", "")


class BinanceTHExchange(BaseExchange):
    """Binance TH (Thailand) exchange — trades THB pairs via /api/v1/ endpoints."""

    name = "binance_th"
    quote_currency = "THB"

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
        return hmac.new(
            self._api_secret.encode(),
            query.encode(),
            hashlib.sha256,
        ).hexdigest()

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def get_ticker(self, symbol: str) -> Ticker:
        th_sym = _to_th_symbol(symbol)
        session = await self._get_session()
        async with session.get(
            f"{API_V1}/ticker/24hr",
            params={"symbol": th_sym},
        ) as r:
            data = await r.json()

        if isinstance(data, dict) and "code" in data:
            raise ValueError(f"Binance TH ticker error: {data}")

        return Ticker(
            symbol=symbol,
            price=float(data["lastPrice"]),
            change_24h=float(data["priceChangePercent"]),
            volume_24h=float(data["volume"]),
            high_24h=float(data["highPrice"]),
            low_24h=float(data["lowPrice"]),
        )

    async def get_ohlcv(self, symbol: str, timeframe: str = "5m", limit: int = 100) -> List[OHLCV]:
        th_sym = _to_th_symbol(symbol)
        tf = TIMEFRAME_MAP.get(timeframe, "5m")
        session = await self._get_session()
        async with session.get(
            f"{API_V1}/klines",
            params={"symbol": th_sym, "interval": tf, "limit": limit},
        ) as r:
            data = await r.json()

        if isinstance(data, dict) and "code" in data:
            raise ValueError(f"Binance TH klines error: {data}")

        return [
            OHLCV(
                timestamp=datetime.fromtimestamp(row[0] / 1000),
                open=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=float(row[4]),
                volume=float(row[5]),
            )
            for row in data
        ]

    async def get_balance(self) -> Dict[str, Balance]:
        params = {"timestamp": int(time.time() * 1000)}
        params["signature"] = self._sign(params)
        session = await self._get_session()
        async with session.get(f"{API_V1}/account", params=params) as r:
            data = await r.json()

        if "code" in data:
            raise ValueError(f"Binance TH account error: {data.get('msg', data)}")

        return {
            b["asset"]: Balance(
                b["asset"],
                float(b["free"]),
                float(b["locked"]),
                float(b["free"]) + float(b["locked"]),
            )
            for b in data.get("balances", [])
            if float(b["free"]) + float(b["locked"]) > 0
        }

    async def create_order(
        self, symbol: str, side: str, amount: float, price: Optional[float] = None
    ) -> Order:
        th_sym = _to_th_symbol(symbol)
        params = {
            "symbol": th_sym,
            "side": side.upper(),
            "type": "MARKET",
            "quantity": amount,
            "timestamp": int(time.time() * 1000),
        }
        params["signature"] = self._sign(params)
        session = await self._get_session()
        async with session.post(f"{API_V1}/order", params=params) as r:
            data = await r.json()

        if "code" in data and int(data["code"]) < 0:
            raise ValueError(f"Binance TH order error: {data.get('msg', data)}")

        fills = data.get("fills", [])
        exec_price = float(fills[0]["price"]) if fills else 0.0
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

    @staticmethod
    def supported_symbols() -> List[str]:
        return list(SYMBOL_MAP.keys())
