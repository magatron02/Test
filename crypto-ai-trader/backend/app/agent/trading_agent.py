import json
import asyncio
from typing import Optional
import anthropic
from app.core.config import settings
from app.agent.market_analyzer import compute_indicators, calculate_grid_params, calculate_position_size
from app.exchanges.binance_client import BinanceClient
from app.exchanges.okx_client import OKXClient
from app.exchanges.hyperliquid_client import HyperliquidClient
from app.exchanges.demo_client import DemoClient

WATCHLIST = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "AVAX/USDT"]
HL_WATCHLIST = ["BTC", "ETH", "SOL"]


def _make_client(real_client, exchange_name: str):
    """Return real client if exchange is reachable, otherwise demo client."""
    return real_client


class TradingAgent:
    def __init__(self):
        self.client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.binance = BinanceClient()
        self.okx = OKXClient()
        self.hyperliquid = HyperliquidClient()
        self.demo = DemoClient("demo")
        self.is_running = False
        self.paper_balance = {"USDT": 10000.0}
        self.paper_positions = []
        self.use_demo = settings.USE_DEMO_MODE

    def _client_for(self, exchange: str):
        if self.use_demo:
            return self.demo
        if exchange == "binance":
            return self.binance
        if exchange == "okx":
            return self.okx
        return self.demo

    async def analyze_market(self, symbol: str, exchange: str = "binance") -> dict:
        try:
            client = self._client_for(exchange)
            if not self.use_demo and exchange == "hyperliquid":
                hl_symbol = symbol.split("/")[0]
                ohlcv_1h = await self.hyperliquid.get_ohlcv(hl_symbol, "1h", 200)
                ohlcv_4h = await self.hyperliquid.get_ohlcv(hl_symbol, "4h", 100)
                ticker = await self.hyperliquid.get_ticker(hl_symbol)
                orderbook = {"bids": [], "asks": [], "spread": 0}
            else:
                ohlcv_1h = await client.get_ohlcv(symbol, "1h", 200)
                ohlcv_4h = await client.get_ohlcv(symbol, "4h", 100)
                ticker = await client.get_ticker(symbol)
                orderbook = await client.get_orderbook(symbol) if hasattr(client, "get_orderbook") else {"bids": [], "asks": [], "spread": 0}

            indicators_1h = compute_indicators(ohlcv_1h)
            indicators_4h = compute_indicators(ohlcv_4h)

            return {
                "symbol": symbol,
                "exchange": exchange,
                "ticker": ticker,
                "indicators_1h": indicators_1h,
                "indicators_4h": indicators_4h,
                "orderbook_spread": orderbook.get("spread", 0),
            }
        except Exception as e:
            return {"symbol": symbol, "error": str(e)}

    async def get_ai_decision(self, market_data: dict, portfolio_value: float, risk_level: str = "medium") -> dict:
        risk_map = {"low": 0.01, "medium": 0.02, "high": 0.04}
        risk_pct = risk_map.get(risk_level, 0.02)

        prompt = f"""You are an expert crypto trader. Analyze this market data and decide whether to trade.

Symbol: {market_data['symbol']}
Exchange: {market_data['exchange']}

Current Price: {market_data.get('ticker', {}).get('price', 'N/A')}
24h Change: {market_data.get('ticker', {}).get('change_24h', 'N/A')}%

1H Indicators:
{json.dumps(market_data.get('indicators_1h', {}), indent=2)}

4H Indicators:
{json.dumps(market_data.get('indicators_4h', {}), indent=2)}

Portfolio Value: ${portfolio_value:.2f}
Risk Level: {risk_level} ({risk_pct*100:.0f}% risk per trade)

Respond with a JSON object ONLY (no markdown, no explanation outside JSON):
{{
  "action": "buy" | "sell" | "short" | "cover" | "grid" | "hold",
  "strategy": "spot" | "futures" | "perpetual" | "grid",
  "confidence": 0.0-1.0,
  "entry_price": number,
  "take_profit": number,
  "stop_loss": number,
  "leverage": 1-10,
  "position_size_pct": 0.01-0.10,
  "reasoning": "brief explanation",
  "key_signals": ["signal1", "signal2"],
  "risk_reward_ratio": number
}}

Rules:
- Only trade when confidence > 0.65
- For "hold", still provide entry_price, take_profit, stop_loss as 0
- Respect risk management: stop_loss must always be set
- Grid strategy: action must be "grid"
- Consider trend alignment across timeframes
"""

        try:
            response = await self.client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            decision = json.loads(text)
            decision["symbol"] = market_data["symbol"]
            decision["exchange"] = market_data["exchange"]
            return decision
        except Exception as e:
            return {
                "action": "hold",
                "strategy": "spot",
                "confidence": 0,
                "reasoning": f"AI analysis failed: {e}",
                "symbol": market_data.get("symbol", ""),
                "exchange": market_data.get("exchange", ""),
            }

    async def execute_decision(
        self,
        decision: dict,
        portfolio_value: float,
        use_paper: bool = True,
    ) -> dict:
        if decision["action"] == "hold" or decision.get("confidence", 0) < 0.65:
            return {"status": "skipped", "reason": "hold or low confidence"}

        symbol = decision["symbol"]
        exchange = decision["exchange"]
        action = decision["action"]
        strategy = decision["strategy"]
        entry_price = decision.get("entry_price", 0)
        stop_loss = decision.get("stop_loss", 0)
        position_size_pct = decision.get("position_size_pct", 0.02)
        leverage = min(decision.get("leverage", 1), settings.MAX_LEVERAGE)

        if entry_price and stop_loss:
            pos = calculate_position_size(
                portfolio_value,
                0.02,
                entry_price,
                stop_loss,
                position_size_pct,
            )
            size = pos["size"]
        else:
            size = (portfolio_value * position_size_pct) / (entry_price or 1)

        if use_paper:
            return await self._execute_paper_trade(decision, size, entry_price)

        try:
            if exchange == "binance":
                if strategy == "spot":
                    side = "buy" if action == "buy" else "sell"
                    result = await self.binance.place_spot_order(symbol, side, size)
                elif strategy in ("futures", "perpetual"):
                    side = "buy" if action in ("buy", "long") else "sell"
                    result = await self.binance.place_futures_order(
                        symbol, side, size, leverage
                    )
                else:
                    result = {"status": "grid_setup_required"}
            elif exchange == "okx":
                if strategy == "spot":
                    side = "buy" if action == "buy" else "sell"
                    result = await self.okx.place_spot_order(symbol, side, size)
                else:
                    side = "buy" if action in ("buy", "long") else "sell"
                    result = await self.okx.place_perpetual_order(symbol, side, size, leverage)
            elif exchange == "hyperliquid":
                hl_symbol = symbol.split("/")[0]
                is_buy = action in ("buy", "long")
                result = await self.hyperliquid.place_order(
                    hl_symbol, is_buy, size, entry_price, leverage=leverage
                )
            else:
                result = {"status": "unknown_exchange"}

            return {
                "status": "executed",
                "exchange": exchange,
                "symbol": symbol,
                "action": action,
                "size": size,
                "price": entry_price,
                "order": result,
                "reasoning": decision.get("reasoning", ""),
                "confidence": decision.get("confidence", 0),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _execute_paper_trade(self, decision: dict, size: float, price: float) -> dict:
        action = decision["action"]
        symbol = decision["symbol"]
        cost = size * price

        if action in ("buy", "long"):
            if self.paper_balance.get("USDT", 0) >= cost:
                self.paper_balance["USDT"] -= cost
                asset = symbol.split("/")[0]
                self.paper_balance[asset] = self.paper_balance.get(asset, 0) + size
                self.paper_positions.append({
                    "symbol": symbol,
                    "side": action,
                    "size": size,
                    "entry_price": price,
                    "take_profit": decision.get("take_profit"),
                    "stop_loss": decision.get("stop_loss"),
                    "leverage": decision.get("leverage", 1),
                    "strategy": decision.get("strategy"),
                })
                return {
                    "status": "paper_executed",
                    "action": action,
                    "symbol": symbol,
                    "size": size,
                    "price": price,
                    "cost": cost,
                    "reasoning": decision.get("reasoning", ""),
                }
        return {"status": "paper_skipped", "reason": "insufficient balance or sell without position"}

    async def run_cycle(
        self,
        watchlist: list,
        exchanges: list,
        portfolio_value: float,
        risk_level: str = "medium",
        use_paper: bool = True,
    ) -> list:
        results = []
        tasks = []

        for symbol in watchlist:
            for exchange in exchanges:
                tasks.append(self.analyze_market(symbol, exchange))

        market_data_list = await asyncio.gather(*tasks, return_exceptions=True)

        for market_data in market_data_list:
            if isinstance(market_data, Exception) or "error" in market_data:
                continue
            decision = await self.get_ai_decision(market_data, portfolio_value, risk_level)
            result = await self.execute_decision(decision, portfolio_value, use_paper)
            results.append({
                "market_data": market_data,
                "decision": decision,
                "execution": result,
            })

        return results

    async def close(self):
        await self.binance.close()
        await self.okx.close()
        await self.hyperliquid.close()
