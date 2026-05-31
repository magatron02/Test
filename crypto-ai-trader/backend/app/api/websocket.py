import asyncio
import json
from fastapi import WebSocket, WebSocketDisconnect
from typing import Set
from app.agent.trading_agent import TradingAgent

active_connections: Set[WebSocket] = set()


async def websocket_endpoint(websocket: WebSocket, agent: TradingAgent):
    await websocket.accept()
    active_connections.add(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            cmd = msg.get("type")

            if cmd == "subscribe_prices":
                symbols = msg.get("symbols", ["BTC/USDT", "ETH/USDT"])
                asyncio.create_task(stream_prices(websocket, agent, symbols))

            elif cmd == "subscribe_agent":
                asyncio.create_task(stream_agent_status(websocket, agent))

            elif cmd == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

    except WebSocketDisconnect:
        active_connections.discard(websocket)
    except Exception:
        active_connections.discard(websocket)


async def stream_prices(websocket: WebSocket, agent: TradingAgent, symbols: list):
    while websocket in active_connections:
        try:
            prices = {}
            for symbol in symbols:
                try:
                    ticker = await agent.binance.get_ticker(symbol)
                    prices[symbol] = {
                        "price": ticker["price"],
                        "change_24h": ticker["change_24h"],
                        "volume": ticker["volume"],
                    }
                except Exception:
                    pass
            await websocket.send_text(json.dumps({"type": "prices", "data": prices}))
        except Exception:
            break
        await asyncio.sleep(3)


async def stream_agent_status(websocket: WebSocket, agent: TradingAgent):
    while websocket in active_connections:
        try:
            status = {
                "type": "agent_status",
                "data": {
                    "is_running": agent.is_running,
                    "paper_balance": agent.paper_balance,
                    "open_positions": len(agent.paper_positions),
                    "positions": agent.paper_positions,
                },
            }
            await websocket.send_text(json.dumps(status))
        except Exception:
            break
        await asyncio.sleep(5)


async def broadcast(message: dict):
    dead = set()
    for ws in active_connections:
        try:
            await ws.send_text(json.dumps(message))
        except Exception:
            dead.add(ws)
    active_connections -= dead
