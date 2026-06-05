import asyncio
import logging
import sys
import threading
import webbrowser
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

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
from .agent.alert_monitor import AlertMonitor
from .api.routes import router, set_trader, set_training_loop, set_hourly_trainer
from .api.websocket import broadcast, websocket_endpoint

logging.basicConfig(
    level=getattr(logging, settings.get("app", "log_level", default="INFO")),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

WEB_DIR = (Path(_sys._MEIPASS) / "src" / "web") if getattr(_sys, 'frozen', False) else (Path(__file__).parent / "web")

app = FastAPI(title=settings.app_name, version="2.0.0")
APP_VERSION = "2.0.0"
APP_NAME    = "Aiterra"
AI_NAME     = "Lunai"
AI_VERSION  = "2.0.0"

# Attach slowapi rate-limiter state so @limiter.limit decorators work.
try:
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from .api.routes import _limiter as _route_limiter
    if _route_limiter:
        app.state.limiter = _route_limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
except ImportError:
    pass  # slowapi optional — graceful degradation if not installed
except Exception:
    logger.warning("slowapi rate-limiter setup failed; running without rate limits", exc_info=True)

app.add_middleware(
    CORSMiddleware,
    # Restrict to localhost only — this is a single-user local app.
    # If you expose over a LAN, also add your LAN address here.
    allow_origins=[
        f"http://localhost:{settings.app_port}",
        f"http://127.0.0.1:{settings.app_port}",
    ],
    allow_methods=["GET", "POST", "DELETE"],
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
    return FileResponse(WEB_DIR / "terminal.html")


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket_endpoint(websocket)


_trader: AITrader = None
_trader_task = None
_training_loop_inst: TrainingLoop = None
_hourly_trainer_inst: HourlyTrainer = None
_alert_monitor_inst: AlertMonitor = None
_alert_task = None


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
                    logger.warning("Portfolio snapshot DB write failed", exc_info=True)
                finally:
                    db.close()
        except Exception as e:
            logger.warning("Snapshot loop error: %s", e)
        await asyncio.sleep(300)  # every 5 minutes

@app.on_event("startup")
async def startup():
    global _trader, _trader_task, _training_loop_inst, _hourly_trainer_inst
    global _alert_monitor_inst, _alert_task

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
    _hourly_trainer_inst = HourlyTrainer(
        _trader._trainer, broadcast_fn=broadcast, trader=_trader
    )

    set_trader(_trader)
    set_training_loop(_training_loop_inst)
    set_hourly_trainer(_hourly_trainer_inst)

    _trader_task = asyncio.create_task(_trader.start())
    asyncio.create_task(_snapshot_loop())
    _alert_monitor_inst = AlertMonitor(exchange, broadcast_fn=broadcast)
    _alert_task = asyncio.create_task(_alert_monitor_inst.start())
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
        _trader.stop()   # signals the event — unlocks the inter-cycle sleep
    if _trader_task:
        # Give the current cycle up to 30 s to finish cleanly, then force-cancel.
        try:
            await asyncio.wait_for(asyncio.shield(_trader_task), timeout=30)
        except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
            _trader_task.cancel()
    # Close exchange HTTP sessions to avoid ResourceWarning on exit
    try:
        if _trader and hasattr(_trader._exchange, "close"):
            await _trader._exchange.close()
    except Exception:
        pass
    if _hourly_trainer_inst:
        _hourly_trainer_inst.stop()
    if _alert_monitor_inst:
        _alert_monitor_inst.stop()
    if _alert_task:
        _alert_task.cancel()


def main():
    print(f"""
╔══════════════════════════════════════════╗
║    Aiterra v2.0.0  |  Lunai v2.0.0          ║
║  Mode: {settings.trading_mode.upper():<10} Model: {settings.ai_model:<12}║
║  Port: {settings.app_port:<10} URL: http://localhost:{settings.app_port} ║
╚══════════════════════════════════════════╝
""")
    # Bind to localhost only by default — prevents unintended LAN exposure.
    # Set app.host = "0.0.0.0" in settings.yml to expose over a network.
    host = settings.get("app", "host", default="127.0.0.1")
    uvicorn.run(
        app,
        host=host,
        port=settings.app_port,
        reload=False,
        log_level=settings.get("app", "log_level", default="info").lower(),
    )


if __name__ == "__main__":
    main()
