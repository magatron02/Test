import asyncio
from typing import Optional
import ccxt.async_support as ccxt
from app.core.config import settings


def _has_keys(api_key: str, secret: str) -> bool:
    return bool(api_key and secret and not api_key.startswith("your_"))


class BinanceClient:
    def __init__(self):
        futures_cfg: dict = {"enableRateLimit": True, "options": {"defaultType": "future"}}
        if _has_keys(settings.BINANCE_API_KEY, settings.BINANCE_SECRET_KEY):
            futures_cfg["apiKey"] = settings.BINANCE_API_KEY
            futures_cfg["secret"] = settings.BINANCE_SECRET_KEY
        self.exchange = ccxt.binance(futures_cfg)
        if settings.BINANCE_TESTNET:
            self.exchange.set_sandbox_mode(True)

        # Spot: mainnet, public endpoints work without keys
        spot_cfg: dict = {"enableRateLimit": True}
        if _has_keys(settings.BINANCE_API_KEY, settings.BINANCE_SECRET_KEY):
            spot_cfg["apiKey"] = settings.BINANCE_API_KEY
            spot_cfg["secret"] = settings.BINANCE_SECRET_KEY
        self.spot = ccxt.binance(spot_cfg)

    async def get_ticker(self, symbol: str) -> dict:
        try:
            ticker = await self.spot.fetch_ticker(symbol)
            return {
                "symbol": symbol,
                "price": ticker["last"],
                "bid": ticker["bid"],
                "ask": ticker["ask"],
                "volume": ticker["quoteVolume"],
                "change_24h": ticker["percentage"],
                "high_24h": ticker["high"],
                "low_24h": ticker["low"],
            }
        except Exception as e:
            raise Exception(f"Binance ticker error: {e}")

    async def get_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 200) -> list:
        try:
            ohlcv = await self.spot.fetch_ohlcv(symbol, timeframe, limit=limit)
            return [
                {
                    "timestamp": candle[0],
                    "open": candle[1],
                    "high": candle[2],
                    "low": candle[3],
                    "close": candle[4],
                    "volume": candle[5],
                }
                for candle in ohlcv
            ]
        except Exception as e:
            raise Exception(f"Binance OHLCV error: {e}")

    async def get_orderbook(self, symbol: str, limit: int = 20) -> dict:
        try:
            ob = await self.spot.fetch_order_book(symbol, limit)
            return {
                "bids": ob["bids"][:10],
                "asks": ob["asks"][:10],
                "spread": ob["asks"][0][0] - ob["bids"][0][0] if ob["bids"] and ob["asks"] else 0,
            }
        except Exception as e:
            raise Exception(f"Binance orderbook error: {e}")

    async def get_balance(self) -> dict:
        try:
            balance = await self.spot.fetch_balance()
            return {
                asset: {
                    "free": info["free"],
                    "used": info["used"],
                    "total": info["total"],
                }
                for asset, info in balance["total"].items()
                if info > 0
            }
        except Exception as e:
            raise Exception(f"Binance balance error: {e}")

    async def place_spot_order(
        self, symbol: str, side: str, amount: float, price: Optional[float] = None
    ) -> dict:
        try:
            order_type = "limit" if price else "market"
            order = await self.spot.create_order(symbol, order_type, side, amount, price)
            return {
                "id": order["id"],
                "symbol": order["symbol"],
                "side": order["side"],
                "price": order["price"] or order["average"],
                "amount": order["amount"],
                "filled": order["filled"],
                "status": order["status"],
            }
        except Exception as e:
            raise Exception(f"Binance spot order error: {e}")

    async def place_futures_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        leverage: int = 3,
        price: Optional[float] = None,
        reduce_only: bool = False,
    ) -> dict:
        try:
            await self.exchange.set_leverage(leverage, symbol)
            params = {"reduceOnly": reduce_only}
            order_type = "limit" if price else "market"
            order = await self.exchange.create_order(
                symbol, order_type, side, amount, price, params
            )
            return {
                "id": order["id"],
                "symbol": order["symbol"],
                "side": order["side"],
                "price": order["price"] or order["average"],
                "amount": order["amount"],
                "filled": order["filled"],
                "status": order["status"],
                "leverage": leverage,
            }
        except Exception as e:
            raise Exception(f"Binance futures order error: {e}")

    async def get_positions(self) -> list:
        try:
            positions = await self.exchange.fetch_positions()
            return [
                {
                    "symbol": p["symbol"],
                    "side": p["side"],
                    "size": p["contracts"],
                    "entry_price": p["entryPrice"],
                    "mark_price": p["markPrice"],
                    "unrealized_pnl": p["unrealizedPnl"],
                    "leverage": p["leverage"],
                    "margin": p["initialMargin"],
                }
                for p in positions
                if p["contracts"] and p["contracts"] > 0
            ]
        except Exception as e:
            raise Exception(f"Binance positions error: {e}")

    async def cancel_order(self, order_id: str, symbol: str) -> dict:
        try:
            return await self.spot.cancel_order(order_id, symbol)
        except Exception as e:
            raise Exception(f"Binance cancel order error: {e}")

    async def close(self):
        await self.exchange.close()
        await self.spot.close()
