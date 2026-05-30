import json
from typing import Optional
import aiohttp
import eth_account
from eth_account.signers.local import LocalAccount
from app.core.config import settings

MAINNET_URL = "https://api.hyperliquid.xyz"
TESTNET_URL = "https://api.hyperliquid-testnet.xyz"


class HyperliquidClient:
    def __init__(self):
        self.base_url = TESTNET_URL if settings.HYPERLIQUID_TESTNET else MAINNET_URL
        self.account: Optional[LocalAccount] = None
        if settings.HYPERLIQUID_PRIVATE_KEY:
            self.account = eth_account.Account.from_key(settings.HYPERLIQUID_PRIVATE_KEY)
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if not self.session:
            self.session = aiohttp.ClientSession()
        return self.session

    async def _post(self, endpoint: str, payload: dict) -> dict:
        session = await self._get_session()
        async with session.post(f"{self.base_url}/{endpoint}", json=payload) as resp:
            return await resp.json()

    async def get_all_mids(self) -> dict:
        try:
            session = await self._get_session()
            async with session.post(
                f"{self.base_url}/info",
                json={"type": "allMids"},
            ) as resp:
                data = await resp.json()
                return data
        except Exception as e:
            raise Exception(f"Hyperliquid mids error: {e}")

    async def get_ticker(self, symbol: str) -> dict:
        try:
            mids = await self.get_all_mids()
            price = float(mids.get(symbol, 0))
            return {
                "symbol": symbol,
                "price": price,
                "bid": price * 0.9999,
                "ask": price * 1.0001,
            }
        except Exception as e:
            raise Exception(f"Hyperliquid ticker error: {e}")

    async def get_ohlcv(self, symbol: str, interval: str = "1h", limit: int = 200) -> list:
        try:
            import time
            end_time = int(time.time() * 1000)
            interval_map = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}
            minutes = interval_map.get(interval, 60)
            start_time = end_time - limit * minutes * 60 * 1000

            payload = {
                "type": "candleSnapshot",
                "req": {
                    "coin": symbol,
                    "interval": interval,
                    "startTime": start_time,
                    "endTime": end_time,
                },
            }
            data = await self._post("info", payload)
            return [
                {
                    "timestamp": c["t"],
                    "open": float(c["o"]),
                    "high": float(c["h"]),
                    "low": float(c["l"]),
                    "close": float(c["c"]),
                    "volume": float(c["v"]),
                }
                for c in (data or [])
            ]
        except Exception as e:
            raise Exception(f"Hyperliquid OHLCV error: {e}")

    async def get_user_state(self) -> dict:
        if not self.account:
            raise Exception("No wallet configured for Hyperliquid")
        try:
            payload = {"type": "clearinghouseState", "user": self.account.address}
            return await self._post("info", payload)
        except Exception as e:
            raise Exception(f"Hyperliquid state error: {e}")

    async def place_order(
        self,
        symbol: str,
        is_buy: bool,
        size: float,
        price: float,
        reduce_only: bool = False,
        leverage: int = 3,
    ) -> dict:
        if not self.account:
            raise Exception("No wallet configured for Hyperliquid")
        try:
            import time

            timestamp = int(time.time() * 1000)
            order = {
                "a": symbol,
                "b": is_buy,
                "p": str(price),
                "s": str(size),
                "r": reduce_only,
                "t": {"limit": {"tif": "Gtc"}},
            }
            action = {"type": "order", "orders": [order], "grouping": "na"}
            payload = {
                "action": action,
                "nonce": timestamp,
                "signature": self._sign_action(action, timestamp),
            }
            result = await self._post("exchange", payload)
            return result
        except Exception as e:
            raise Exception(f"Hyperliquid order error: {e}")

    def _sign_action(self, action: dict, timestamp: int) -> dict:
        from eth_account.messages import encode_defunct
        import hashlib

        message = json.dumps({"action": action, "nonce": timestamp}, separators=(",", ":"))
        msg_hash = hashlib.sha256(message.encode()).hexdigest()
        signed = self.account.sign_message(encode_defunct(hexstr=msg_hash))
        return {
            "r": hex(signed.r),
            "s": hex(signed.s),
            "v": signed.v,
        }

    async def close(self):
        if self.session:
            await self.session.close()
