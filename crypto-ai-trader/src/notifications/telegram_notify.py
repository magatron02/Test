import logging
import aiohttp
from ..core.config import settings

logger = logging.getLogger(__name__)


async def send(message: str):
    token = settings.get("notifications", "telegram", "bot_token", default="")
    chat_id = settings.get("notifications", "telegram", "chat_id", default="")
    enabled = settings.get("notifications", "telegram", "enabled", default=False)

    if not token or not chat_id or not enabled:
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"}) as resp:
                if resp.status != 200:
                    logger.warning(f"Telegram notify failed: {resp.status}")
    except Exception as e:
        logger.error(f"Telegram notify error: {e}")


async def send_trade(action: str, symbol: str, price: float, pnl_pct: float = None):
    emoji = "🟢" if action == "BUY" else ("🔴" if action == "SELL" else "⚪")
    msg = f"{emoji} <b>{action} {symbol}</b>\nPrice: {price:.4f} USDT"
    if pnl_pct is not None:
        sign = "+" if pnl_pct >= 0 else ""
        msg += f"\nPnL: {sign}{pnl_pct:.2f}%"
    await send(msg)
