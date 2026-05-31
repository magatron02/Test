import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import aiohttp

from .base import Balance, BaseExchange, OHLCV, Order, Ticker
from ..core.config import settings

logger = logging.getLogger(__name__)

BINANCE_BASE = "https://api.binance.com"
BINANCE_TH_BASE = "https://api.binance.th"


class DemoExchange(BaseExchange):
    """Paper trading with real Binance market data."""

    name = "demo"
    is_demo = True

    def __init__(self):
        cfg = settings.get("exchanges", "demo") or {}
        self._cash = float(cfg.get("virtual_balance_usdt", 10000.0))
        self._initial_cash = self._cash
        self._positions: Dict[str, dict] = {}  # symbol -> {amount, avg_price}
        self._orders: List[Order] = []
        self._order_counter = 1
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def get_ticker(self, symbol: str) -> Ticker:
        ccxt_sym = symbol.replace("/", "")
        session = await self._get_session()
        try:
            async with session.get(
                f"{BINANCE_BASE}/api/v3/ticker/24hr",
                params={"symbol": ccxt_sym}
            ) as resp:
                data = await resp.json()
            return Ticker(
                symbol=symbol,
                price=float(data["lastPrice"]),
                change_24h=float(data["priceChangePercent"]),
                volume_24h=float(data["volume"]),
                high_24h=float(data["highPrice"]),
                low_24h=float(data["lowPrice"]),
            )
        except Exception as e:
            logger.warning(f"Ticker fetch failed for {symbol}: {e}")
            raise

    async def get_ohlcv(self, symbol: str, timeframe: str = "5m", limit: int = 100) -> List[OHLCV]:
        ccxt_sym = symbol.replace("/", "")
        session = await self._get_session()
        try:
            async with session.get(
                f"{BINANCE_BASE}/api/v3/klines",
                params={"symbol": ccxt_sym, "interval": timeframe, "limit": limit}
            ) as resp:
                data = await resp.json()
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
        except Exception as e:
            logger.warning(f"OHLCV fetch failed for {symbol}: {e}")
            raise

    async def get_balance(self) -> Dict[str, Balance]:
        balances = {
            "USDT": Balance("USDT", self._cash, 0.0, self._cash)
        }
        for sym, pos in self._positions.items():
            base = sym.split("/")[0]
            balances[base] = Balance(base, pos["amount"], 0.0, pos["amount"])
        return balances

    async def create_order(self, symbol: str, side: str, amount: float, price: Optional[float] = None) -> Order:
        ticker = await self.get_ticker(symbol)
        exec_price = price or ticker.price
        cost = exec_price * amount

        if side == "buy":
            if cost > self._cash:
                raise ValueError(f"Insufficient balance: need {cost:.2f} USDT, have {self._cash:.2f}")
            self._cash -= cost
            base = symbol.split("/")[0]
            if base not in self._positions:
                self._positions[base] = {"amount": 0.0, "avg_price": 0.0, "symbol": symbol}
            pos = self._positions[base]
            total_cost = pos["avg_price"] * pos["amount"] + cost
            pos["amount"] += amount
            pos["avg_price"] = total_cost / pos["amount"] if pos["amount"] > 0 else 0
        else:  # sell
            base = symbol.split("/")[0]
            pos = self._positions.get(base)
            if not pos or pos["amount"] < amount:
                raise ValueError(f"Insufficient position for {symbol}")
            self._cash += cost
            pos["amount"] -= amount
            if pos["amount"] <= 1e-8:
                del self._positions[base]

        order = Order(
            id=f"DEMO-{self._order_counter:06d}",
            symbol=symbol,
            side=side,
            type="market",
            price=exec_price,
            amount=amount,
            cost=cost,
            status="closed",
        )
        self._order_counter += 1
        self._orders.append(order)
        return order

    def get_portfolio_value(self, prices: Dict[str, float]) -> float:
        total = self._cash
        for base, pos in self._positions.items():
            sym = pos["symbol"]
            price = prices.get(sym, pos["avg_price"])
            total += pos["amount"] * price
        return total

    def get_portfolio_state(self) -> dict:
        return {
            "cash_usdt": self._cash,
            "initial_cash": self._initial_cash,
            "positions": dict(self._positions),
            "total_orders": len(self._orders),
        }

    def reset(self):
        self._cash = self._initial_cash
        self._positions.clear()
        self._orders.clear()
        self._order_counter = 1
