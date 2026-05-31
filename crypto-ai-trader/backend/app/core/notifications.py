"""
Push notification service for trade alerts.
Supports: FCM (Firebase Cloud Messaging) for Android, APNs for iOS.
"""
import httpx
from typing import Optional
from app.core.config import settings


class NotificationService:
    def __init__(self):
        self.fcm_url = "https://fcm.googleapis.com/fcm/send"
        self.device_tokens: list[str] = []

    def register_token(self, token: str):
        if token not in self.device_tokens:
            self.device_tokens.append(token)

    def unregister_token(self, token: str):
        self.device_tokens = [t for t in self.device_tokens if t != token]

    async def send_trade_alert(
        self,
        action: str,
        symbol: str,
        price: float,
        confidence: float,
        reasoning: str,
        pnl: Optional[float] = None,
    ):
        title_map = {
            "buy": "BUY Signal",
            "sell": "SELL Signal",
            "long": "LONG Position Opened",
            "short": "SHORT Position Opened",
            "hold": "Market Update",
            "grid": "Grid Started",
        }
        title = title_map.get(action.lower(), "Trade Alert")
        pnl_str = f" | PnL: ${pnl:+.2f}" if pnl is not None else ""
        body = f"{symbol} @ ${price:,.2f} | {confidence*100:.0f}% confidence{pnl_str}"

        await self._send_push(title, body, {
            "action": action,
            "symbol": symbol,
            "price": str(price),
            "reasoning": reasoning[:200],
        })

    async def send_pnl_alert(self, symbol: str, pnl: float, pnl_pct: float):
        emoji = "📈" if pnl > 0 else "📉"
        title = f"{emoji} Position Closed"
        body = f"{symbol}: {'+' if pnl > 0 else ''}{pnl:.2f} USDT ({pnl_pct:+.1f}%)"
        await self._send_push(title, body, {"type": "pnl", "symbol": symbol})

    async def send_risk_alert(self, message: str):
        await self._send_push("Risk Alert", message, {"type": "risk"}, high_priority=True)

    async def send_agent_status(self, is_running: bool, message: str = ""):
        status = "running" if is_running else "stopped"
        title = f"Agent {status.capitalize()}"
        body = message or f"Trading agent is now {status}"
        await self._send_push(title, body, {"type": "agent_status"})

    async def _send_push(
        self,
        title: str,
        body: str,
        data: dict,
        high_priority: bool = False,
    ):
        if not self.device_tokens or not settings.FCM_SERVER_KEY:
            return

        payload = {
            "registration_ids": self.device_tokens,
            "notification": {"title": title, "body": body, "sound": "default"},
            "data": data,
            "priority": "high" if high_priority else "normal",
        }
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    self.fcm_url,
                    json=payload,
                    headers={
                        "Authorization": f"key={settings.FCM_SERVER_KEY}",
                        "Content-Type": "application/json",
                    },
                    timeout=10,
                )
        except Exception as e:
            print(f"[Notification] Failed to send: {e}")


notification_service = NotificationService()
