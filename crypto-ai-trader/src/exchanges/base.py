from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple


@dataclass
class Ticker:
    symbol: str
    price: float
    change_24h: float
    volume_24h: float
    high_24h: float
    low_24h: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class OHLCV:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Balance:
    currency: str
    free: float
    used: float
    total: float


@dataclass
class Order:
    id: str
    symbol: str
    side: str          # buy | sell
    type: str          # market | limit
    price: float
    amount: float
    cost: float
    status: str        # open | closed | cancelled
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class OrderBook:
    symbol: str
    bids: List[Tuple[float, float]]   # [(price, qty), ...] descending
    asks: List[Tuple[float, float]]   # [(price, qty), ...] ascending
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class BaseExchange(ABC):
    name: str = "base"
    is_demo: bool = False
    # Quote/settlement currency the account holds cash in. Global exchanges
    # settle in USDT; Thai exchanges (Bitkub, Binance TH) settle in THB.
    # Readers should use this instead of a global setting so cash lookups stay
    # correct across a demo↔live or USDT↔THB hot-swap.
    quote_currency: str = "USDT"

    @abstractmethod
    async def get_ticker(self, symbol: str) -> Ticker:
        pass

    @abstractmethod
    async def get_ohlcv(self, symbol: str, timeframe: str = "5m", limit: int = 100) -> List[OHLCV]:
        pass

    @abstractmethod
    async def get_balance(self) -> Dict[str, Balance]:
        pass

    @abstractmethod
    async def create_order(self, symbol: str, side: str, amount: float, price: Optional[float] = None) -> Order:
        pass

    async def get_order_book(self, symbol: str, limit: int = 20) -> Optional[OrderBook]:
        """Return top-N bids/asks. Returns None if unsupported by the exchange."""
        return None

    async def get_multiple_tickers(self, symbols: List[str]) -> Dict[str, Ticker]:
        result = {}
        for sym in symbols:
            try:
                result[sym] = await self.get_ticker(sym)
            except Exception:
                pass
        return result

    async def get_orderbook_top(self, symbol: str) -> Optional["OrderbookTop"]:
        """Return best bid/ask. Default: last price ± 0.05% spread."""
        try:
            ticker = await self.get_ticker(symbol)
            s = ticker.price * 0.0005
            return OrderbookTop(symbol, ticker.price - s, ticker.price + s,
                                round(s / ticker.price * 200, 6))
        except Exception:
            return None

    async def get_funding_rate(self, symbol: str) -> Optional[dict]:
        """Return perpetual funding rate dict. None if exchange doesn't support it."""
        return None


@dataclass
class OrderbookTop:
    symbol:     str
    bid:        float
    ask:        float
    spread_pct: float   # (ask-bid)/bid × 100
