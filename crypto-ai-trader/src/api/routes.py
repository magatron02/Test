import asyncio
import csv
import io
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.database import Portfolio, PriceAlert, Trade, TrainingRecord, get_db, SessionLocal
from .websocket import get_notifications, clear_notifications
from ..notifications import line_notify, telegram_notify

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

# ── Rate limiting (slowapi) ───────────────────────────────────────────────────
try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    _limiter = Limiter(key_func=get_remote_address, default_limits=[])
except ImportError:
    _limiter = None


def _rate_limit(limit_string: str):
    """Dependency that applies a rate limit when slowapi is available."""
    if _limiter is None:
        return Depends(lambda: None)
    return Depends(_limiter.limit(limit_string))

# Reference to trader injected at startup
_trader = None
_training_loop = None
_hourly_trainer = None


def set_trader(trader):
    global _trader
    _trader = trader


def set_training_loop(loop):
    global _training_loop
    _training_loop = loop


def set_hourly_trainer(ht):
    global _hourly_trainer
    _hourly_trainer = ht


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
    # Quote currency (USDT for global exchanges, THB for Bitkub / Binance TH)
    quote = _trader._exchange.quote_currency
    try:
        balances = await _trader._exchange.get_balance()
        analyses = _trader.analyses
        positions = []
        total_value = 0.0

        cash_bal = balances.get(quote)
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

        ex = _trader._exchange
        return {
            "cash_usdt": cash,        # kept for UI back-compat; holds `quote` balance
            "quote_currency": quote,
            "total_value": total_value,
            "positions": positions,
            "is_demo": ex.is_demo,
            "initial_balance": getattr(ex, "_initial_cash", None),
        }
    except Exception as e:
        # In live mode a transient API/auth error shouldn't blank the dashboard.
        logger.warning(f"Portfolio fetch failed ({_trader._exchange.name}): {e}")
        return {
            "cash_usdt": 0.0,
            "quote_currency": quote,
            "total_value": 0.0,
            "positions": [],
            "is_demo": _trader._exchange.is_demo,
            "error": str(e)[:160],
        }


@router.get("/trades")
async def get_trades(limit: int = 50, db: Session = Depends(get_db)):
    limit = max(1, min(limit, 1000))   # cap unbounded reads
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
            "journal": t.journal,
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


@router.get("/dashboard/state")
async def get_dashboard_state():
    """GET /api/dashboard/state — signal funnel, today's PnL, and AI agent activity."""
    if not _trader:
        return {
            "funnel": {"analyzed": 0, "signals": 0, "approved": 0, "rejected": 0},
            "pnl_today": {"realized": 0, "floating": 0, "total": 0},
            "agents": {}, "last_signal": None, "open_positions": 0,
        }
    return await _trader.get_dashboard_state()


@router.get("/training")
async def get_training_stats():
    if not _trader:
        raise HTTPException(503, "Trader not running")
    return _trader.trainer_stats


@router.post("/training/trigger")
@(_limiter.limit("6/minute") if _limiter else lambda f: f)
async def trigger_training(request: Request):
    if not _trader:
        raise HTTPException(503, "Trader not running")
    success = _trader._trainer.train()
    return {"success": success, "stats": _trader.trainer_stats}


@router.get("/ml/feature-importance")
async def ml_feature_importance():
    """Global SHAP feature importance from the LightGBM signal model (ML4T Ch.12)."""
    if not _trader:
        raise HTTPException(503, "Trader not running")
    try:
        importance = _trader._trainer.feature_importance()
        stats = _trader.trainer_stats
        return {
            "model_type": stats.get("model_type", "none"),
            "accuracy":   stats.get("accuracy"),
            "features":   importance[:20],
        }
    except Exception as e:
        return {"model_type": "none", "features": [], "error": str(e)}


@router.get("/portfolio/hrp")
async def portfolio_hrp():
    """Hierarchical Risk Parity weights across tracked symbols (ML4T Ch.13)."""
    if not _trader:
        raise HTTPException(503, "Trader not running")
    try:
        _trader._update_hrp_weights()
        weights = _trader._hrp_weights or {}
        n = len(weights)
        equal = 1.0 / n if n else 0.0
        rows = [
            {
                "symbol":     s,
                "weight":     round(w, 4),
                "vs_equal":   round((w / equal) if equal else 1.0, 2),
                "multiplier": round(_trader._hrp_multiplier(s), 2),
            }
            for s, w in sorted(weights.items(), key=lambda kv: -kv[1])
        ]
        return {"equal_weight": round(equal, 4), "weights": rows}
    except Exception as e:
        return {"weights": [], "error": str(e)}


@router.get("/pairs/cointegration")
async def pairs_cointegration():
    """Cointegrated pairs for statistical-arbitrage signals (ML4T Ch.9)."""
    if not _trader:
        raise HTTPException(503, "Trader not running")
    try:
        pairs = _trader.cointegration_pairs()
        return {"pairs": pairs, "count": len(pairs)}
    except Exception as e:
        return {"pairs": [], "count": 0, "error": str(e)}


@router.get("/settings")
async def get_settings():
    cfg = settings._cfg.copy()
    # mask API keys
    for ex in cfg.get("exchanges", {}).values():
        if isinstance(ex, dict):
            if "api_key" in ex and ex["api_key"]:
                ex["api_key"] = "****"          # full mask — even first chars leak entropy
            if "api_secret" in ex and ex["api_secret"]:
                ex["api_secret"] = "****"
            if "api_secret" in ex and ex["api_secret"]:
                ex["api_secret"] = "****"
    if "ai" in cfg:
        for provider in ("claude", "openai", "gemini"):
            if provider in cfg["ai"] and isinstance(cfg["ai"][provider], dict):
                key = cfg["ai"][provider].get("api_key", "")
                cfg["ai"][provider]["api_key"] = key[:8] + "****" if key else ""
    return cfg


# (section, key) → (type_coerce_fn, min_val, max_val)
# None min/max means no range check.
_SETTINGS_SCHEMA: Dict[tuple, tuple] = {
    ("trading", "take_profit_pct"):    (float, 0.001, 0.50),
    ("trading", "stop_loss_pct"):      (float, 0.001, 0.50),
    ("trading", "min_confidence"):     (float, 0.10,  1.0),
    ("trading", "analysis_interval"):  (int,   30,    86400),
    ("trading", "risk_per_trade_pct"): (float, 0.001, 0.20),
    ("trading", "max_daily_loss_pct"): (float, 0.001, 1.0),
    ("trading", "max_open_trades"):    (int,   1,     50),
    ("trading", "max_position_pct"):   (float, 0.01,  1.0),
    ("trading", "dry_run"):            (bool,  None,  None),
    ("trading", "live_max_budget_usdt"): (float, 0.0, 1e7),
    ("risk",    "max_drawdown_pct"):   (float, 0.01,  1.0),
    ("risk",    "max_daily_loss_pct"): (float, 0.001, 1.0),
    ("risk",    "max_portfolio_heat"): (float, 0.01,  1.0),
    ("risk",    "max_position_pct"):   (float, 0.01,  1.0),
    ("backtest","fee_pct"):            (float, 0.0,   0.05),
    ("backtest","slippage_pct"):       (float, 0.0,   0.05),
    ("position_sizer", "kelly_fraction"):   (float, 0.01, 1.0),
    ("position_sizer", "min_trade_usdt"):   (float, 1.0, 1e6),
    ("position_sizer", "max_trade_usdt"):   (float, 1.0, 1e6),
    ("position_sizer", "fallback_risk_pct"):(float, 0.001, 0.20),
    ("position_sizer", "target_atr_pct"):   (float, 0.1,  20.0),
}


def _coerce_and_validate(section: str, key: str, value: Any) -> Any:
    """Type-coerce and range-check a setting value. Raises HTTPException on failure."""
    schema = _SETTINGS_SCHEMA.get((section, key))
    if schema is None:
        return value   # no schema for this key — pass through unchanged
    coerce_fn, lo, hi = schema
    try:
        if coerce_fn is bool:
            if isinstance(value, bool):
                coerced = value
            elif isinstance(value, str):
                coerced = value.lower() in ("true", "1", "yes")
            else:
                coerced = bool(value)
        else:
            coerced = coerce_fn(value)
    except (TypeError, ValueError):
        raise HTTPException(400, f"'{section}.{key}' must be a {coerce_fn.__name__}")
    if lo is not None and coerced < lo:
        raise HTTPException(400, f"'{section}.{key}' must be >= {lo}")
    if hi is not None and coerced > hi:
        raise HTTPException(400, f"'{section}.{key}' must be <= {hi}")
    return coerced


_SETTINGS_ALLOWLIST: Dict[str, set] = {
    "trading": {
        "take_profit_pct", "stop_loss_pct", "min_confidence",
        "analysis_interval", "risk_per_trade_pct", "max_daily_loss_pct",
        "max_open_trades", "max_position_pct", "dry_run",
        "schedule", "live_max_budget_usdt",
    },
    "strategy": {
        "primary", "roi_table", "trailing_stop",
    },
    "risk": {
        "max_drawdown_pct", "max_daily_loss_pct",
        "max_portfolio_heat", "max_position_pct",
    },
    "ai": {
        "default_model",
    },
    "notifications": {
        "line", "telegram", "notify_on",
    },
    "exchanges": {
        # allow writing api_key/secret only — not enabled/testnet flags
        "binance", "binance_th", "bitkub", "okx",
    },
    "backtest": {"fee_pct", "slippage_pct"},
    "position_sizer": {
        "kelly_fraction", "min_trade_usdt", "max_trade_usdt",
        "fallback_risk_pct", "target_atr_pct",
    },
}


@router.post("/settings")
async def update_settings(data: Dict[str, Any]):
    for section, values in data.items():
        allowed_keys = _SETTINGS_ALLOWLIST.get(section)
        if allowed_keys is None:
            raise HTTPException(400, f"Section '{section}' is not writable via API")
        if isinstance(values, dict):
            for key, val in values.items():
                if key not in allowed_keys:
                    raise HTTPException(400, f"Key '{section}.{key}' is not writable via API")
                val = _coerce_and_validate(section, key, val)
                settings.set(val, section, key)
        else:
            # scalar top-level key
            settings.set(values, section)
    settings.save()
    settings.reload()
    return {"success": True}


@router.post("/mode")
async def set_mode(data: Dict[str, Any]):
    mode = data.get("mode", "demo")
    if mode not in ("demo", "live"):
        raise HTTPException(400, "Mode must be 'demo' or 'live'")
    if mode == "live":
        # Real funds at risk — require explicit confirmation and accept a budget cap.
        if not data.get("confirm"):
            raise HTTPException(400, "Live mode requires confirm=true")
        if "budget_usdt" in data:
            try:
                budget = float(data.get("budget_usdt") or 0)
            except (TypeError, ValueError):
                raise HTTPException(400, "budget_usdt must be a number")
            if budget < 0 or budget > 10_000_000:
                raise HTTPException(400, "budget_usdt must be 0 – 10,000,000")
            settings.set(budget, "trading", "live_max_budget_usdt")
    settings.set(mode, "trading", "mode")
    settings.save()
    settings.reload()
    return {"mode": mode,
            "live_max_budget_usdt": settings.get("trading", "live_max_budget_usdt", default=0)}


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
    valid = ("claude", "rule_based", "ml", "hybrid", "multi_model")
    if model not in valid:
        raise HTTPException(400, f"Model must be one of {valid}")
    settings.set(model, "ai", "default_model")
    settings.save()
    return {"model": model}


@router.get("/symbols")
async def get_symbols():
    """GET /api/symbols — list currently tracked trading pairs."""
    return {"symbols": settings.symbols}


@router.post("/symbols")
async def update_symbols(data: Dict[str, Any]):
    """POST /api/symbols — add or remove a trading pair at runtime.

    Body: {"add": "TAO/THB"} or {"remove": "BTC/USDT"}
    Changes are persisted to settings.yml and take effect on the next analysis cycle.
    """
    current = list(settings.symbols)

    if "add" in data:
        sym = str(data["add"]).strip().upper()
        if "/" not in sym:
            raise HTTPException(400, "Symbol must be in BASE/QUOTE format (e.g. TAO/THB)")
        if sym not in current:
            current.append(sym)

    if "remove" in data:
        sym = str(data["remove"]).strip().upper()
        if sym in current:
            current.remove(sym)
        if not current:
            raise HTTPException(400, "Cannot remove the last symbol")

    settings.set(current, "trading", "symbols")
    settings.save()
    settings.reload()

    # Hot-reload the trader's symbol list so new pair is picked up immediately
    if _trader:
        _trader._analyses  # existing analyses stay; new symbol added next cycle

    return {"symbols": settings.symbols}


@router.post("/demo/reset")
async def reset_demo():
    if not _trader or not _trader._exchange.is_demo:
        raise HTTPException(400, "Not in demo mode")
    _trader._exchange.reset()
    _trader._open_trades.clear()
    return {"success": True}



@router.get("/trades/export")
async def export_trades(db: Session = Depends(get_db)):
    """GET /api/trades/export — Download all trades as CSV."""
    trades = db.query(Trade).order_by(Trade.opened_at.desc()).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "symbol", "side", "price", "amount", "cost", "mode",
                     "exchange", "strategy", "ai_model", "confidence", "status",
                     "close_price", "pnl", "pnl_pct", "opened_at", "closed_at"])
    for t in trades:
        writer.writerow([
            t.id, t.symbol, t.side, t.price, t.amount, t.cost, t.mode,
            t.exchange, t.strategy, t.ai_model, t.confidence, t.status,
            t.close_price, t.pnl, t.pnl_pct,
            t.opened_at.isoformat() if t.opened_at else "",
            t.closed_at.isoformat() if t.closed_at else "",
        ])
    buf.seek(0)
    filename = f"trades_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/stats/advanced")
async def get_advanced_stats(db: Session = Depends(get_db)):
    """GET /api/stats/advanced — Sharpe ratio, Max Drawdown, daily PnL."""
    closed = db.query(Trade).filter(Trade.status == "closed").order_by(Trade.closed_at).all()
    if len(closed) < 2:
        return {"sharpe": 0, "max_drawdown_pct": 0, "daily_pnl": [], "equity_curve": []}

    # Cumulative equity from trades (start at 10000 for display)
    capital = 10000.0
    equity  = [capital]
    for t in closed:
        pnl = t.pnl or 0
        capital += pnl
        equity.append(round(capital, 2))

    eq = np.array(equity, dtype=float)
    rets = np.diff(eq) / np.where(eq[:-1] != 0, eq[:-1], 1)
    sharpe = float((rets.mean() / rets.std()) * math.sqrt(252)) if rets.std() > 0 else 0.0

    run_max = np.maximum.accumulate(eq)
    max_dd  = float(((eq - run_max) / np.where(run_max != 0, run_max, 1)).min() * 100)

    # Daily PnL aggregation
    from collections import defaultdict
    daily: dict = defaultdict(float)
    for t in closed:
        if t.closed_at:
            day = t.closed_at.strftime("%Y-%m-%d")
            daily[day] += t.pnl or 0
    daily_pnl = [{"date": d, "pnl": round(v, 2)} for d, v in sorted(daily.items())]

    # Use portfolio snapshots for equity curve if available (better than trade-based)
    snapshots = db.query(Portfolio).order_by(Portfolio.recorded_at).all()
    if len(snapshots) >= 2:
        equity_curve = [{"t": s.recorded_at.isoformat(), "v": round(s.total_value_usdt, 2)}
                        for s in snapshots]
        # Recompute drawdown from snapshots
        eq_snap = np.array([s.total_value_usdt for s in snapshots])
        run_max_snap = np.maximum.accumulate(eq_snap)
        max_dd = float(((eq_snap - run_max_snap) / np.where(run_max_snap != 0, run_max_snap, 1)).min() * 100)
        rets_snap = np.diff(eq_snap) / np.where(eq_snap[:-1] != 0, eq_snap[:-1], 1)
        if rets_snap.std() > 0:
            sharpe = float((rets_snap.mean() / rets_snap.std()) * math.sqrt(252 * 288))  # 5-min intervals
    else:
        equity_curve = [{"i": i, "v": v} for i, v in enumerate(equity)]

    return {
        "sharpe":           round(sharpe, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "daily_pnl":        daily_pnl,
        "equity_curve":     equity_curve,
    }


@router.get("/candles")
async def get_candles(symbol: str = "BTC/USDT", limit: int = 80, timeframe: str = "15m"):
    """GET /api/candles?symbol=BTC/USDT&limit=80&timeframe=15m — OHLCV for candlestick chart."""
    if not _trader:
        raise HTTPException(503, "Trader not running")
    try:
        candles = await _trader._exchange.get_ohlcv(symbol, timeframe=timeframe, limit=limit)
        return [
            {"t": int(c.timestamp.timestamp() * 1000),
             "o": c.open, "h": c.high, "l": c.low, "c": c.close, "v": c.volume}
            for c in candles
        ]
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/analysis/mtf")
async def get_mtf_analysis(symbol: str = "BTC/USDT"):
    """GET /api/analysis/mtf — Multi-timeframe analysis (15m + 1h + 4h)."""
    if not _trader:
        raise HTTPException(503, "Trader not running")
    from ..agent.market_analyzer import analyze

    async def _tf(tf: str, limit: int):
        try:
            candles = await _trader._exchange.get_ohlcv(symbol, timeframe=tf, limit=limit)
            ticker  = await _trader._exchange.get_ticker(symbol)
            result  = analyze(symbol, candles, ticker.price, ticker.change_24h)
            return {
                "timeframe":  tf,
                "signal":     result.overall_signal,
                "confidence": round(result.signal_strength, 2),
                "rsi":        round(result.rsi, 1),
                "ema_trend":  result.ema_trend,
                "macd_trend": result.macd_trend,
                "bb_signal":  result.bb_signal,
            }
        except Exception:
            return {"timeframe": tf, "signal": "HOLD", "confidence": 0,
                    "rsi": 50, "ema_trend": "NEUTRAL", "macd_trend": "NEUTRAL", "bb_signal": "NEUTRAL"}

    results = {}
    for tf, limit in [("15m", 80), ("1h", 80), ("4h", 60)]:
        results[tf] = await _tf(tf, limit)

    # Weighted combined signal (15m:0.3, 1h:0.4, 4h:0.3)
    weights = {"15m": 0.3, "1h": 0.4, "4h": 0.3}
    buy_score = sell_score = 0.0
    for tf, w in weights.items():
        sig = results[tf]["signal"]
        conf = results[tf]["confidence"]
        if sig == "BUY":   buy_score  += w * conf
        elif sig == "SELL": sell_score += w * conf

    if buy_score > sell_score and buy_score >= 0.25:
        combined = "BUY"
        combined_conf = round(buy_score, 2)
    elif sell_score > buy_score and sell_score >= 0.25:
        combined = "SELL"
        combined_conf = round(sell_score, 2)
    else:
        combined = "HOLD"
        combined_conf = round(max(buy_score, sell_score), 2)

    return {
        "symbol":           symbol,
        "timeframes":       results,
        "combined_signal":  combined,
        "combined_conf":    combined_conf,
    }


@router.post("/backtest")
@(_limiter.limit("10/minute") if _limiter else lambda f: f)
async def run_backtest(request: Request, data: Dict[str, Any]):
    """POST /api/backtest — Backtest with Market Regime + Chart Patterns + Kelly Sizing.

    Body:
      symbol:          BTC/USDT (default)
      days:            7-365    (default 30)
      tp_pct:          take-profit fraction (default 0.04)
      sl_pct:          stop-loss  fraction  (default 0.02)
      initial_capital: starting capital USDT (default 10000)

    Response includes:
      - Primary metrics from autotrade AI stack
      - comparison.basic / comparison.hybrid / comparison.autotrade
      - regime_stats: performance breakdown per detected regime
      - pattern_stats: best/worst chart patterns by PnL
      - equity_curve + last 50 annotated trades
    """
    from ..agent.backtest import run_backtest_real as _run
    symbol  = str(data.get("symbol", "BTC/USDT"))
    days    = int(data.get("days", 30))
    tp_pct  = float(data.get("tp_pct", 0.04))
    sl_pct  = float(data.get("sl_pct", 0.02))
    capital = float(data.get("initial_capital", 10_000.0))
    if days < 7 or days > 365:
        raise HTTPException(400, "days must be 7-365")
    if not (0.001 <= tp_pct <= 0.50):
        raise HTTPException(400, "tp_pct must be between 0.1% and 50%")
    if not (0.001 <= sl_pct <= 0.50):
        raise HTTPException(400, "sl_pct must be between 0.1% and 50%")
    if capital < 100 or capital > 10_000_000:
        raise HTTPException(400, "initial_capital must be 100 – 10,000,000")
    try:
        result = await _run(symbol, days=days, tp_pct=tp_pct, sl_pct=sl_pct,
                            initial_capital=capital)
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/backtest/walkforward")
@(_limiter.limit("4/minute") if _limiter else lambda f: f)
async def backtest_walkforward(
    request: Request,
    symbol: str = "BTC/USDT",
    days: int = 90,
    folds: int = 3,
    tp_pct: float = 0.04,
    sl_pct: float = 0.02,
    initial_capital: float = 10000.0,
):
    """Walk-forward validation: Jesse-style rolling IS/OOS parameter optimisation."""
    from ..agent.backtest import run_walkforward
    if days < 14 or days > 365:
        raise HTTPException(400, "days must be 14-365")
    if folds < 2 or folds > 10:
        raise HTTPException(400, "folds must be 2-10")
    if not (0.001 <= tp_pct <= 0.50):
        raise HTTPException(400, "tp_pct must be between 0.1% and 50%")
    if not (0.001 <= sl_pct <= 0.50):
        raise HTTPException(400, "sl_pct must be between 0.1% and 50%")
    if initial_capital < 100 or initial_capital > 10_000_000:
        raise HTTPException(400, "initial_capital must be 100 – 10,000,000")
    try:
        result = await run_walkforward(
            symbol=symbol, days=days, folds=folds,
            tp_pct=tp_pct, sl_pct=sl_pct, initial_capital=initial_capital,
        )
        return result
    except Exception as e:
        return {"error": str(e), "symbol": symbol}


# ─── Training Loop Routes ──────────────────────────────────────

@router.post("/training/loop/start")
async def start_training_loop(data: Dict[str, Any] = None):
    if not _training_loop:
        raise HTTPException(503, "Training loop not available")
    d = data or {}
    target     = float(d.get("target", 0.80))
    auto_trade = bool(d.get("auto_trade", False))
    await _training_loop.start(target=target, auto_trade=auto_trade)
    return {"started": True, "target": target, "auto_trade": auto_trade}


@router.get("/training/loop/status")
async def get_training_loop_status():
    if not _training_loop:
        return {"running": False, "completed": False, "total_trades": 0, "win_rate": 0.0}
    return _training_loop.status


# ─── Notification History ──────────────────────────────────────

@router.get("/notifications")
async def get_notification_history():
    """GET /api/notifications — recent trade/training events (newest first)."""
    return get_notifications()


@router.delete("/notifications")
async def clear_notification_history():
    """DELETE /api/notifications — clear the notification log."""
    clear_notifications()
    return {"cleared": True}


# ─── Live Positions (enriched open trades) ────────────────────

@router.get("/positions")
async def get_open_positions():
    """GET /api/positions — open trades enriched with current price and floating PnL."""
    if not _trader:
        return []
    rows = []
    for sym, trade in list(_trader.open_trades.items()):
        analysis = _trader.analyses.get(sym)
        cur_price = analysis.price if analysis else trade["price"]
        entry     = trade["price"]
        amount    = trade.get("amount", 0)
        floating  = (cur_price - entry) * amount
        pnl_pct   = (cur_price - entry) / entry * 100 if entry > 0 else 0.0
        rows.append({
            "symbol":         sym,
            "side":           trade.get("side", "BUY"),
            "entry_price":    round(entry, 6),
            "current_price":  round(cur_price, 6),
            "amount":         round(amount, 6),
            "cost":           round(trade.get("cost", 0), 2),
            "floating_pnl":   round(floating, 4),
            "pnl_pct":        round(pnl_pct, 2),
            "stop_loss":      round(trade.get("stop_loss_price", 0), 6),
            "take_profit":    round(trade.get("take_profit_price", 0), 6),
            "strategy":       trade.get("strategy", ""),
            "confidence":     round(trade.get("confidence", 0), 2),
            "opened_at":      trade["opened_at"].isoformat() if isinstance(trade.get("opened_at"), datetime) else trade.get("opened_at"),
        })
    return rows


# ─── Price Alerts ─────────────────────────────────────────────────

def _alert_to_dict(a: PriceAlert) -> dict:
    return {
        "id": a.id,
        "symbol": a.symbol,
        "condition": a.condition,
        "target_price": a.target_price,
        "note": a.note,
        "active": a.active,
        "repeat": a.repeat,
        "triggered_at": a.triggered_at.isoformat() if a.triggered_at else None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


@router.get("/alerts")
async def list_alerts(db: Session = Depends(get_db)):
    """GET /api/alerts — all price alerts, active first then newest."""
    alerts = db.query(PriceAlert).order_by(
        PriceAlert.active.desc(), PriceAlert.created_at.desc()
    ).all()
    return [_alert_to_dict(a) for a in alerts]


@router.post("/alerts")
async def create_alert(data: Dict[str, Any], db: Session = Depends(get_db)):
    """POST /api/alerts — create a price alert.
    Body: {"symbol":"BTC/THB", "condition":"above"|"below", "target_price":1234, "note":"", "repeat":false}
    """
    symbol = str(data.get("symbol") or "")
    condition = str(data.get("condition") or "").lower()
    if symbol not in settings.symbols:
        raise HTTPException(400, f"symbol must be one of: {settings.symbols}")
    if condition not in ("above", "below"):
        raise HTTPException(400, "condition must be 'above' or 'below'")
    try:
        target = float(data.get("target_price"))
    except (TypeError, ValueError):
        raise HTTPException(400, "target_price must be a number")
    if target <= 0 or target > 1e12:
        raise HTTPException(400, "target_price out of range")
    note = (str(data.get("note") or ""))[:200]
    alert = PriceAlert(
        symbol=symbol,
        condition=condition,
        target_price=target,
        note=note or None,
        active=True,
        repeat=bool(data.get("repeat", False)),
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return _alert_to_dict(alert)


@router.post("/alerts/{alert_id}/toggle")
async def toggle_alert(alert_id: int, db: Session = Depends(get_db)):
    """POST /api/alerts/{id}/toggle — enable/disable an alert (re-arms a fired one)."""
    alert = db.query(PriceAlert).filter(PriceAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(404, "Alert not found")
    alert.active = not alert.active
    if alert.active:
        alert.triggered_at = None  # re-arm
    db.commit()
    db.refresh(alert)
    return _alert_to_dict(alert)


@router.delete("/alerts/{alert_id}")
async def delete_alert(alert_id: int, db: Session = Depends(get_db)):
    """DELETE /api/alerts/{id} — remove an alert."""
    alert = db.query(PriceAlert).filter(PriceAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(404, "Alert not found")
    db.delete(alert)
    db.commit()
    return {"deleted": alert_id}


# ─── Trade Journal ────────────────────────────────────────────────

@router.post("/trades/{trade_id}/note")
async def set_trade_note(trade_id: int, data: Dict[str, Any], db: Session = Depends(get_db)):
    """POST /api/trades/{id}/note — attach/update a personal journal note on a trade.
    Body: {"note": "เหตุผลที่เข้า/ออก ..."}
    """
    trade = db.query(Trade).filter(Trade.id == trade_id).first()
    if not trade:
        raise HTTPException(404, "Trade not found")
    note = str(data.get("note") or "")[:2000]
    trade.journal = note or None
    db.commit()
    return {"ok": True, "id": trade_id, "journal": trade.journal}


@router.post("/trade/manual")
@(_limiter.limit("12/minute") if _limiter else lambda f: f)
async def manual_trade(request: Request, data: Dict[str, Any]):
    """POST /api/trade/manual — manually open or close a position (demo-safe override).
    Body: {"action":"BUY"|"SELL"|"CLOSE", "symbol":"BTC/USDT", "amount_usdt": 200}
    Bypasses the AI signal so users can test the full trade pipeline.
    """
    if not _trader:
        raise HTTPException(503, "Trader not running")
    action   = (data.get("action") or "").upper()
    symbol   = str(data.get("symbol") or "BTC/USDT")
    amt_usdt = float(data.get("amount_usdt") or 0)
    if action not in ("BUY", "SELL", "CLOSE"):
        raise HTTPException(400, "action must be BUY, SELL, or CLOSE")
    if symbol not in settings.symbols:
        raise HTTPException(400, f"symbol must be one of: {settings.symbols}")
    if amt_usdt < 0 or amt_usdt > 1_000_000:
        raise HTTPException(400, "amount_usdt must be 0 – 1,000,000")

    analysis = await _trader.analyze_symbol(symbol)
    if not analysis:
        raise HTTPException(503, f"Cannot fetch data for {symbol}")

    if action == "CLOSE":
        if symbol not in _trader.open_trades:
            raise HTTPException(400, f"No open trade for {symbol}")
        trade = _trader.open_trades[symbol]
        side  = trade["side"]
        price = analysis.price
        amount = trade.get("amount", 0)
        pnl   = (price - trade["price"]) * amount if side == "BUY" else (trade["price"] - price) * amount
        pnl_pct = pnl / (trade["price"] * amount) * 100 if trade["price"] and amount else 0
        result = await _trader._close_trade(symbol, price, "manual_close")
        if not result:
            raise HTTPException(500, "Close failed: position may have already been liquidated")
        return {"ok": True, "action": "CLOSE", "symbol": symbol,
                "price": round(result.get("price", price), 6),
                "pnl": round(result.get("pnl", pnl), 4),
                "pnl_pct": round(result.get("pnl_pct", pnl_pct), 2)}

    # BUY / SELL
    from ..agent.strategy_manager import TradingSignal
    from ..agent.market_regime import RegimeResult
    portfolio = await _trader._get_portfolio_summary()
    avail = portfolio.get("available_usdt", 0)
    if amt_usdt <= 0:
        # default: 10% of portfolio, capped at available
        amt_usdt = min(avail * 0.10, avail * 0.95)
    if amt_usdt <= 0:
        raise HTTPException(400, "Insufficient funds for manual trade")
    amount = amt_usdt / analysis.price
    signal = TradingSignal(action=action, confidence=1.0,
                           reasoning="manual override",
                           strategy="manual",
                           stop_loss_pct=0.02,
                           take_profit_pct=0.04)
    # Use cached regime or default
    regime = _trader.regimes.get(symbol) or RegimeResult("RANGING", 0.5, 20.0, 2.0, 0.0, "manual")
    executed = await _trader._execute_trade(symbol, signal, analysis, regime, force=True)
    if executed:
        return {"ok": True, "action": action, "symbol": symbol,
                "price": round(analysis.price, 6), "amount": round(amount, 6),
                "amount_usdt": round(amt_usdt, 2)}
    return {"ok": False, "reason": "execute returned False (risk limit / existing position / demo error)"}


@router.post("/training/loop/stop")
async def stop_training_loop():
    if not _training_loop:
        raise HTTPException(503, "Training loop not available")
    _training_loop.stop()
    return {"stopped": True}


# ─── Arbitrage ────────────────────────────────────────────────────────────────

@router.get("/arbitrage/scan")
async def get_arbitrage_scan():
    """GET /api/arbitrage/scan — latest tri-arb opportunities + funding rates."""
    if not _trader:
        return {"tri_opportunities": [], "funding_rates": [], "executed": []}
    return _trader._arb.last_result


@router.post("/arbitrage/scan")
@(_limiter.limit("12/minute") if _limiter else lambda f: f)
async def trigger_arbitrage_scan(request: Request):
    """POST /api/arbitrage/scan — immediately run a fresh arb + funding-rate scan."""
    if not _trader:
        raise HTTPException(503, "Trader not running")
    try:
        portfolio = await _trader._get_portfolio_summary()
        result = await _trader._arb.run_cycle(
            symbols       = list(settings.symbols),
            available_usdt = portfolio.get("available_usdt", 0.0),
        )
        return result
    except Exception as exc:
        raise HTTPException(500, str(exc))


@router.get("/arbitrage/stats")
async def get_arbitrage_stats():
    """GET /api/arbitrage/stats — cumulative execution stats."""
    if not _trader:
        return {"triangular": {}, "funding": {}}
    return _trader._arb.full_stats()


@router.get("/training/hourly/status")
async def hourly_train_status():
    """GET /api/training/hourly/status — hourly real-data trainer status."""
    if not _hourly_trainer:
        return {"enabled": False}
    return {"enabled": True, **_hourly_trainer.status}


@router.post("/training/hourly/run")
async def hourly_train_run():
    """POST /api/training/hourly/run — trigger an immediate training run."""
    if not _hourly_trainer:
        raise HTTPException(503, "Hourly trainer not available")
    result = await _hourly_trainer.run_now()
    return result


# ─── Chat Bot ──────────────────────────────────────────────────

class ChatHandler:
    _SYMBOLS = {
        "btc": "BTC/USDT", "eth": "ETH/USDT", "bnb": "BNB/USDT",
        "sol": "SOL/USDT", "xrp": "XRP/USDT",
    }
    _TRAIN_KW    = ["train", "เทรน", "retrain", "ฝึก", "เรียน", "improve", "learn", "อัพเดต", "update model"]
    _REPORT_KW   = ["report", "รายงาน", "stats", "สถิติ", "ผล", "performance", "สรุป", "win rate", "กำไร", "ขาดทุน", "pnl"]
    _PORTFOLIO_KW= ["portfolio", "พอร์ต", "balance", "ยอด", "เงิน", "holdings", "position", "wallet"]
    _BUY_KW      = ["buy", "ซื้อ", "long", "เปิด"]
    _SELL_KW     = ["sell", "ขาย", "short", "ปิด"]
    _ANALYZE_KW  = ["analyze", "วิเคราะห์", "analysis", "check", "ดู", "how is", "สัญญาณ"]

    def __init__(self, trader, hourly_trainer):
        self._trader = trader
        self._hourly_trainer = hourly_trainer

    async def handle(self, message: str) -> dict:
        m = message.lower().strip()
        symbol = next((v for k, v in self._SYMBOLS.items() if k in m), None)

        if any(kw in m for kw in self._TRAIN_KW):
            return await self._handle_train()
        if any(kw in m for kw in self._REPORT_KW):
            return await self._handle_report()
        if any(kw in m for kw in self._PORTFOLIO_KW):
            return await self._handle_portfolio()
        if any(kw in m for kw in self._ANALYZE_KW):
            return await self._handle_analyze(symbol or "BTC/USDT")
        if any(kw in m for kw in self._BUY_KW):
            return await self._handle_trade("BUY", symbol, message)
        if any(kw in m for kw in self._SELL_KW):
            return await self._handle_trade("SELL", symbol, message)
        return await self._handle_general(message)

    async def _handle_train(self) -> dict:
        if not self._hourly_trainer:
            if self._trader:
                ok = self._trader._trainer.train()
                return {"type": "train", "reply": f"เทรน ML model {'สำเร็จ' if ok else 'ไม่สำเร็จ — ต้องการข้อมูลเพิ่ม'}"}
            return {"type": "error", "reply": "Trainer ไม่พร้อมใช้งาน"}
        try:
            result = await self._hourly_trainer.run_now()
            added = result.get("samples_added", 0)
            return {"type": "train", "reply": f"เทรน AI สำเร็จ ✓\nเพิ่มข้อมูล {added} samples\n{result.get('message', '')}"}
        except Exception as e:
            return {"type": "error", "reply": f"เทรนไม่สำเร็จ: {e}"}

    async def _handle_report(self) -> dict:
        db = SessionLocal()
        try:
            closed = db.query(Trade).filter(Trade.status == "closed").all()
            if not closed:
                return {"type": "report", "reply": "ยังไม่มีการเทรดที่ปิดแล้ว"}
            wins = [t for t in closed if (t.pnl or 0) > 0]
            total_pnl = sum(t.pnl or 0 for t in closed)
            win_rate = len(wins) / len(closed) * 100
            avg_pnl = sum(t.pnl_pct or 0 for t in closed) / len(closed)
            recent = sorted(closed, key=lambda t: t.closed_at or datetime.min, reverse=True)[:5]
            recent_lines = "\n".join(
                f"  {'✅' if (t.pnl or 0) > 0 else '❌'} {t.symbol} {t.side} {t.pnl_pct:+.2f}%"
                for t in recent if t.pnl_pct is not None
            )
            reply = (
                f"สรุปผลการเทรด\n"
                f"ทั้งหมด: {len(closed)} trades | Win: {win_rate:.1f}%\n"
                f"PnL รวม: {total_pnl:+.2f} USDT | เฉลี่ย: {avg_pnl:+.2f}%\n\n"
                f"5 ล่าสุด:\n{recent_lines or '  (ไม่มี)'}"
            )
            return {"type": "report", "reply": reply}
        finally:
            db.close()

    async def _handle_portfolio(self) -> dict:
        if not self._trader:
            return {"type": "error", "reply": "Trader ไม่พร้อมใช้งาน"}
        try:
            quote = self._trader._exchange.quote_currency
            balances = await self._trader._exchange.get_balance()
            cash_bal = balances.get(quote)
            cash = float(cash_bal.free) if cash_bal else 0.0
            total = cash
            lines = []
            for sym, analysis in self._trader.analyses.items():
                base = sym.split("/")[0]
                bal = balances.get(base)
                if bal and bal.total > 0:
                    value = bal.total * analysis.price
                    total += value
                    lines.append(f"  {base}: {bal.total:.6f} ({value:.2f} {quote})")
            pos_text = "\n".join(lines) if lines else "  ไม่มี open position"
            reply = f"พอร์ตโฟลิโอ\nCash: {cash:.2f} {quote}\nTotal: {total:.2f} {quote}\n\nPositions:\n{pos_text}"
            return {"type": "portfolio", "reply": reply}
        except Exception as e:
            return {"type": "error", "reply": f"ดึงข้อมูลพอร์ตไม่ได้: {e}"}

    async def _handle_analyze(self, symbol: str) -> dict:
        if not self._trader:
            return {"type": "error", "reply": "Trader ไม่พร้อมใช้งาน"}
        analysis = await self._trader.analyze_symbol(symbol)
        if not analysis:
            return {"type": "error", "reply": f"วิเคราะห์ {symbol} ไม่ได้"}
        portfolio = await self._trader._get_portfolio_summary()
        from ..agent.market_regime import RegimeResult
        regime = self._trader.regimes.get(symbol) or RegimeResult("RANGING", 0.5, 20.0, 2.0, 0.0, "")
        signal = await self._trader._get_final_signal(analysis, portfolio, regime)
        pat_text = ""
        if getattr(analysis, "patterns", None):
            pat_text = "\nPattern: " + ", ".join(p.name_th for p in analysis.patterns[:2])
        reply = (
            f"วิเคราะห์ {symbol} [{regime.regime}]\n"
            f"ราคา: ${analysis.price:.4f} ({analysis.change_24h:+.2f}%)\n"
            f"RSI: {analysis.rsi:.1f} | EMA: {analysis.ema_trend} | MACD: {analysis.macd_trend}\n"
            f"Bollinger: {analysis.bb_signal} | Volatility: {analysis.volatility}{pat_text}\n"
            f"สัญญาณ: {signal.action} (conf {signal.confidence:.0%})\n"
            f"เหตุผล: {signal.reasoning[:220]}"
        )
        return {"type": "analysis", "reply": reply, "signal": signal.action}

    async def _handle_trade(self, action: str, symbol: Optional[str], message: str) -> dict:
        if not self._trader:
            return {"type": "error", "reply": "Trader ไม่พร้อมใช้งาน"}
        if not symbol:
            return {"type": "info", "reply": f"กรุณาระบุ symbol เช่น '{action.lower()} BTC'"}
        analysis = await self._trader.analyze_symbol(symbol)
        if not analysis:
            return {"type": "error", "reply": f"ดึงข้อมูล {symbol} ไม่ได้"}
        portfolio = await self._trader._get_portfolio_summary()
        from ..agent.market_regime import RegimeResult
        regime = self._trader.regimes.get(symbol) or RegimeResult("RANGING", 0.5, 20.0, 2.0, 0.0, "")
        signal = await self._trader._get_final_signal(analysis, portfolio, regime)
        if signal.action == action:
            executed = await self._trader._execute_trade(symbol, signal, analysis, regime)
            if executed:
                return {"type": "trade", "reply": f"✓ ส่งคำสั่ง {action} {symbol} @ ${analysis.price:.4f} (conf {signal.confidence:.0%})\n{signal.reasoning[:180]}"}
            return {"type": "info", "reply": f"AI เห็นด้วยกับ {action} {symbol} แต่ไม่ execute (ติด risk limit / เงินไม่พอ / มี position อยู่แล้ว)"}
        return {"type": "info", "reply": f"AI แนะนำ {signal.action} สำหรับ {symbol} (conf {signal.confidence:.0%})\nไม่ตรงกับคำสั่ง {action} จึงไม่ execute\nเหตุผล: {signal.reasoning[:180]}"}

    async def _handle_general(self, message: str) -> dict:
        api_key = settings.claude_api_key
        if not api_key:
            return {"type": "info", "reply": "คำสั่งที่รองรับ:\n• ซื้อ/ขาย BTC ETH SOL XRP BNB\n• วิเคราะห์ BTC\n• รายงานผล / สรุปผล\n• พอร์ตฉัน\n• เทรนตัวเอง"}
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=api_key)
            db = SessionLocal()
            try:
                recent = db.query(Trade).filter(Trade.status == "closed").order_by(Trade.opened_at.desc()).limit(5).all()
                trade_ctx = ", ".join(f"{t.symbol} {t.side} {t.pnl_pct:+.2f}%" for t in recent if t.pnl_pct is not None) or "ยังไม่มี"
            finally:
                db.close()
            sys_prompt = f"คุณคือ Lunai v1.0.0 — AI trading assistant ภายใน Aiterra ตอบสั้น กระชับ เป็นภาษาไทย recent trades: {trade_ctx}"
            resp = await client.messages.create(
                model=settings.claude_model, max_tokens=512,
                system=sys_prompt,
                messages=[{"role": "user", "content": message}],
            )
            reply = resp.content[0].text if resp.content else "ไม่มีคำตอบ"
            return {"type": "ai", "reply": reply}
        except Exception:
            return {"type": "info", "reply": "คำสั่งที่รองรับ:\n• ซื้อ/ขาย BTC ETH SOL XRP BNB\n• วิเคราะห์ BTC\n• รายงานผล\n• พอร์ตฉัน\n• เทรนตัวเอง"}


@router.post("/chat")
async def chat_endpoint(data: Dict[str, Any]):
    """POST /api/chat — Natural language command interface for the AI trading agent."""
    message = (data.get("message") or "").strip()
    if not message:
        raise HTTPException(400, "message required")
    handler = ChatHandler(_trader, _hourly_trainer)
    return await handler.handle(message)


@router.get("/exchanges/test")
async def test_exchanges():
    """GET /api/exchanges/test — Ping configured exchanges and return status."""
    results = {}

    # Always test demo (should always work)
    if _trader and _trader._exchange:
        try:
            ticker = await _trader._exchange.get_ticker("BTC/USDT")
            results["demo"] = {"ok": True, "price": ticker.price, "source": "live" if ticker.price > 1000 else "simulated"}
        except Exception as e:
            results["demo"] = {"ok": False, "error": str(e)}

    # Test each configured live exchange (single source of truth = factory)
    from ..exchanges import LIVE_EXCHANGES, has_credentials
    from ..exchanges.factory import _load
    for name in LIVE_EXCHANGES:
        cfg = settings.get("exchanges", name) or {}
        if not cfg.get("enabled") or not has_credentials(name):
            results[name] = {"ok": None, "status": "not_configured"}
            continue
        # THB venues quote against THB, not USDT — probe a symbol they list.
        probe = "BTC/THB" if name in ("bitkub", "binance_th") else "BTC/USDT"
        client = None
        try:
            client = _load(name)
            ticker = await client.get_ticker(probe)
            results[name] = {"ok": True, "price": ticker.price}
        except Exception as e:
            results[name] = {"ok": False, "error": str(e)[:120]}
        finally:
            if client is not None and hasattr(client, "close"):
                try:
                    await client.close()
                except Exception:
                    pass

    return results


# ─── Notification Test ─────────────────────────────────────────

@router.post("/notifications/test")
async def test_notifications(data: Dict[str, Any] = None):
    """Send a test message to configured LINE / Telegram channels."""
    msg = "🧪 Lunai v1.0.0 (Aiterra) — การแจ้งเตือนทดสอบ / Test notification ✅"
    results = {}

    # LINE Messaging API
    line_id     = settings.get("notifications", "line", "channel_id",     default="")
    line_secret = settings.get("notifications", "line", "channel_secret", default="")
    if line_id and line_secret:
        try:
            import aiohttp
            # 1. Get channel access token
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.line.me/v2/oauth/accessToken",
                    data={"grant_type": "client_credentials",
                          "client_id": line_id, "client_secret": line_secret},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as tr:
                    tr.raise_for_status()
                    access_token = (await tr.json())["access_token"]
            # 2. Send message (push if user_id set, broadcast otherwise)
            user_id = settings.get("notifications", "line", "user_id", default="")
            headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
            body = {"messages": [{"type": "text", "text": msg}]}
            url = "https://api.line.me/v2/bot/message/push" if user_id else "https://api.line.me/v2/bot/message/broadcast"
            if user_id:
                body["to"] = user_id
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=body,
                                        timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status in (200, 201):
                        results["line"] = {"ok": True}
                    else:
                        body_text = await resp.text()
                        results["line"] = {"ok": False, "error": f"HTTP {resp.status}: {body_text[:120]}"}
        except Exception as e:
            results["line"] = {"ok": False, "error": str(e)[:120]}
    else:
        results["line"] = {"ok": None, "status": "not_configured"}

    # Telegram
    tg_token   = settings.get("notifications", "telegram", "bot_token", default="")
    tg_chat_id = settings.get("notifications", "telegram", "chat_id", default="")
    if tg_token and tg_chat_id:
        try:
            import aiohttp
            url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json={"chat_id": tg_chat_id, "text": msg},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    body = await resp.json()
                    if resp.status == 200 and body.get("ok"):
                        results["telegram"] = {"ok": True}
                    else:
                        results["telegram"] = {"ok": False, "error": body.get("description", f"HTTP {resp.status}")[:120]}
        except Exception as e:
            results["telegram"] = {"ok": False, "error": str(e)[:120]}
    else:
        results["telegram"] = {"ok": None, "status": "not_configured"}

    return results


# ─── Live Mode Hot-Swap ────────────────────────────────────────

@router.post("/mode/swap")
async def hot_swap_mode(data: Dict[str, str]):
    """POST /api/mode/swap — switch demo↔live without restarting the server.

    For live mode the first *enabled* exchange with an api_key is used.
    Returns the new mode and exchange name, or an error if no live exchange
    is configured when switching to live.
    """
    mode = data.get("mode", "demo")
    if mode not in ("demo", "live"):
        raise HTTPException(400, "mode must be 'demo' or 'live'")

    if not _trader:
        raise HTTPException(503, "Trader not running")

    from ..exchanges import DemoExchange, create_live_exchange_strict, LiveExchangeError

    if mode == "demo":
        new_exchange = DemoExchange()
        exchange_name = "demo"
    else:
        try:
            new_exchange, exchange_name = create_live_exchange_strict()
        except LiveExchangeError as e:
            raise HTTPException(400, str(e))

    # Refuse to abandon real open positions on a live→demo (or live→live) switch.
    if not _trader._exchange.is_demo and _trader._open_trades:
        raise HTTPException(
            409,
            f"Close your {len(_trader._open_trades)} open live position(s) before switching modes."
        )

    # Close old exchange if it has a close() method
    old_exchange = _trader._exchange
    try:
        if hasattr(old_exchange, "close"):
            await old_exchange.close()
    except Exception:
        pass

    # Swap in the new exchange — hot-swap while the trader loop keeps running.
    _trader._exchange = new_exchange
    _trader._claude.set_exchange(new_exchange)   # Claude tool-calls must hit the new exchange
    _trader._analyses.clear()                    # stale prices from the old exchange
    _trader._open_trades.clear()                 # positions belong to the previous exchange/mode
    _trader._daily_pnl = 0.0                      # realized PnL is per-exchange
    settings.set(mode, "trading", "mode")
    settings.save()

    logger.info(f"Hot-swapped to {mode} mode (exchange: {exchange_name})")
    await _trader._broadcast("mode_changed", {"mode": mode, "exchange": exchange_name})

    return {"mode": mode, "exchange": exchange_name, "swapped": True}


@router.post("/exchange/probe")
async def probe_exchange(data: Dict[str, Any]):
    """POST /api/exchange/probe — test public + authenticated connection for a named exchange.

    Does NOT require the exchange to be enabled.  Useful during setup to verify
    API keys before going live.

    Body: {"exchange": "binance_th", "api_key": "...", "api_secret": "..."}
    Returns: public_ok, auth_ok, balances (THB/USDT/BTC), latency_ms, error.
    """
    from ..exchanges.factory import LIVE_EXCHANGES, _load
    import time as _time

    name = str(data.get("exchange") or "binance_th").lower()
    if name not in LIVE_EXCHANGES:
        raise HTTPException(400, f"Unknown exchange: {name}. Must be one of {list(LIVE_EXCHANGES)}")

    api_key    = str(data.get("api_key")    or "").strip()
    api_secret = str(data.get("api_secret") or "").strip()

    # Temporarily write keys to settings so the client picks them up,
    # then restore originals regardless of outcome.
    orig_key    = settings.get("exchanges", name, "api_key",    default="")
    orig_secret = settings.get("exchanges", name, "api_secret", default="")
    result: dict = {"exchange": name, "public_ok": False, "auth_ok": False,
                    "balance": {}, "latency_ms": None, "error": None}
    client = None
    try:
        if api_key:
            settings.set(api_key,    "exchanges", name, "api_key")
        if api_secret:
            settings.set(api_secret, "exchanges", name, "api_secret")

        client = _load(name)
        probe_sym = "BTC/THB" if name in ("bitkub", "binance_th") else "BTC/USDT"

        # 1. Public API — price fetch (no auth)
        t0 = _time.monotonic()
        ticker = await client.get_ticker(probe_sym)
        result["latency_ms"] = round((_time.monotonic() - t0) * 1000)
        result["public_ok"]  = ticker.price > 0
        result["price"]      = round(ticker.price, 2)

        # 2. Authenticated API — balance fetch (requires valid keys)
        if api_key and api_secret:
            try:
                balances = await client.get_balance()
                bal = {}
                for asset in ("THB", "USDT", "BTC", "ETH", "BNB", "XRP", "SOL"):
                    b = balances.get(asset)
                    if b:
                        bal[asset] = {"free": round(b.free, 6), "total": round(b.total, 6)}
                result["auth_ok"]  = True
                result["balance"]  = bal
            except Exception as e:
                result["auth_ok"] = False
                result["error"]   = f"Auth failed: {str(e)[:200]}"
        else:
            result["auth_ok"] = None  # keys not provided — not tested
    except Exception as e:
        result["error"] = str(e)[:200]
    finally:
        # Always restore original keys
        settings.set(orig_key,    "exchanges", name, "api_key")
        settings.set(orig_secret, "exchanges", name, "api_secret")
        if client is not None and hasattr(client, "close"):
            try:
                await client.close()
            except Exception:
                pass
    return result


@router.get("/exchange/active")
async def get_active_exchange():
    """GET /api/exchange/active — which live exchange is selected and which would
    actually be used (resolved), plus the live-readiness of each exchange."""
    from ..exchanges import LIVE_EXCHANGES, has_credentials, resolve_live_exchange
    status = {}
    for name in LIVE_EXCHANGES:
        cfg = settings.get("exchanges", name) or {}
        status[name] = {
            "enabled": bool(cfg.get("enabled")),
            "has_keys": has_credentials(name),
            "ready": bool(cfg.get("enabled")) and has_credentials(name),
        }
    return {
        "active": settings.get("exchanges", "active", default=""),
        "resolved": resolve_live_exchange(),   # what live mode would actually use
        "current": _trader._exchange.name if _trader else None,
        "mode": settings.trading_mode,
        "exchanges": status,
    }


@router.post("/exchange/active")
async def set_active_exchange(data: Dict[str, str]):
    """POST /api/exchange/active — choose which live exchange to trade on.
    Body: {"exchange": "binance"|"binance_th"|"bitkub"|"okx"}
    Does not switch mode; call /api/mode/swap to go live.
    """
    from ..exchanges import LIVE_EXCHANGES
    name = (data.get("exchange") or "").strip()
    if name not in LIVE_EXCHANGES:
        raise HTTPException(400, f"exchange must be one of {list(LIVE_EXCHANGES)}")
    settings.set(name, "exchanges", "active")
    settings.save()
    return {"active": name}


# ─── Autotrade Intelligence Endpoints ─────────────────────────

@router.get("/regimes")
async def get_market_regimes():
    """GET /api/regimes — current market regime for each tracked symbol."""
    if not _trader:
        return {}
    return {
        sym: {
            "regime":     r.regime,
            "confidence": round(r.confidence, 2),
            "adx":        round(r.adx, 1),
            "atr_pct":    round(r.atr_pct, 2),
            "trend_slope": round(r.trend_slope, 4),
            "detail":     r.detail,
        }
        for sym, r in _trader.regimes.items()
    }


@router.get("/narratives")
async def get_narratives():
    """GET /api/narratives — plain-language market summary for each tracked symbol."""
    if not _trader:
        return {}
    return dict(_trader.narratives)


@router.get("/correlations")
async def get_correlations():
    """GET /api/correlations — pairwise return-correlation matrix across symbols."""
    if not _trader:
        return {"symbols": [], "matrix": []}
    return _trader.correlation_matrix()


@router.get("/risk")
async def get_risk_state():
    """GET /api/risk — portfolio risk engine state (drawdown, heat, circuit breaker)."""
    if not _trader:
        return {}
    return _trader.risk_summary


@router.get("/rl/stats")
async def get_rl_stats():
    """GET /api/rl/stats — Reinforcement Learning bandit state per regime."""
    if not _trader:
        return {}
    stats = _trader._rl.stats
    arm_data = {}
    for regime in ["BULL_TREND", "BEAR_TREND", "RANGING", "VOLATILE", "CRASH"]:
        arm_data[regime] = _trader._rl.get_arm_stats(regime)
        arm_data[regime]["best_strategy"] = _trader._rl.select_strategy(regime)
    return {**stats, "arms": arm_data}


@router.get("/patterns")
async def get_chart_patterns(symbol: str = "BTC/USDT"):
    """GET /api/patterns?symbol=BTC/USDT — detected chart patterns for symbol."""
    if not _trader:
        raise HTTPException(503, "Trader not running")
    analysis = _trader.analyses.get(symbol)
    if not analysis:
        analysis = await _trader.analyze_symbol(symbol)
    if not analysis:
        raise HTTPException(503, f"No data for {symbol}")
    patterns = getattr(analysis, "patterns", [])
    return {
        "symbol":  symbol,
        "count":   len(patterns),
        "summary": getattr(analysis, "pattern_summary", ""),
        "patterns": [
            {
                "name":           p.name,
                "name_th":        p.name_th,
                "type":           p.pattern_type,
                "signal":         p.signal,
                "confidence":     round(p.confidence, 2),
                "description":    p.description,
                "description_th": p.description_th,
            }
            for p in patterns
        ],
    }


@router.get("/sizer/stats")
async def get_sizer_stats():
    """GET /api/sizer/stats — Kelly Criterion win-rate stats per symbol."""
    if not _trader:
        return {}
    symbols = settings.symbols
    return {sym: _trader._sizer.stats_for(sym) for sym in symbols}


@router.get("/analytics")
async def get_analytics(symbol: Optional[str] = None, days: int = 30):
    """GET /api/analytics — Sharpe, Sortino, Calmar, VaR, streaks from DB trade history."""
    from ..agent.risk_analytics import compute_metrics

    with SessionLocal() as db:
        q = db.query(Trade).filter(Trade.status == "closed", Trade.pnl_pct.isnot(None))
        if symbol:
            q = q.filter(Trade.symbol == symbol)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        q = q.filter(Trade.closed_at >= cutoff)
        trades_db = q.order_by(Trade.opened_at).all()

    if not trades_db:
        from ..agent.risk_analytics import _empty
        return {**_empty(), "symbol": symbol, "days": days, "source": "db", "note": "no closed trades"}

    trade_dicts = [{"pnl_pct": t.pnl_pct, "win": (t.pnl_pct or 0) > 0} for t in trades_db]

    # Approximate equity curve from trade outcomes
    initial = 10_000.0
    equity  = [initial]
    for t in trades_db:
        last    = equity[-1]
        equity.append(last * (1 + (t.pnl_pct or 0) / 100))

    metrics = compute_metrics(trade_dicts, equity, initial)
    return {**metrics, "symbol": symbol, "days": days, "source": "db"}


@router.get("/sentiment")
async def get_sentiment(symbol: str = "BTC/USDT"):
    """GET /api/sentiment — all market intelligence data for a symbol.

    Returns Fear & Greed, funding, OI, derivatives flow, order book
    microstructure (F1.2), on-chain metrics (F1.1), and news sentiment (F1.3).
    symbol: crypto pair, e.g. BTC/USDT
    """
    from ..data.sentiment import (
        get_fear_greed, get_funding_rate, get_open_interest,
        get_long_short_ratio, get_taker_ratio, derivatives_bias, _record_oi,
    )
    from ..data.orderbook import get_order_book
    from ..data.onchain import get_onchain
    from ..data.social import get_news_sentiment

    binance_symbol = symbol.replace("/", "")
    exchange = _trader._exchange if _trader else None

    mark_price = None
    if _trader:
        a = _trader.analyses.get(symbol)
        if a:
            mark_price = a.price

    # All sources fire concurrently
    fng_task     = get_fear_greed()
    oi_task      = get_open_interest(binance_symbol, mark_price=mark_price)
    ls_task      = get_long_short_ratio(binance_symbol)
    taker_task   = get_taker_ratio(binance_symbol)
    ob_task      = get_order_book(binance_symbol)      # F1.2
    onchain_task = get_onchain(symbol)                 # F1.1
    social_task  = get_news_sentiment(symbol)          # F1.3

    if exchange:
        funding_task = get_funding_rate(exchange, symbol)
        fng, oi, ls, taker, funding, ob, oc, soc = await asyncio.gather(
            fng_task, oi_task, ls_task, taker_task, funding_task,
            ob_task, onchain_task, social_task, return_exceptions=True)
    else:
        fng, oi, ls, taker, ob, oc, soc = await asyncio.gather(
            fng_task, oi_task, ls_task, taker_task,
            ob_task, onchain_task, social_task, return_exceptions=True)
        funding = {"symbol": symbol, "funding_rate": None, "error": "exchange unavailable"}

    fng     = fng     if not isinstance(fng,     Exception) else {"value": None, "label": None, "error": str(fng)}
    oi      = oi      if not isinstance(oi,      Exception) else {"open_interest_usdt": None, "error": str(oi)}
    ls      = ls      if not isinstance(ls,      Exception) else {"long_short_ratio": None, "error": str(ls)}
    taker   = taker   if not isinstance(taker,   Exception) else {"taker_buy_sell_ratio": None, "error": str(taker)}
    funding = funding if not isinstance(funding, Exception) else {"funding_rate": None, "error": str(funding)}
    # ob/oc/soc are dataclasses; on exception substitute a None-safe fallback
    if isinstance(ob,  Exception): ob  = None
    if isinstance(oc,  Exception): oc  = None
    if isinstance(soc, Exception): soc = None

    def _f(snap, attr):
        try:
            return getattr(snap, attr) if snap else None
        except Exception:
            return None

    # Derive trading bias from Fear & Greed
    fng_value = fng.get("value")
    if fng_value is None:   bias = "NEUTRAL"
    elif fng_value <= 25:   bias = "CONTRARIAN_BUY"
    elif fng_value <= 45:   bias = "CAUTIOUS_BUY"
    elif fng_value <= 55:   bias = "NEUTRAL"
    elif fng_value <= 75:   bias = "CAUTIOUS_SELL"
    else:                   bias = "CONTRARIAN_SELL"

    oi_change = _record_oi(binance_symbol, oi.get("open_interest_contracts"))
    deriv_label, deriv_score = derivatives_bias(
        ls.get("long_short_ratio"),
        taker.get("taker_buy_sell_ratio"),
        oi_change,
        funding.get("funding_rate"),
    )

    return {
        "symbol": symbol,
        "fear_greed": {
            "value":        fng.get("value"),
            "label":        fng.get("label"),
            "trading_bias": bias,
            "error":        fng.get("error"),
        },
        "funding_rate": {
            "rate":         funding.get("funding_rate"),
            "rate_pct":     funding.get("funding_rate_pct"),
            "next_funding": funding.get("next_funding_time"),
            "error":        funding.get("error"),
        },
        "open_interest": {
            "usdt":       oi.get("open_interest_usdt"),
            "contracts":  oi.get("open_interest_contracts"),
            "change_pct": oi_change,
            "error":      oi.get("error"),
        },
        "derivatives": {
            "long_short_ratio":     ls.get("long_short_ratio"),
            "taker_buy_sell_ratio": taker.get("taker_buy_sell_ratio"),
            "oi_change_pct":        oi_change,
            "bias":                 deriv_label,
            "score":                deriv_score,
            "error":                ls.get("error") or taker.get("error"),
        },
        # F1.2 Order Book Microstructure
        "order_book": {
            "bid_ask_imbalance": _f(ob, "bid_ask_imbalance"),
            "bid_wall_pct":      _f(ob, "bid_wall_pct"),
            "ask_wall_pct":      _f(ob, "ask_wall_pct"),
            "spread_bps":        _f(ob, "spread_bps"),
            "signal":            _f(ob, "signal") or "NEUTRAL",
            "error":             _f(ob, "error"),
        },
        # F1.1 On-chain Metrics
        "onchain": {
            "active_addr_change_pct": _f(oc, "active_addr_change_pct"),
            "tx_count_change_pct":    _f(oc, "tx_count_change_pct"),
            "hash_rate_change_pct":   _f(oc, "hash_rate_change_pct"),
            "label":                  _f(oc, "label") or "NEUTRAL",
            "score":                  _f(oc, "score"),
            "error":                  _f(oc, "error"),
        },
        # F1.3 Social / News Sentiment
        "social": {
            "label":         _f(soc, "label") or "NEUTRAL",
            "score":         _f(soc, "score"),
            "article_count": _f(soc, "article_count"),
            "bullish_count": _f(soc, "bullish_count"),
            "bearish_count": _f(soc, "bearish_count"),
            "error":         _f(soc, "error"),
        },
    }


@router.get("/trading/kill-switch")
async def kill_switch_status():
    """GET /api/trading/kill-switch — return current kill switch and dry-run state."""
    return {
        "killed":  _trader.killed   if _trader else False,
        "dry_run": _trader.dry_run  if _trader else False,
        "running": _trader._running if _trader else False,
    }


@router.post("/trading/kill-switch")
async def set_kill_switch(action: str = "activate"):
    """POST /api/trading/kill-switch?action=activate|deactivate — toggle kill switch.

    action=activate   → halt all new trades immediately.
    action=deactivate → resume trading.
    """
    if not _trader:
        raise HTTPException(503, "Trader not initialised")
    if action == "activate":
        _trader.kill()
        return {"killed": True, "message": "Kill switch activated — trading halted"}
    elif action == "deactivate":
        _trader.resume()
        return {"killed": False, "message": "Kill switch deactivated — trading resumed"}
    raise HTTPException(400, "action must be 'activate' or 'deactivate'")


@router.post("/trading/dry-run")
async def set_dry_run(enabled: bool = True):
    """POST /api/trading/dry-run?enabled=true|false — toggle paper-trading mode at runtime.

    When enabled, orders are logged but never sent to the exchange.
    """
    if not _trader:
        raise HTTPException(503, "Trader not initialised")
    _trader._dry_run = enabled
    return {
        "dry_run": _trader._dry_run,
        "message": f"Dry-run {'enabled' if enabled else 'disabled'}",
    }


@router.post("/trading/close-all")
async def close_all_positions():
    """POST /api/trading/close-all — force-close every open position at current market price."""
    if not _trader:
        raise HTTPException(503, "Trader not initialised")
    open_syms = list(_trader._open_trades.keys())
    if not open_syms:
        return {"closed": [], "message": "No open positions"}
    results = []
    for sym in open_syms:
        try:
            ticker = await _trader._exchange.fetch_ticker(sym)
            price = ticker.get("last") or ticker.get("close", 0)
            result = await _trader._close_trade(sym, price, "force_close_all")
            results.append({"symbol": sym, "ok": True, "result": result})
        except Exception as e:
            results.append({"symbol": sym, "ok": False, "error": str(e)})
    return {"closed": results, "message": f"Attempted to close {len(open_syms)} position(s)"}




@router.get("/orderbook/heatmap")
async def get_orderbook_heatmap(symbol: str = "BTC/USDT"):
    """GET /api/orderbook/heatmap?symbol=BTC/USDT
    Returns the rolling order book snapshot history for the heatmap canvas.
    """
    if not _trader:
        raise HTTPException(503, "Trader not initialised")
    hist = _trader._ob_history.get(symbol, [])
    return {
        "symbol": symbol,
        "snapshots": list(hist),
        "count": len(hist),
    }


@router.get("/journal")
async def get_journal():
    """GET /api/journal — F2.3 Trade Journal / Memory summary."""
    if not _trader:
        raise HTTPException(503, "Trader not initialised")
    return _trader._journal.summary()


@router.get("/microstructure")
async def get_microstructure(symbol: str = "BTC/USDT"):
    """GET /api/microstructure?symbol=BTC/USDT
    Returns current microstructure metrics for a symbol.
    """
    if not _trader:
        raise HTTPException(503, "Trader not initialised")
    analysis = _trader.analyses.get(symbol)
    if not analysis:
        raise HTTPException(404, "No analysis for symbol")
    return {
        "symbol":          symbol,
        "book_imbalance":  round(analysis.book_imbalance, 4),
        "whale_bid_price": analysis.whale_bid_price,
        "whale_bid_size":  analysis.whale_bid_size,
        "whale_ask_price": analysis.whale_ask_price,
        "whale_ask_size":  analysis.whale_ask_size,
        "twap_detected":   analysis.twap_detected,
        "twap_score":      round(analysis.twap_score, 2),
    }


# ─── Champion / Challenger (F5.3) ─────────────────────────────

@router.get("/champion")
async def get_champion(symbol: str = "BTC/USDT"):
    """GET /api/champion?symbol=BTC/USDT — current champion strategy for a symbol."""
    from ..agent.champion_challenger import ChampionChallenger
    cc = ChampionChallenger(symbol=symbol)
    champ = cc.champion
    if champ is None:
        return {"symbol": symbol, "champion": None, "note": "no tournament run yet"}
    return {"symbol": symbol, "champion": champ}


@router.post("/champion/tournament")
@(_limiter.limit("2/minute") if _limiter else lambda f: f)
async def run_champion_tournament(request: Request, data: Dict[str, Any] = None):
    """POST /api/champion/tournament — run Champion/Challenger tournament.

    Body (all optional):
      symbol:     BTC/USDT (default)
      days:       60       (lookback, 14-180)
      use_cache:  true     (use parquet kline cache)
    """
    from ..agent.champion_challenger import ChampionChallenger
    d = data or {}
    symbol    = str(d.get("symbol", "BTC/USDT"))
    days      = int(d.get("days", 60))
    use_cache = bool(d.get("use_cache", True))
    if days < 14 or days > 180:
        raise HTTPException(400, "days must be 14-180")
    try:
        cc = ChampionChallenger(symbol=symbol)
        result = await cc.run_tournament(days=days, use_cache=use_cache)
        return result
    except Exception as exc:
        raise HTTPException(500, str(exc))


@router.get("/model-router/stats")
async def get_model_router_stats():
    from ..agent.model_router import get_router
    return get_router().stats
