"""
Demo client — generates realistic synthetic OHLCV and price data.
Used for testing the full AI agent pipeline without exchange connectivity.
"""
import math
import random
import time
from typing import Optional


# Seed prices (close to real market values)
SEED_PRICES: dict[str, float] = {
    "BTC/USDT": 67000.0,
    "ETH/USDT": 3500.0,
    "SOL/USDT": 170.0,
    "BNB/USDT": 580.0,
    "AVAX/USDT": 38.0,
    "ARB/USDT": 1.1,
    "OP/USDT": 2.5,
    "BTC": 67000.0,
    "ETH": 3500.0,
    "SOL": 170.0,
}

_price_state: dict[str, float] = {}


def _current_price(symbol: str) -> float:
    base = SEED_PRICES.get(symbol, 100.0)
    if symbol not in _price_state:
        _price_state[symbol] = base
    # Random walk with mean reversion
    drift = (base - _price_state[symbol]) * 0.001
    shock = random.gauss(0, base * 0.002)
    _price_state[symbol] = max(_price_state[symbol] + drift + shock, base * 0.5)
    return _price_state[symbol]


def _generate_ohlcv(symbol: str, n: int = 200, interval_minutes: int = 60) -> list:
    base = SEED_PRICES.get(symbol, 100.0)
    price = base * random.uniform(0.85, 1.15)
    now_ms = int(time.time() * 1000)
    step_ms = interval_minutes * 60 * 1000

    ohlcv = []
    # Simulate trend phases: accumulation → bull → distribution → bear
    for i in range(n):
        phase = (i / n) * 4 * math.pi
        trend = math.sin(phase) * 0.0005 + random.gauss(0, 0.008)
        price *= 1 + trend
        price = max(price, base * 0.3)

        volatility = abs(random.gauss(0, price * 0.012))
        open_ = price
        close = price * (1 + random.gauss(0, 0.006))
        high = max(open_, close) + random.uniform(0, volatility)
        low = min(open_, close) - random.uniform(0, volatility)
        volume = random.uniform(base * 100, base * 800)

        ohlcv.append({
            "timestamp": now_ms - (n - i) * step_ms,
            "open": round(open_, 4),
            "high": round(high, 4),
            "low": round(low, 4),
            "close": round(close, 4),
            "volume": round(volume, 2),
        })
        price = close

    return ohlcv


class DemoClient:
    """Drop-in replacement for exchange clients in demo mode."""

    def __init__(self, exchange_name: str = "demo"):
        self.exchange_name = exchange_name
        self.orders: list[dict] = []
        self._order_id = 1000

    async def get_ticker(self, symbol: str) -> dict:
        price = _current_price(symbol)
        base_price = SEED_PRICES.get(symbol, 100.0)
        change = (price - base_price) / base_price * 100
        return {
            "symbol": symbol,
            "price": round(price, 4),
            "bid": round(price * 0.9999, 4),
            "ask": round(price * 1.0001, 4),
            "volume": round(price * random.uniform(5000, 20000), 2),
            "change_24h": round(change + random.gauss(0, 1), 2),
            "high_24h": round(price * 1.02, 4),
            "low_24h": round(price * 0.98, 4),
        }

    async def get_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 200) -> list:
        interval_map = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}
        minutes = interval_map.get(timeframe, 60)
        return _generate_ohlcv(symbol, min(limit, 500), minutes)

    async def get_orderbook(self, symbol: str, limit: int = 20) -> dict:
        price = _current_price(symbol)
        bids = [[round(price * (1 - i * 0.0002), 4), round(random.uniform(0.1, 5), 4)] for i in range(1, 11)]
        asks = [[round(price * (1 + i * 0.0002), 4), round(random.uniform(0.1, 5), 4)] for i in range(1, 11)]
        return {
            "bids": bids,
            "asks": asks,
            "spread": round(asks[0][0] - bids[0][0], 4),
        }

    async def get_balance(self) -> dict:
        return {
            "USDT": {"free": 10000.0, "used": 0.0, "total": 10000.0},
            "BTC": {"free": 0.1, "used": 0.0, "total": 0.1},
            "ETH": {"free": 1.5, "used": 0.0, "total": 1.5},
        }

    async def place_spot_order(
        self, symbol: str, side: str, amount: float, price: Optional[float] = None
    ) -> dict:
        fill_price = price or _current_price(symbol)
        order_id = str(self._order_id)
        self._order_id += 1
        order = {
            "id": order_id,
            "symbol": symbol,
            "side": side,
            "price": round(fill_price, 4),
            "amount": round(amount, 6),
            "filled": round(amount, 6),
            "status": "closed",
            "type": "limit" if price else "market",
        }
        self.orders.append(order)
        return order

    async def place_futures_order(
        self, symbol: str, side: str, amount: float, leverage: int = 3,
        price: Optional[float] = None, reduce_only: bool = False,
    ) -> dict:
        order = await self.place_spot_order(symbol, side, amount, price)
        order["leverage"] = leverage
        order["reduce_only"] = reduce_only
        return order

    async def place_perpetual_order(
        self, symbol: str, side: str, amount: float, leverage: int = 3,
        price: Optional[float] = None,
    ) -> dict:
        return await self.place_futures_order(symbol, side, amount, leverage, price)

    async def get_positions(self) -> list:
        return []

    async def close(self):
        pass
