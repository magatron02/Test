import logging
import aiohttp
from ..core.config import settings

logger = logging.getLogger(__name__)
LINE_NOTIFY_URL = "https://notify-api.line.me/api/notify"


async def send(message: str):
    token = settings.get("notifications", "line", "token", default="")
    if not token or not settings.get("notifications", "line", "enabled", default=False):
        return
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                LINE_NOTIFY_URL,
                headers={"Authorization": f"Bearer {token}"},
                data={"message": f"\n{message}"},
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"LINE notify failed: {resp.status}")
    except Exception as e:
        logger.error(f"LINE notify error: {e}")
