import asyncio
import logging
import sys
import threading
import webbrowser
from pathlib import Path

import sys as _sys
import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .core.config import settings
from .core.database import init_db
from .exchanges.demo_client import DemoExchange
from .agent.ai_trader import AITrader
from .agent.training_loop import TrainingLoop
from .api.routes import router, set_trader, set_training_loop
from .api.websocket import broadcast, websocket_endpoint

logging.basicConfig(
    level=getattr(logging, settings.get("app", "log_level", default="INFO")),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

WEB_DIR = (Path(_sys._MEIPASS) / "src" / "web") if getattr(_sys, 'frozen', False) else (Path(__file__).parent / "web")

app = FastAPI(title=settings.app_name, version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

if (WEB_DIR / "static").exists():
    app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")


@app.get("/", response_class=FileResponse)
async def index():
    return FileResponse(WEB_DIR / "index.html")


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket_endpoint(websocket)


_trader: AITrader = None
_trader_task = None
_training_loop_inst: TrainingLoop = None


@app.on_event("startup")
async def startup():
    global _trader, _trader_task, _training_loop_inst

    init_db()
    logger.info(f"Database initialized")

    exchange = DemoExchange()
    _trader = AITrader(exchange)
    _trader.set_broadcast(broadcast)

    _training_loop_inst = TrainingLoop(_trader, broadcast_fn=broadcast)

    set_trader(_trader)
    set_training_loop(_training_loop_inst)

    _trader_task = asyncio.create_task(_trader.start())
    logger.info(f"AI Trader started in {settings.trading_mode} mode with model={settings.ai_model}")

    if settings.get("app", "open_browser", default=True):
        def open_browser():
            import time
            time.sleep(1.5)
            webbrowser.open(f"http://localhost:{settings.app_port}")
        threading.Thread(target=open_browser, daemon=True).start()


@app.on_event("shutdown")
async def shutdown():
    if _trader:
        _trader.stop()
    if _trader_task:
        _trader_task.cancel()


def main():
    print(f"""
╔══════════════════════════════════════════╗
║        AI Auto Trader - Starting...      ║
║  Mode: {settings.trading_mode.upper():<10} Model: {settings.ai_model:<12}║
║  Port: {settings.app_port:<10} URL: http://localhost:{settings.app_port} ║
╚══════════════════════════════════════════╝
""")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=settings.app_port,
        reload=False,
        log_level=settings.get("app", "log_level", default="info").lower(),
    )


if __name__ == "__main__":
    main()
