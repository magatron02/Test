import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.database import Portfolio, Trade, TrainingRecord, get_db
from ..notifications import line_notify, telegram_notify

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

# Reference to trader injected at startup
_trader = None


def set_trader(trader):
    global _trader
    _trader = trader


@router.get("/status")
async def get_status():
    return {
        "mode": settings.trading_mode,
        "ai_model": settings.ai_model,
        "symbols": settings.symbols,
        "running": _trader._running if _trader else False,
        "open_trades": len(_trader.open_trades) if _trader else 0,
    }


@router.get("/prices")
async def get_prices():
    if not _trader:
        return {}
    return {
        sym: {
            "price": a.price,
            "change_24h": a.change_24h,
            "rsi": a.rsi,
            "signal": a.overall_signal,
            "signal_strength": a.signal_strength,
        }
        for sym, a in _trader.analyses.items()
    }


@router.get("/portfolio")
async def get_portfolio():
    if not _trader:
        raise HTTPException(503, "Trader not running")
    try:
        balances = await _trader._exchange.get_balance()
        analyses = _trader.analyses
        positions = []
        total_value = 0.0

        cash_bal = balances.get("USDT")
        cash = float(cash_bal.free) if cash_bal else 0.0
        total_value += cash

        for sym, analysis in analyses.items():
            base = sym.split("/")[0]
            bal = balances.get(base)
            if bal and bal.total > 0:
                value = bal.total * analysis.price
                total_value += value
                entry = _trader.open_trades.get(sym, {}).get("price", analysis.price)
                positions.append({
                    "symbol": sym,
                    "amount": bal.total,
                    "price": analysis.price,
                    "value": value,
                    "entry_price": entry,
                    "pnl_pct": (analysis.price - entry) / entry * 100 if entry > 0 else 0,
                })

        return {
            "cash_usdt": cash,
            "total_value": total_value,
            "positions": positions,
            "is_demo": _trader._exchange.is_demo,
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/trades")
async def get_trades(limit: int = 50, db: Session = Depends(get_db)):
    trades = db.query(Trade).order_by(Trade.opened_at.desc()).limit(limit).all()
    return [
        {
            "id": t.id,
            "symbol": t.symbol,
            "side": t.side,
            "price": t.price,
            "amount": t.amount,
            "cost": t.cost,
            "status": t.status,
            "strategy": t.strategy,
            "ai_model": t.ai_model,
            "confidence": t.confidence,
            "reasoning": t.reasoning,
            "close_price": t.close_price,
            "pnl": t.pnl,
            "pnl_pct": t.pnl_pct,
            "mode": t.mode,
            "opened_at": t.opened_at.isoformat() if t.opened_at else None,
            "closed_at": t.closed_at.isoformat() if t.closed_at else None,
        }
        for t in trades
    ]


@router.get("/stats")
async def get_stats(db: Session = Depends(get_db)):
    closed = db.query(Trade).filter(Trade.status == "closed").all()
    if not closed:
        return {"total_trades": 0, "win_rate": 0, "avg_pnl_pct": 0, "total_pnl": 0}

    wins = [t for t in closed if (t.pnl or 0) > 0]
    total_pnl = sum(t.pnl or 0 for t in closed)
    avg_pnl_pct = sum(t.pnl_pct or 0 for t in closed) / len(closed)

    return {
        "total_trades": len(closed),
        "win_rate": len(wins) / len(closed) * 100,
        "avg_pnl_pct": avg_pnl_pct,
        "total_pnl": total_pnl,
        "best_trade": max((t.pnl_pct or 0) for t in closed),
        "worst_trade": min((t.pnl_pct or 0) for t in closed),
    }


@router.get("/training")
async def get_training_stats():
    if not _trader:
        raise HTTPException(503, "Trader not running")
    return _trader.trainer_stats


@router.post("/training/trigger")
async def trigger_training():
    if not _trader:
        raise HTTPException(503, "Trader not running")
    success = _trader._trainer.train()
    return {"success": success, "stats": _trader.trainer_stats}


@router.get("/settings")
async def get_settings():
    cfg = settings._cfg.copy()
    # mask API keys
    for ex in cfg.get("exchanges", {}).values():
        if isinstance(ex, dict):
            if "api_key" in ex and ex["api_key"]:
                ex["api_key"] = ex["api_key"][:4] + "****"
            if "api_secret" in ex and ex["api_secret"]:
                ex["api_secret"] = "****"
    if "ai" in cfg and "claude" in cfg["ai"]:
        key = cfg["ai"]["claude"].get("api_key", "")
        cfg["ai"]["claude"]["api_key"] = key[:8] + "****" if key else ""
    return cfg


@router.post("/settings")
async def update_settings(data: Dict[str, Any]):
    for section, values in data.items():
        if isinstance(values, dict):
            for key, val in values.items():
                settings.set(val, section, key)
    settings.save()
    settings.reload()
    return {"success": True}


@router.post("/mode")
async def set_mode(data: Dict[str, str]):
    mode = data.get("mode", "demo")
    if mode not in ("demo", "live"):
        raise HTTPException(400, "Mode must be 'demo' or 'live'")
    settings.set(mode, "trading", "mode")
    settings.save()
    return {"mode": mode}


@router.post("/strategy")
async def set_strategy(data: Dict[str, str]):
    strategy = data.get("strategy", "hybrid")
    if strategy not in ("dca", "trend", "mean_reversion", "hybrid"):
        raise HTTPException(400, "Invalid strategy")
    settings.set(strategy, "strategy", "primary")
    settings.save()
    return {"strategy": strategy}


@router.post("/ai-model")
async def set_ai_model(data: Dict[str, str]):
    model = data.get("model", "hybrid")
    valid = ("claude", "rule_based", "ml", "hybrid")
    if model not in valid:
        raise HTTPException(400, f"Model must be one of {valid}")
    settings.set(model, "ai", "default_model")
    settings.save()
    return {"model": model}


@router.post("/demo/reset")
async def reset_demo():
    if not _trader or not _trader._exchange.is_demo:
        raise HTTPException(400, "Not in demo mode")
    _trader._exchange.reset()
    _trader._open_trades.clear()
    return {"success": True}
