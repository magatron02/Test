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


class DCAStrategy:
    """Dollar-Cost Averaging strategy — buys at fixed intervals and scales in on dips"""

    def __init__(self, exchange_client, symbol: str, config: dict):
        self.client = exchange_client
        self.symbol = symbol
        self.total_amount = config["total_amount"]
        self.interval_hours = config["interval_hours"]
        self.num_orders = config["num_orders"]
        self.min_drop_pct = config["min_drop_pct"]
        self.base_order_size = self.total_amount / self.num_orders

    async def check_and_buy(
        self,
        current_price: float,
        last_buy_price: float,
        portfolio_value: float,
    ) -> dict:
        """
        Decide whether to place a DCA buy.

        Returns a dict with keys:
          action    – "buy" or "skip"
          amount    – USDT amount to spend (0 when skipping)
          reasoning – human-readable explanation
        """
        if current_price <= 0:
            return {"action": "skip", "amount": 0, "reasoning": "Invalid price data"}

        # How far has price dropped from the last purchase?
        if last_buy_price and last_buy_price > 0:
            drop_pct = (last_buy_price - current_price) / last_buy_price * 100
        else:
            drop_pct = 0.0

        # Aggressive multiplier when price has dropped beyond the threshold
        if drop_pct >= self.min_drop_pct:
            # Scale buy size proportionally to how deep the dip is (up to 3x base)
            dip_multiplier = min(1.0 + (drop_pct / self.min_drop_pct), 3.0)
            amount = round(self.base_order_size * dip_multiplier, 2)
            reasoning = (
                f"Price dropped {drop_pct:.2f}% from last buy (${last_buy_price:.4f} → "
                f"${current_price:.4f}), exceeding the {self.min_drop_pct}% threshold. "
                f"Scaling in aggressively with {dip_multiplier:.2f}x the base order size."
            )
            return {"action": "buy", "amount": amount, "reasoning": reasoning}

        # Regular interval buy — only if we still have budget headroom
        max_deployed = self.total_amount
        if portfolio_value >= max_deployed:
            amount = round(self.base_order_size, 2)
            reasoning = (
                f"Scheduled DCA interval purchase of ${amount:.2f} at ${current_price:.4f}. "
                f"Price is within {drop_pct:.2f}% of last buy — no dip multiplier applied."
            )
            return {"action": "buy", "amount": amount, "reasoning": reasoning}

        return {
            "action": "skip",
            "amount": 0,
            "reasoning": (
                f"Total DCA budget of ${self.total_amount:.2f} already deployed. "
                "Skipping this interval."
            ),
        }


class TrendFollowStrategy:
    """Multi-timeframe trend-following strategy using EMA200, RSI, and MACD"""

    def __init__(self, exchange_client, symbol: str, leverage: int = 2):
        self.client = exchange_client
        self.symbol = symbol
        self.leverage = leverage
        self._MIN_CONFIDENCE = 0.6

    async def analyze(self, indicators_1h: dict, indicators_4h: dict) -> dict:
        """
        Cross-timeframe analysis returning a trading signal.

        Returns a dict with keys:
          signal     – "long", "short", or "flat"
          confidence – float 0-1 (signals below 0.6 are suppressed to "flat")
          entry      – suggested entry price (current price)
          tp         – take-profit price
          sl         – stop-loss price
          reasoning  – human-readable explanation
        """
        score = 0.0
        max_score = 0.0
        reasons: list[str] = []

        price = indicators_1h.get("price") or indicators_4h.get("price", 0)
        atr_1h = indicators_1h.get("atr", 0)
        atr_4h = indicators_4h.get("atr", 0)
        atr = atr_4h if atr_4h else atr_1h  # prefer 4 h ATR for wider targets

        # --- EMA 200 bias (both timeframes) ---
        for tf_label, ind in (("1h", indicators_1h), ("4h", indicators_4h)):
            ema200 = ind.get("ema200")
            if ema200 and price:
                max_score += 1.0
                if price > ema200:
                    score += 1.0
                    reasons.append(f"Price above EMA200 on {tf_label} (bullish)")
                else:
                    score -= 1.0
                    reasons.append(f"Price below EMA200 on {tf_label} (bearish)")

        # --- RSI divergence / level ---
        rsi_1h = indicators_1h.get("rsi", 50)
        rsi_4h = indicators_4h.get("rsi", 50)
        max_score += 1.0
        if rsi_1h < 45 and rsi_4h > 50:
            # 1 h oversold while 4 h still bullish → bullish divergence
            score += 1.0
            reasons.append(f"RSI bullish divergence: 1h={rsi_1h:.1f}, 4h={rsi_4h:.1f}")
        elif rsi_1h > 55 and rsi_4h < 50:
            # 1 h overbought while 4 h bearish → bearish divergence
            score -= 1.0
            reasons.append(f"RSI bearish divergence: 1h={rsi_1h:.1f}, 4h={rsi_4h:.1f}")
        else:
            reasons.append(f"RSI neutral: 1h={rsi_1h:.1f}, 4h={rsi_4h:.1f}")

        # --- MACD crossover (both timeframes) ---
        for tf_label, ind in (("1h", indicators_1h), ("4h", indicators_4h)):
            macd_hist = ind.get("macd_histogram", 0)
            macd_prev = ind.get("macd_histogram_prev", 0)
            if macd_hist is not None and macd_prev is not None:
                max_score += 1.0
                if macd_hist > 0 and macd_prev <= 0:
                    score += 1.0
                    reasons.append(f"MACD bullish crossover on {tf_label}")
                elif macd_hist < 0 and macd_prev >= 0:
                    score -= 1.0
                    reasons.append(f"MACD bearish crossover on {tf_label}")
                elif macd_hist > 0:
                    score += 0.5
                    reasons.append(f"MACD positive histogram on {tf_label}")
                elif macd_hist < 0:
                    score -= 0.5
                    reasons.append(f"MACD negative histogram on {tf_label}")

        # Normalise score to [-1, 1] then map to confidence in [0, 1]
        if max_score > 0:
            normalised = score / max_score  # range [-1, 1]
        else:
            normalised = 0.0

        confidence = abs(normalised)
        raw_signal = "long" if normalised > 0 else ("short" if normalised < 0 else "flat")

        if confidence < self._MIN_CONFIDENCE:
            return {
                "signal": "flat",
                "confidence": round(confidence, 3),
                "entry": round(price, 4),
                "tp": None,
                "sl": None,
                "reasoning": (
                    f"Confidence {confidence:.2f} below threshold {self._MIN_CONFIDENCE}. "
                    "No trade. " + " | ".join(reasons)
                ),
            }

        # Calculate TP / SL from ATR; widen targets on higher timeframe
        tp_atr = atr * 2.5 * self.leverage
        sl_atr = atr * 1.2

        if raw_signal == "long":
            tp = round(price + tp_atr, 4) if atr else None
            sl = round(price - sl_atr, 4) if atr else None
        else:
            tp = round(price - tp_atr, 4) if atr else None
            sl = round(price + sl_atr, 4) if atr else None

        return {
            "signal": raw_signal,
            "confidence": round(confidence, 3),
            "entry": round(price, 4),
            "tp": tp,
            "sl": sl,
            "reasoning": " | ".join(reasons),
        }
