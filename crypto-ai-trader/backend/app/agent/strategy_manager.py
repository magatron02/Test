import asyncio
from typing import Optional
from app.agent.market_analyzer import calculate_grid_params, compute_indicators
from app.exchanges.binance_client import BinanceClient
from app.exchanges.okx_client import OKXClient


class GridStrategy:
    """Automated grid trading strategy"""

    def __init__(self, exchange_client, symbol: str, config: dict):
        self.client = exchange_client
        self.symbol = symbol
        self.upper = config["upper_price"]
        self.lower = config["lower_price"]
        self.grid_count = config["grid_count"]
        self.investment = config["investment_amount"]
        self.grid_levels = self._calculate_levels()
        self.orders = {}
        self.total_profit = 0.0

    def _calculate_levels(self) -> list:
        step = (self.upper - self.lower) / self.grid_count
        return [self.lower + i * step for i in range(self.grid_count + 1)]

    async def initialize(self):
        """Place initial grid orders"""
        ticker = await self.client.get_ticker(self.symbol)
        current_price = ticker["price"]
        per_grid = self.investment / self.grid_count
        orders_placed = []

        for level in self.grid_levels:
            if level < current_price:
                qty = per_grid / level
                try:
                    order = await self.client.place_spot_order(
                        self.symbol, "buy", qty, level
                    )
                    self.orders[level] = {"type": "buy", "order": order, "qty": qty}
                    orders_placed.append({"side": "buy", "price": level, "qty": qty})
                except Exception as e:
                    orders_placed.append({"side": "buy", "price": level, "error": str(e)})
            else:
                qty = per_grid / level
                try:
                    order = await self.client.place_spot_order(
                        self.symbol, "sell", qty, level
                    )
                    self.orders[level] = {"type": "sell", "order": order, "qty": qty}
                    orders_placed.append({"side": "sell", "price": level, "qty": qty})
                except Exception as e:
                    orders_placed.append({"side": "sell", "price": level, "error": str(e)})

        return orders_placed

    async def check_and_rebalance(self, current_price: float):
        """Check filled orders and place counter orders"""
        rebalanced = []
        grid_spacing = (self.upper - self.lower) / self.grid_count

        for level, order_info in list(self.orders.items()):
            order_id = order_info["order"].get("id")
            if not order_id:
                continue
            try:
                status = await self.client.spot.fetch_order(order_id, self.symbol)
                if status["status"] == "closed":
                    qty = order_info["qty"]
                    if order_info["type"] == "buy":
                        sell_level = level + grid_spacing
                        if sell_level <= self.upper:
                            profit = qty * grid_spacing
                            self.total_profit += profit
                            new_order = await self.client.place_spot_order(
                                self.symbol, "sell", qty, sell_level
                            )
                            self.orders[sell_level] = {"type": "sell", "order": new_order, "qty": qty}
                            rebalanced.append({"action": "placed_sell", "price": sell_level})
                    else:
                        buy_level = level - grid_spacing
                        if buy_level >= self.lower:
                            new_order = await self.client.place_spot_order(
                                self.symbol, "buy", qty, buy_level
                            )
                            self.orders[buy_level] = {"type": "buy", "order": new_order, "qty": qty}
                            rebalanced.append({"action": "placed_buy", "price": buy_level})
                    del self.orders[level]
            except Exception:
                pass

        return rebalanced


class PerpetualStrategy:
    """Perpetual/futures strategy with dynamic position management"""

    def __init__(self, exchange_client, symbol: str, leverage: int = 3):
        self.client = exchange_client
        self.symbol = symbol
        self.leverage = leverage
        self.position = None

    async def check_and_manage(self, indicators: dict, portfolio_value: float) -> dict:
        rsi = indicators.get("rsi", 50)
        trend = indicators.get("trend", "sideways")
        macd_hist = indicators.get("macd_histogram", 0)
        price = indicators.get("price", 0)
        atr = indicators.get("atr", 0)

        signal = None
        if trend == "bullish" and rsi < 65 and macd_hist > 0:
            signal = "long"
        elif trend == "bearish" and rsi > 35 and macd_hist < 0:
            signal = "short"

        if not signal:
            return {"action": "hold"}

        tp_multiplier = 2.0
        sl_multiplier = 1.0
        size = (portfolio_value * 0.03) / (price * self.leverage) if price > 0 else 0

        if signal == "long":
            take_profit = price + atr * tp_multiplier
            stop_loss = price - atr * sl_multiplier
        else:
            take_profit = price - atr * tp_multiplier
            stop_loss = price + atr * sl_multiplier

        return {
            "action": signal,
            "size": round(size, 6),
            "leverage": self.leverage,
            "take_profit": round(take_profit, 4),
            "stop_loss": round(stop_loss, 4),
            "rr_ratio": round(abs(take_profit - price) / abs(stop_loss - price), 2),
        }
