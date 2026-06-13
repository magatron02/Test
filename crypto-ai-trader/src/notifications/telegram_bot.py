"""Telegram bot — bidirectional command interface for Aiterra (Phase 3).

Uses raw Telegram Bot API long-polling (no external library — just aiohttp
which is already a dependency). Runs as a background asyncio task.

Configure in settings.yml:
  notifications:
    telegram:
      bot_token: "123456:ABC..."
      chat_id: "9876543"          # also used as the allowed chat for commands
      enabled: true
      bot_enabled: true           # set false to disable command bot (keep send-only)

Supported commands:
  /start   — greeting
  /status  — current bot state (mode, regime, open trades)
  /balance — portfolio summary
  /positions — open positions
  /panel   — latest agent panel consensus
  /pause   — pause all new trades (kill switch)
  /resume  — re-enable trading
  /help    — command list
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

import aiohttp

from ..core.config import settings

logger = logging.getLogger(__name__)

_POLL_TIMEOUT = 30   # long-poll timeout seconds
_RETRY_DELAY  = 5    # seconds between retries on error

_COMMANDS = {
    "/start":     "ยินดีต้อนรับสู่ Aiterra! 🤖\nพิมพ์ /help เพื่อดูคำสั่งทั้งหมด",
    "/help": (
        "📋 <b>คำสั่ง Aiterra Bot</b>\n\n"
        "/status — สถานะ bot ปัจจุบัน\n"
        "/balance — ยอดพอร์ต\n"
        "/positions — สถานะ open trades\n"
        "/panel — Agent Panel consensus\n"
        "/pause — หยุดเทรดชั่วคราว\n"
        "/resume — เปิดเทรดอีกครั้ง\n"
        "/help — คำสั่งทั้งหมด"
    ),
}


class TelegramBot:
    """Background bot that polls Telegram for commands and routes them to the trader."""

    def __init__(self, trader=None):
        self._trader = trader
        self._token: str = settings.get("notifications", "telegram", "bot_token", default="")
        self._allowed_chat: str = str(settings.get("notifications", "telegram", "chat_id", default=""))
        self._enabled: bool = bool(
            self._token
            and settings.get("notifications", "telegram", "bot_enabled", default=True)
        )
        self._offset: int = 0
        self._task: Optional[asyncio.Task] = None
        self._running = False

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def start(self):
        if not self._enabled:
            logger.info("TelegramBot: disabled (no token or bot_enabled=false)")
            return
        if self._task and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("TelegramBot: started polling")

    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()

    # ── internals ─────────────────────────────────────────────────────────────

    def _api(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self._token}/{method}"

    async def _send(self, session: aiohttp.ClientSession, chat_id: str, text: str):
        try:
            await session.post(
                self._api("sendMessage"),
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
                timeout=aiohttp.ClientTimeout(total=10),
            )
        except Exception as e:
            logger.warning("TelegramBot: send error — %s", e)

    async def _poll_loop(self):
        async with aiohttp.ClientSession() as session:
            while self._running:
                try:
                    async with session.get(
                        self._api("getUpdates"),
                        params={"offset": self._offset, "timeout": _POLL_TIMEOUT,
                                "allowed_updates": '["message"]'},
                        timeout=aiohttp.ClientTimeout(total=_POLL_TIMEOUT + 5),
                    ) as resp:
                        data = await resp.json()

                    if not data.get("ok"):
                        logger.warning("TelegramBot: getUpdates error — %s", data)
                        await asyncio.sleep(_RETRY_DELAY)
                        continue

                    for update in data.get("result", []):
                        self._offset = update["update_id"] + 1
                        msg = update.get("message", {})
                        text = (msg.get("text") or "").strip()
                        chat_id = str(msg.get("chat", {}).get("id", ""))
                        if not text or not chat_id:
                            continue
                        # Security: only respond to the configured chat
                        if self._allowed_chat and chat_id != self._allowed_chat:
                            logger.debug("TelegramBot: ignoring msg from unknown chat %s", chat_id)
                            continue
                        cmd = text.split("@")[0].split()[0].lower()
                        reply = await self._handle_command(cmd, chat_id)
                        if reply:
                            await self._send(session, chat_id, reply)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.warning("TelegramBot: poll error — %s", e)
                    await asyncio.sleep(_RETRY_DELAY)

    async def _handle_command(self, cmd: str, chat_id: str) -> Optional[str]:
        if cmd in ("/start", "/help"):
            return _COMMANDS[cmd]

        t = self._trader

        if cmd == "/status":
            if not t:
                return "⚠️ Trader not started"
            mode  = settings.trading_mode.upper()
            model = settings.ai_model
            killed = getattr(t, "_killed", False)
            open_n = len(getattr(t, "_open_trades", {}))
            regime_map = getattr(t, "_regimes", {})
            regime_str = ", ".join(f"{s}: {r.regime}" for s, r in list(regime_map.items())[:3]) or "—"
            return (
                f"🤖 <b>Aiterra Status</b>\n"
                f"Mode: {mode} | Model: {model}\n"
                f"Kill switch: {'🔴 ON' if killed else '🟢 OFF'}\n"
                f"Open trades: {open_n}\n"
                f"Regime: {regime_str}"
            )

        if cmd == "/balance":
            if not t:
                return "⚠️ Trader not started"
            try:
                portfolio = await t._get_portfolio_summary()
                total  = portfolio.get("total_usdt",     0)
                avail  = portfolio.get("available_usdt", 0)
                pnl    = portfolio.get("daily_pnl",      0)
                pnl_pct = portfolio.get("daily_pnl_pct", 0)
                sign = "+" if pnl >= 0 else ""
                return (
                    f"💰 <b>Portfolio</b>\n"
                    f"Total: {total:.2f} USDT\n"
                    f"Available: {avail:.2f} USDT\n"
                    f"Daily PnL: {sign}{pnl:.2f} USDT ({sign}{pnl_pct:.2f}%)"
                )
            except Exception as e:
                return f"❌ Balance error: {e}"

        if cmd == "/positions":
            if not t:
                return "⚠️ Trader not started"
            trades = getattr(t, "_open_trades", {})
            if not trades:
                return "📭 No open positions"
            lines = ["📊 <b>Open Positions</b>"]
            for sym, tr in trades.items():
                side  = tr.get("side", "?")
                entry = tr.get("price", 0)
                lines.append(f"  {sym} {side} @ {entry:.4f}")
            return "\n".join(lines)

        if cmd == "/panel":
            if not t:
                return "⚠️ Trader not started"
            panel_map = getattr(t, "_last_panel", {})
            if not panel_map:
                return "🔄 Panel not yet computed — waiting for analysis cycle"
            # pick last non-HOLD
            sym, p = list(panel_map.items())[-1]
            for s, pp in panel_map.items():
                if pp.get("action") not in ("HOLD", "—"):
                    sym, p = s, pp
            action = p.get("action", "—")
            conf   = p.get("confidence", 0)
            veto   = p.get("veto", "")
            votes_str = ""
            for v in p.get("votes", []):
                votes_str += f"\n  {v['agent']:10} {v['vote']} ({v['confidence']:.0%})"
            return (
                f"🧠 <b>Agent Panel — {sym}</b>\n"
                f"Consensus: <b>{action}</b> {conf:.0%}"
                + (f"\n⛔ {veto}" if veto else "")
                + votes_str
            )

        if cmd == "/pause":
            if not t:
                return "⚠️ Trader not started"
            t._killed = True
            logger.warning("TelegramBot: kill switch activated by Telegram command")
            return "🔴 <b>Trading PAUSED</b> — kill switch activated. Use /resume to re-enable."

        if cmd == "/resume":
            if not t:
                return "⚠️ Trader not started"
            t._killed = False
            logger.info("TelegramBot: kill switch deactivated by Telegram command")
            return "🟢 <b>Trading RESUMED</b> — kill switch deactivated."

        return None   # unknown command — no reply


# ── Module-level singleton launcher ──────────────────────────────────────────

_bot_instance: Optional[TelegramBot] = None


def create_bot(trader=None) -> TelegramBot:
    global _bot_instance
    _bot_instance = TelegramBot(trader=trader)
    return _bot_instance
