from typing import Optional
import ccxt.async_support as ccxt
from app.core.config import settings


class OKXClient:
    def __init__(self):
        params = {
            "apiKey": settings.OKX_API_KEY,
            "secret": settings.OKX_SECRET_KEY,
            "password": settings.OKX_PASSPHRASE,
            "enableRateLimit": True,
        }
        self.spot = ccxt.okx({**params, "options": {"defaultType": "spot"}})
        self.futures = ccxt.okx({**params, "options": {"defaultType": "swap"}})

        if settings.OKX_TESTNET:
            self.spot.set_sandbox_mode(True)
            self.futures.set_sandbox_mode(True)

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
            raise Exception(f"OKX ticker error: {e}")

    async def get_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 200) -> list:
        try:
            ohlcv = await self.spot.fetch_ohlcv(symbol, timeframe, limit=limit)
            return [
                {
                    "timestamp": c[0],
                    "open": c[1],
                    "high": c[2],
                    "low": c[3],
                    "close": c[4],
                    "volume": c[5],
                }
                for c in ohlcv
            ]
        except Exception as e:
            raise Exception(f"OKX OHLCV error: {e}")

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
            raise Exception(f"OKX balance error: {e}")

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
            raise Exception(f"OKX spot order error: {e}")

    async def place_perpetual_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        leverage: int = 3,
        price: Optional[float] = None,
    ) -> dict:
        try:
            await self.futures.set_leverage(leverage, symbol)
            order_type = "limit" if price else "market"
            order = await self.futures.create_order(symbol, order_type, side, amount, price)
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
            raise Exception(f"OKX perpetual order error: {e}")

    async def get_positions(self) -> list:
        try:
            positions = await self.futures.fetch_positions()
            return [
                {
                    "symbol": p["symbol"],
                    "side": p["side"],
                    "size": p["contracts"],
                    "entry_price": p["entryPrice"],
                    "mark_price": p["markPrice"],
                    "unrealized_pnl": p["unrealizedPnl"],
                    "leverage": p["leverage"],
                }
                for p in positions
                if p.get("contracts") and p["contracts"] > 0
            ]
        except Exception as e:
            raise Exception(f"OKX positions error: {e}")

    async def close(self):
        await self.spot.close()
        await self.futures.close()
