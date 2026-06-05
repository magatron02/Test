"""Price alert monitor.

Polls the exchange for the symbols that currently have active price alerts and
fires a notification (dashboard + LINE/Telegram) when a target is crossed.

Runs on its own lightweight loop independent of the analysis cycle, so alerts
land in near-real-time even when the AI is only analysing every few minutes.
"""
import asyncio
import logging
from datetime import datetime, timezone

from ..core.database import PriceAlert, SessionLocal
from ..notifications import line_notify, telegram_notify

logger = logging.getLogger(__name__)


class AlertMonitor:
    def __init__(self, exchange, broadcast_fn=None, interval: int = 60):
        self._exchange = exchange
        self._broadcast = broadcast_fn
        self._interval = interval
        self._running = False

    async def start(self):
        self._running = True
        await asyncio.sleep(15)  # let the exchange client warm up
        logger.info("Price alert monitor started (every %ds)", self._interval)
        while self._running:
            try:
                await self.check_once()
            except Exception as e:
                logger.debug("Alert check error: %s", e)
            await asyncio.sleep(self._interval)

    def stop(self):
        self._running = False

    async def check_once(self):
        """Fetch fresh prices for symbols with active alerts and fire matches."""
        db = SessionLocal()
        try:
            alerts = db.query(PriceAlert).filter(PriceAlert.active == True).all()  # noqa: E712
            if not alerts:
                return

            # Fetch each distinct symbol's price once.
            symbols = {a.symbol for a in alerts}
            prices: dict[str, float] = {}
            for sym in symbols:
                try:
                    ticker = await self._exchange.get_ticker(sym)
                    prices[sym] = float(ticker.price)
                except Exception as e:
                    logger.debug("Alert price fetch failed for %s: %s", sym, e)

            for a in alerts:
                price = prices.get(a.symbol)
                if price is None:
                    continue
                crossed = (
                    (a.condition == "above" and price >= a.target_price) or
                    (a.condition == "below" and price <= a.target_price)
                )
                if not crossed:
                    continue

                a.triggered_at = datetime.now(timezone.utc)
                if not a.repeat:
                    a.active = False  # one-shot
                db.commit()
                await self._fire(a, price)
        finally:
            db.close()

    async def _fire(self, alert: PriceAlert, price: float):
        arrow = "📈" if alert.condition == "above" else "📉"
        cond_th = "ขึ้นถึง" if alert.condition == "above" else "ลงถึง"
        quote = alert.symbol.split("/")[1] if "/" in alert.symbol else ""
        msg = f"{arrow} แจ้งเตือนราคา: {alert.symbol} {cond_th} {alert.target_price:,.2f} {quote} (ตอนนี้ {price:,.2f})"
        if alert.note:
            msg += f"\n📝 {alert.note}"

        # Dashboard toast / notification log
        if self._broadcast:
            try:
                await self._broadcast("price_alert", {
                    "id": alert.id,
                    "symbol": alert.symbol,
                    "condition": alert.condition,
                    "target_price": alert.target_price,
                    "price": price,
                    "note": alert.note or "",
                })
            except Exception:
                pass

        # External notifications (no-op if not configured)
        try:
            await line_notify.send(msg)
            await telegram_notify.send(msg)
        except Exception:
            pass

        logger.info("Price alert fired: %s %s %.2f (price=%.2f)",
                    alert.symbol, alert.condition, alert.target_price, price)
