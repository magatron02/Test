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
from .exchanges import create_exchange
from .agent.ai_trader import AITrader
from .agent.training_loop import TrainingLoop
from .agent.hourly_trainer import HourlyTrainer
from .api.routes import router, set_trader, set_training_loop, set_hourly_trainer
from .api.websocket import broadcast, websocket_endpoint

logging.basicConfig(
    level=getattr(logging, settings.get("app", "log_level", default="INFO")),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

WEB_DIR = (Path(_sys._MEIPASS) / "src" / "web") if getattr(_sys, 'frozen', False) else (Path(__file__).parent / "web")

app = FastAPI(title=settings.app_name, version="1.0.0")

# CORS is restricted to the localhost origins this app is served from.
# The frontend uses same-origin relative URLs, so this does NOT affect the
# dashboard (even when reached via a LAN IP — that's still same-origin).
# A wildcard here would let any website the user visits read /api/auth/token
# cross-origin and then drive authenticated mutations (settings, live trades).
_port = settings.app_port
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        f"http://localhost:{_port}",
        f"http://127.0.0.1:{_port}",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

if (WEB_DIR / "static").exists():
    app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")


@app.get("/", response_class=FileResponse)
async def index():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/terminal", response_class=FileResponse)
async def terminal():
    """New minimal trading terminal UI (JetBrains Mono + Noto Sans Thai Looped)."""
    return FileResponse(WEB_DIR / "terminal.html")


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket_endpoint(websocket)


_trader: AITrader = None
_trader_task = None
_training_loop_inst: TrainingLoop = None
_hourly_trainer_inst: HourlyTrainer = None


async def _snapshot_loop():
    """Save portfolio snapshot to DB every 5 minutes."""
    from .core.database import Portfolio, SessionLocal
    await asyncio.sleep(30)  # wait for trader to initialize
    while True:
        try:
            if _trader:
                balances = await _trader._exchange.get_balance()
                analyses = _trader.analyses
                cash_bal = balances.get(_trader._exchange.quote_currency)
                cash = float(cash_bal.free) if cash_bal else 0.0
                total = cash
                positions = {}
                for sym, analysis in analyses.items():
                    base = sym.split("/")[0]
                    bal = balances.get(base)
                    if bal and bal.total > 0:
                        val = bal.total * analysis.price
                        total += val
                        positions[sym] = {"amount": bal.total, "price": analysis.price, "value": val}

                db = SessionLocal()
                try:
                    snap = Portfolio(
                        mode=settings.trading_mode,
                        exchange=_trader._exchange.name,
                        total_value_usdt=total,
                        cash_usdt=cash,
                        positions=positions,
                    )
                    db.add(snap)
                    db.commit()
                except Exception:
                    db.rollback()
                finally:
                    db.close()
        except Exception as e:
            logger.debug(f"Snapshot error: {e}")
        await asyncio.sleep(300)  # every 5 minutes

@app.on_event("startup")
async def startup():
    global _trader, _trader_task, _training_loop_inst, _hourly_trainer_inst

    init_db()
    logger.info(f"Database initialized")

    exchange, ex_name = create_exchange()
    # If live was requested but unconfigured, create_exchange falls back to demo.
    # Keep the in-memory mode honest so the dashboard badge matches reality.
    if settings.trading_mode == "live" and getattr(exchange, "is_demo", False):
        settings.set("demo", "trading", "mode")
        logger.warning("Live mode requested but no exchange configured — running DEMO. "
                       "Add API keys in Settings, then switch to Live Mode.")
    _trader = AITrader(exchange)
    _trader.set_broadcast(broadcast)

    _training_loop_inst = TrainingLoop(_trader, broadcast_fn=broadcast)
    _hourly_trainer_inst = HourlyTrainer(_trader._trainer, broadcast_fn=broadcast)

    set_trader(_trader)
    set_training_loop(_training_loop_inst)
    set_hourly_trainer(_hourly_trainer_inst)

    _trader_task = asyncio.create_task(_trader.start())
    asyncio.create_task(_snapshot_loop())
    _hourly_trainer_inst.start()
    logger.info(f"AI Trader started in {settings.trading_mode} mode (exchange={ex_name}) with model={settings.ai_model}")

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
║          Aiterra v1.0.0 - Starting...    ║
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
