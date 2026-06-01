import logging
import aiohttp
from ..core.config import settings

logger = logging.getLogger(__name__)

LINE_TOKEN_URL     = "https://api.line.me/v2/oauth/accessToken"
LINE_BROADCAST_URL = "https://api.line.me/v2/bot/message/broadcast"
LINE_PUSH_URL      = "https://api.line.me/v2/bot/message/push"


async def _get_access_token(channel_id: str, channel_secret: str) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.post(
            LINE_TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": channel_id,
                "client_secret": channel_secret,
            },
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            resp.raise_for_status()
            return (await resp.json())["access_token"]


async def send(message: str):
    channel_id     = settings.get("notifications", "line", "channel_id",     default="")
    channel_secret = settings.get("notifications", "line", "channel_secret", default="")
    if not channel_id or not channel_secret:
        return
    if not settings.get("notifications", "line", "enabled", default=False):
        return
    try:
        token = await _get_access_token(channel_id, channel_secret)
        user_id = settings.get("notifications", "line", "user_id", default="")
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        body = {"messages": [{"type": "text", "text": message}]}
        if user_id:
            body["to"] = user_id
            url = LINE_PUSH_URL
        else:
            url = LINE_BROADCAST_URL
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=body,
                                    timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status not in (200, 201):
                    logger.warning(f"LINE API failed: {resp.status}")
    except Exception as e:
        logger.error(f"LINE Messaging API error: {e}")
