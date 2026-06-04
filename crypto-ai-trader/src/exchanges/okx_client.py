import logging
from datetime import datetime
from typing import Dict, List, Optional

import ccxt.async_support as ccxt

from .base import Balance, BaseExchange, OHLCV, Order, Ticker
from .retry import with_retry
from ..core.config import settings

logger = logging.getLogger(__name__)


class OKXExchange(BaseExchange):
    name = "okx"

    def __init__(self):
        cfg = settings.get("exchanges", "okx") or {}
        self._client = ccxt.okx({
            "apiKey": cfg.get("api_key", ""),
            "secret": cfg.get("api_secret", ""),
            "password": cfg.get("passphrase", ""),
            "enableRateLimit": True,
        })
        if cfg.get("testnet"):
            self._client.set_sandbox_mode(True)

    async def close(self):
        await self._client.close()

    @with_retry()
    async def get_ticker(self, symbol: str) -> Ticker:
        data = await self._client.fetch_ticker(symbol)
        return Ticker(
            symbol=symbol,
            price=float(data["last"]),
            change_24h=float(data.get("percentage") or 0),
            volume_24h=float(data.get("quoteVolume") or 0),
            high_24h=float(data.get("high") or 0),
            low_24h=float(data.get("low") or 0),
        )

    @with_retry()
    async def get_ohlcv(self, symbol: str, timeframe: str = "5m", limit: int = 100) -> List[OHLCV]:
        data = await self._client.fetch_ohlcv(symbol, timeframe, limit=limit)
        return [
            OHLCV(datetime.fromtimestamp(row[0] / 1000), row[1], row[2], row[3], row[4], row[5])
            for row in data
        ]

    @with_retry()
    async def get_balance(self) -> Dict[str, Balance]:
        data = await self._client.fetch_balance()
        free  = data.get("free", {})  or {}
        used  = data.get("used", {})  or {}
        total = data.get("total", {}) or {}
        return {
            cur: Balance(cur, float(free.get(cur, 0) or 0), float(used.get(cur, 0) or 0), float(amt or 0))
            for cur, amt in total.items()
            if float(amt or 0) > 0
        }

    @with_retry(max_attempts=2)
    async def create_order(self, symbol: str, side: str, amount: float, price: Optional[float] = None) -> Order:
        # Round to the exchange's lot-size precision so live orders aren't rejected.
        try:
            if not self._client.markets:
                await self._client.load_markets()
            amount = float(self._client.amount_to_precision(symbol, amount))
        except Exception as e:
            logger.warning(f"amount_to_precision failed for {symbol}: {e}")
        if amount <= 0:
            raise ValueError(f"Order amount rounds to 0 for {symbol} (below min lot size)")
        fn = self._client.create_market_buy_order if side == "buy" else self._client.create_market_sell_order
        data = await fn(symbol, amount)
        return Order(
            id=str(data["id"]),
            symbol=symbol,
            side=side,
            type="market",
            price=float(data.get("price") or data.get("average") or 0),
            amount=float(data["amount"]),
            cost=float(data.get("cost") or 0),
            status=data.get("status", "closed"),
        )
