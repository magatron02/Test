import hashlib
import hmac
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urlencode

import httpx

from .base import Balance, BaseExchange, OHLCV, Order, Ticker
from ..core.config import settings

logger = logging.getLogger(__name__)

BINANCE_TH_BASE  = "https://api.binance.th"
BINANCE_COM_BASE = "https://api.binance.com"   # price-data fallback
API_V1  = f"{BINANCE_TH_BASE}/api/v1"
API_COM = f"{BINANCE_COM_BASE}/api/v3"

SYMBOL_MAP = {
    "BTC/THB":   "BTCTHB",
    "ETH/THB":   "ETHTHB",
    "BNB/THB":   "BNBTHB",
    "XRP/THB":   "XRPTHB",
    "SOL/THB":   "SOLTHB",
    "USDT/THB":  "USDTTHB",
    "ADA/THB":   "ADATHB",
    "DOGE/THB":  "DOGETHB",
    "MATIC/THB": "MATICTHB",
    "DOT/THB":   "DOTTHB",
}

TIMEFRAME_MAP = {
    "1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m",
    "30m": "30m", "1h": "1h", "2h": "2h", "4h": "4h",
    "6h": "6h", "12h": "12h", "1d": "1d", "1w": "1w",
}


def _to_th_symbol(symbol: str) -> str:
    return SYMBOL_MAP.get(symbol, symbol.replace("/", ""))


def _to_usdt_symbol(symbol: str) -> str:
    """BTC/THB → BTCUSDT  (for Binance global fallback)."""
    base = symbol.split("/")[0]
    return f"{base}USDT"


class BinanceTHExchange(BaseExchange):
    """Binance TH — price data via Binance global fallback, orders via api.binance.th."""

    name = "binance_th"
    quote_currency = "THB"

    def __init__(self):
        cfg = settings.get("exchanges", "binance_th") or {}
        self._api_key    = cfg.get("api_key", "")
        self._api_secret = cfg.get("api_secret", "")
        self._client:     Optional[httpx.AsyncClient] = None
        self._pub_client: Optional[httpx.AsyncClient] = None  # public/no-auth

    def _auth_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers={"X-MBX-APIKEY": self._api_key},
                timeout=httpx.Timeout(15.0),
                follow_redirects=True,
            )
        return self._client

    def _pub(self) -> httpx.AsyncClient:
        if self._pub_client is None or self._pub_client.is_closed:
            self._pub_client = httpx.AsyncClient(
                timeout=httpx.Timeout(10.0),
                follow_redirects=True,
            )
        return self._pub_client

    def _sign(self, params: dict) -> str:
        query = urlencode(params)
        return hmac.new(
            self._api_secret.encode(),
            query.encode(),
            hashlib.sha256,
        ).hexdigest()

    async def close(self):
        for c in (self._client, self._pub_client):
            if c and not c.is_closed:
                await c.aclose()

    # ------------------------------------------------------------------ #
    # Price helpers — try api.binance.th, fall back to api.binance.com    #
    # ------------------------------------------------------------------ #

    async def _thb_rate(self) -> float:
        """USDT/THB rate from Binance global (approx 34)."""
        try:
            r = await self._pub().get(f"{API_COM}/ticker/price", params={"symbol": "USDTTHB"})
            if r.status_code == 200:
                return float(r.json().get("price", 34.0))
        except Exception:
            pass
        return 34.0

    async def get_ticker(self, symbol: str) -> Ticker:
        th_sym = _to_th_symbol(symbol)
        # Try direct first
        try:
            r = await self._pub().get(f"{API_V1}/ticker/24hr", params={"symbol": th_sym}, timeout=5.0)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, dict) and "lastPrice" in data:
                    return Ticker(
                        symbol=symbol,
                        price=float(data["lastPrice"]),
                        change_24h=float(data["priceChangePercent"]),
                        volume_24h=float(data["volume"]),
                        high_24h=float(data["highPrice"]),
                        low_24h=float(data["lowPrice"]),
                    )
        except Exception as e:
            logger.debug(f"BinanceTH direct ticker failed ({e}), using Binance global fallback")

        # Fallback: Binance global USDT price × THB rate
        usdt_sym = _to_usdt_symbol(symbol)
        rate = await self._thb_rate()
        r = await self._pub().get(f"{API_COM}/ticker/24hr", params={"symbol": usdt_sym})
        r.raise_for_status()
        data = r.json()
        return Ticker(
            symbol=symbol,
            price=float(data["lastPrice"]) * rate,
            change_24h=float(data["priceChangePercent"]),
            volume_24h=float(data["volume"]),
            high_24h=float(data["highPrice"]) * rate,
            low_24h=float(data["lowPrice"]) * rate,
        )

    async def get_ohlcv(self, symbol: str, timeframe: str = "5m", limit: int = 100) -> List[OHLCV]:
        th_sym = _to_th_symbol(symbol)
        tf = TIMEFRAME_MAP.get(timeframe, "5m")
        # Try direct
        try:
            r = await self._pub().get(
                f"{API_V1}/klines",
                params={"symbol": th_sym, "interval": tf, "limit": limit},
                timeout=5.0,
            )
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list):
                    return [
                        OHLCV(
                            timestamp=datetime.fromtimestamp(row[0] / 1000),
                            open=float(row[1]), high=float(row[2]),
                            low=float(row[3]),  close=float(row[4]),
                            volume=float(row[5]),
                        )
                        for row in data
                    ]
        except Exception as e:
            logger.debug(f"BinanceTH direct ohlcv failed ({e}), using Binance global fallback")

        # Fallback
        usdt_sym = _to_usdt_symbol(symbol)
        rate = await self._thb_rate()
        r = await self._pub().get(
            f"{API_COM}/klines",
            params={"symbol": usdt_sym, "interval": tf, "limit": limit},
        )
        r.raise_for_status()
        data = r.json()
        return [
            OHLCV(
                timestamp=datetime.fromtimestamp(row[0] / 1000),
                open=float(row[1]) * rate,  high=float(row[2]) * rate,
                low=float(row[3]) * rate,   close=float(row[4]) * rate,
                volume=float(row[5]),
            )
            for row in data
        ]

    # ------------------------------------------------------------------ #
    # Account / orders — must use api.binance.th (no fallback)            #
    # ------------------------------------------------------------------ #

    async def get_balance(self) -> Dict[str, Balance]:
        params = {"timestamp": int(time.time() * 1000)}
        params["signature"] = self._sign(params)
        r = await self._auth_client().get(f"{API_V1}/account", params=params)
        r.raise_for_status()
        data = r.json()
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
            "symbol":    th_sym,
            "side":      side.upper(),
            "type":      "MARKET",
            "quantity":  amount,
            "timestamp": int(time.time() * 1000),
        }
        params["signature"] = self._sign(params)
        r = await self._auth_client().post(f"{API_V1}/order", params=params)
        r.raise_for_status()
        data = r.json()
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
