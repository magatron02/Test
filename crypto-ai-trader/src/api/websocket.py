import asyncio
import json
import logging
from collections import deque
from datetime import datetime, timezone
from typing import List, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
_connections: Set[WebSocket] = set()

# In-memory notification history (survives client reloads, not restarts)
_notif_log: deque = deque(maxlen=100)
_notif_seq: int = 0


def _make_notification(event: str, data: dict) -> Optional[dict]:
    """Map a broadcast event into a user-facing notification entry.
    Returns None for high-frequency/noisy events that shouldn't be logged."""
    d = data or {}
    if event == "trade_executed":
        return {
            "type": "success" if d.get("side") == "BUY" else "danger",
            "icon": "🟢" if d.get("side") == "BUY" else "🔴",
            "title": f"{d.get('side','')} {d.get('symbol','')}".strip(),
            "body": f"@ ${d.get('price', 0):,.4f} · {d.get('strategy','')}",
        }
    if event == "trade_closed":
        win = (d.get("pnl", 0) or 0) >= 0
        pct = d.get("pnl_pct", 0) or 0
        return {
            "type": "success" if win else "warning",
            "icon": "✅" if win else "❌",
            "title": f"Closed {d.get('symbol','')}",
            "body": f"{'+' if pct >= 0 else ''}{pct:.2f}% · {d.get('reason','')}",
        }
    if event == "price_alert":
        arrow = "📈" if d.get("condition") == "above" else "📉"
        cond = "ขึ้นถึง" if d.get("condition") == "above" else "ลงถึง"
        quote = (d.get("symbol", "").split("/")[1] if "/" in d.get("symbol", "") else "")
        return {
            "type": "info",
            "icon": arrow,
            "title": f"แจ้งเตือนราคา {d.get('symbol','')}",
            "body": f"{cond} {d.get('target_price', 0):,.2f} {quote} · ตอนนี้ {d.get('price', 0):,.2f}",
        }
    if event == "hourly_train_done":
        acc = d.get("model_accuracy")
        return {
            "type": "info",
            "icon": "🧠",
            "title": "Hourly Training",
            "body": f"+{d.get('last_samples', 0)} samples · "
                    + (f"acc {acc*100:.1f}%" if acc else "model not ready"),
        }
    if event == "training_completed":
        wr = d.get("win_rate", 0) or 0
        return {
            "type": "success",
            "icon": "🎯",
            "title": "Training Loop Complete",
            "body": f"Win rate {wr*100:.1f}% · {d.get('total_trades', 0)} trades",
        }
    return None


def _record_notification(event: str, data: dict):
    global _notif_seq
    entry = _make_notification(event, data)
    if entry is None:
        return
    _notif_seq += 1
    entry["id"] = _notif_seq
    entry["event"] = event
    entry["ts"] = datetime.now(timezone.utc).isoformat()
    _notif_log.append(entry)


def get_notifications() -> List[dict]:
    """Newest first."""
    return list(reversed(_notif_log))


def clear_notifications():
    _notif_log.clear()


async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    _connections.add(websocket)
    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                # echo ping/pong
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"type": "heartbeat"}))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug(f"WebSocket error: {e}")
    finally:
        _connections.discard(websocket)


async def broadcast(event: str, data: dict):
    _record_notification(event, data)
    if not _connections:
        return
    payload = json.dumps({"event": event, "data": data})
    dead = set()
    for ws in list(_connections):
        try:
            await ws.send_text(payload)
        except Exception:
            dead.add(ws)
    # mutate in place — rebinding (`-=`) would shadow the module global and
    # raise UnboundLocalError on the read above.
    _connections.difference_update(dead)
