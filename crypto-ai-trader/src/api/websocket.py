import asyncio
import json
import logging
from typing import Set

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
_connections: Set[WebSocket] = set()


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
