import asyncio
import logging
import math
import random
import time as _time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import aiohttp

from .base import Balance, BaseExchange, OHLCV, Order, Ticker
from ..core.config import settings

logger = logging.getLogger(__name__)

BINANCE_BASE = "https://api.binance.com"

# Realistic seed prices for simulation fallback (USDT and THB pairs)
_SEED_PRICES = {
    "BTC/USDT": 105000.0,
    "ETH/USDT":   3800.0,
    "BNB/USDT":    680.0,
    "SOL/USDT":    175.0,
    "XRP/USDT":      2.30,
    # THB pairs — approximate THB equivalent (1 USD ≈ 34 THB)
    "BTC/THB": 3_570_000.0,
    "ETH/THB":   129_000.0,
    "BNB/THB":    23_000.0,
    "SOL/THB":     5_950.0,
    "XRP/THB":        78.0,
    "USDT/THB":       34.0,
}

# Per-symbol simulated state (price walk)
_sim_state: Dict[str, dict] = {}


def _sim_price(symbol: str) -> float:
    """Brownian-motion price walk per symbol."""
    state = _sim_state.setdefault(symbol, {
        "price": _SEED_PRICES.get(symbol, 100.0),
        "last_t": _time.time(),
    })
    now = _time.time()
    dt = min(now - state["last_t"], 60)
    drift = 0.0001           # slight upward bias
    vol   = 0.0008 * math.sqrt(dt)
    state["price"] *= math.exp(drift * dt + vol * random.gauss(0, 1))
    state["last_t"] = now
    return state["price"]


def _mock_ticker(symbol: str) -> Ticker:
    price = _sim_price(symbol)
    seed = _SEED_PRICES.get(symbol, price)
    return Ticker(
        symbol=symbol,
        price=round(price, 6),
        change_24h=round((price / seed - 1) * 100, 2),
        volume_24h=round(random.uniform(10000, 50000), 2),
        high_24h=round(price * 1.02, 6),
        low_24h=round(price * 0.98, 6),
    )


def _mock_ohlcv(symbol: str, limit: int = 100) -> List[OHLCV]:
    """Generate synthetic OHLCV candles for offline testing."""
    base = _SEED_PRICES.get(symbol, 100.0)
    candles = []
    p = base * random.uniform(0.92, 1.08)
    now = datetime.utcnow()
    for i in range(limit):
        ts = now - timedelta(minutes=(limit - i) * 15)
        o = p
        c = p * math.exp(random.gauss(0.0001, 0.008))
        h = max(o, c) * random.uniform(1.0, 1.005)
        l = min(o, c) * random.uniform(0.995, 1.0)
        v = random.uniform(100, 2000)
        candles.append(OHLCV(ts, round(o,6), round(h,6), round(l,6), round(c,6), round(v,2)))
        p = c
    return candles


class DemoExchange(BaseExchange):
    """Paper trading with real Binance market data."""

    name = "demo"
    is_demo = True

    def __init__(self):
        cfg = settings.get("exchanges", "demo") or {}
        base_currency = settings.get("trading", "base_currency") or "USDT"
        if base_currency == "THB":
            self._cash = float(cfg.get("virtual_balance_thb", 350000.0))
            self._currency = "THB"
        else:
            self._cash = float(cfg.get("virtual_balance_usdt", 10000.0))
            self._currency = "USDT"
        self.quote_currency = self._currency  # sync with base class field
        self._initial_cash = self._cash
        self._positions: Dict[str, dict] = {}  # symbol -> {amount, avg_price}
        self._orders: List[Order] = []
        self._order_counter = 1
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            # ThreadedResolver uses Python socket (system DNS) — avoids aiodns issues on Windows
            connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=10),
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    def _to_usdt_symbol(self, symbol: str):
        """Return (usdt_symbol, thb_rate) for THB pairs so demo can use api.binance.com."""
        if symbol.endswith("/THB"):
            base = symbol.split("/")[0]
            return f"{base}/USDT", 34.0  # approximate THB/USDT; refreshed below
        return symbol, 1.0

    async def _get_thb_rate(self, session) -> float:
        """Fetch USDT/THB rate from Binance (approx 34 THB per USDT)."""
        try:
            async with session.get(
                f"{BINANCE_BASE}/api/v3/ticker/price",
                params={"symbol": "USDTTHB"},
            ) as resp:
                if resp.status == 200:
                    d = await resp.json()
                    return float(d.get("price", 34.0))
        except Exception:
            pass
        return 34.0

    async def get_ticker(self, symbol: str) -> Ticker:
        usdt_sym, _ = self._to_usdt_symbol(symbol)
        ccxt_sym = usdt_sym.replace("/", "")
        session = await self._get_session()
        try:
            # Fetch THB rate if needed
            rate = await self._get_thb_rate(session) if symbol.endswith("/THB") else 1.0
            async with session.get(
                f"{BINANCE_BASE}/api/v3/ticker/24hr",
                params={"symbol": ccxt_sym},
            ) as resp:
                if resp.status != 200:
                    raise ValueError(f"HTTP {resp.status}")
                data = await resp.json()
            if not isinstance(data, dict) or "lastPrice" not in data:
                raise ValueError("unexpected response format")
            return Ticker(
                symbol=symbol,
                price=float(data["lastPrice"]) * rate,
                change_24h=float(data["priceChangePercent"]),
                volume_24h=float(data["volume"]),
                high_24h=float(data["highPrice"]) * rate,
                low_24h=float(data["lowPrice"]) * rate,
            )
        except Exception as e:
            logger.info(f"Binance unreachable ({e}), using simulated price for {symbol}")
            return _mock_ticker(symbol)

    async def get_ohlcv(self, symbol: str, timeframe: str = "5m", limit: int = 100) -> List[OHLCV]:
        usdt_sym, _ = self._to_usdt_symbol(symbol)
        ccxt_sym = usdt_sym.replace("/", "")
        session = await self._get_session()
        try:
            rate = await self._get_thb_rate(session) if symbol.endswith("/THB") else 1.0
            async with session.get(
                f"{BINANCE_BASE}/api/v3/klines",
                params={"symbol": ccxt_sym, "interval": timeframe, "limit": limit},
            ) as resp:
                if resp.status != 200:
                    raise ValueError(f"HTTP {resp.status}")
                data = await resp.json()
            if not isinstance(data, list):
                raise ValueError("unexpected response format")
            return [
                OHLCV(
                    timestamp=datetime.fromtimestamp(row[0] / 1000),
                    open=float(row[1]) * rate,
                    high=float(row[2]) * rate,
                    low=float(row[3]) * rate,
                    close=float(row[4]) * rate,
                    volume=float(row[5]),
                )
                for row in data
            ]
        except Exception as e:
            logger.info(f"Binance unreachable ({e}), using simulated OHLCV for {symbol}")
            return _mock_ohlcv(symbol, limit)

    async def get_balance(self) -> Dict[str, Balance]:
        balances = {
            self._currency: Balance(self._currency, self._cash, 0.0, self._cash)
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
                raise ValueError(f"Insufficient balance: need {cost:.2f} {self._currency}, have {self._cash:.2f}")
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
            "cash_usdt": self._cash,  # may be THB when base_currency=THB
            "initial_cash": self._initial_cash,
            "positions": dict(self._positions),
            "total_orders": len(self._orders),
        }

    def reset(self):
        self._cash = self._initial_cash
        self._positions.clear()
        self._orders.clear()
        self._order_counter = 1
