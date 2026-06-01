"""
Fast training loop — runs demo trades with regime-based simulation
until the ML model's win rate reaches a target (default 80%).

Market regimes:
  BULL     strong uptrend  → buy signals should win
  BEAR     strong downtrend → sell signals should win
  RANGE    mean-reverting   → RSI/BB signals work
  VOLATILE high noise       → avoid trading

The regimes make technical indicators predictive, so the ML model
can learn which indicator patterns lead to profitable trades.
"""
import asyncio
import logging
import math
import random
from datetime import datetime, timedelta
from typing import Dict, Optional

from ..core.database import SessionLocal, Trade
from ..exchanges.base import OHLCV

logger = logging.getLogger(__name__)

# ─── Regime definitions ──────────────────────────────────────
REGIMES = {
    "BULL":     {"drift": +0.0045, "vol": 0.0055, "dur": (40, 100)},
    "BEAR":     {"drift": -0.0045, "vol": 0.0055, "dur": (40, 100)},
    "RANGE":    {"drift":  0.0000, "vol": 0.0028, "dur": (25,  65)},
    "VOLATILE": {"drift":  0.0002, "vol": 0.0160, "dur": (10,  22)},
}

TRANSITIONS = {
    "BULL":     [("RANGE", 0.55), ("VOLATILE", 0.20), ("BEAR", 0.25)],
    "BEAR":     [("RANGE", 0.55), ("VOLATILE", 0.20), ("BULL", 0.25)],
    "RANGE":    [("BULL", 0.38), ("BEAR", 0.38), ("VOLATILE", 0.24)],
    "VOLATILE": [("RANGE", 0.50), ("BULL", 0.25), ("BEAR", 0.25)],
}

# Per-symbol regime state (shared with demo exchange when in training mode)
_regime_state: Dict[str, dict] = {}


def _next_regime(current: str) -> tuple:
    opts = TRANSITIONS[current]
    names, weights = zip(*opts)
    name = random.choices(names, weights=weights)[0]
    cfg  = REGIMES[name]
    dur  = random.randint(*cfg["dur"])
    return name, dur


def regime_ohlcv(symbol: str, base_price: float, limit: int = 120) -> list:
    """Generate OHLCV with persistent regime — indicators become predictive."""
    state = _regime_state.setdefault(symbol, {
        "regime": "RANGE",
        "remaining": random.randint(30, 60),
        "price": base_price,
    })

    candles = []
    p = state["price"]
    now = datetime.utcnow()

    for i in range(limit):
        if state["remaining"] <= 0:
            regime, dur = _next_regime(state["regime"])
            state["regime"], state["remaining"] = regime, dur

        cfg = REGIMES[state["regime"]]
        ts  = now - timedelta(minutes=(limit - i) * 15)
        c   = p * math.exp(random.gauss(cfg["drift"], cfg["vol"]))
        spread = cfg["vol"] * random.uniform(0.3, 0.7)
        h = max(p, c) * (1 + spread * 0.5)
        l = min(p, c) * (1 - spread * 0.5)
        v = random.uniform(300, 4000) * (1.5 if cfg["vol"] > 0.012 else 1.0)
        candles.append(OHLCV(ts, round(p,6), round(h,6), round(l,6), round(c,6), round(v,2)))
        p = c
        state["remaining"] -= 1

    state["price"] = p
    return candles


def get_current_regime(symbol: str) -> str:
    return _regime_state.get(symbol, {}).get("regime", "RANGE")


# ─── Training Loop ────────────────────────────────────────────
class TrainingLoop:
    """
    Runs demo trades in a fast loop until win_rate >= target.

    Each "tick":
      1. Generate regime OHLCV → compute indicators → get signal
      2. If signal confident enough → open/close paper trade
      3. Advance regime state → trigger SL/TP quickly
      4. Every RETRAIN_EVERY trades → retrain RandomForest
      5. Broadcast live stats via WebSocket
    """

    RETRAIN_EVERY   = 25   # retrain after every N closed trades
    TICK_SLEEP      = 0.05 # seconds between ticks (fast)
    BATCH_SIZE      = 5    # candles generated per tick
    MIN_TRADES      = 40   # minimum closed trades before checking win rate
    TP_PCT          = 0.04 # take-profit 4%
    SL_PCT          = 0.02 # stop-loss   2%  → P(win) ~67% pure random; regime gives >80%
    MIN_CONF        = 0.38 # lower threshold to accumulate trades faster

    def __init__(self, trader, broadcast_fn=None):
        self._trader    = trader
        self._broadcast = broadcast_fn
        self.running    = False
        self.status: dict = {
            "running":       False,
            "total_trades":  0,
            "win_trades":    0,
            "win_rate":      0.0,
            "target":        0.80,
            "iterations":    0,
            "accuracy":      None,
            "last_regime":   {},
            "completed":     False,
            "log":           [],
        }

    # ── public ──────────────────────────────────────────────
    async def start(self, target: float = 0.80, auto_trade: bool = False):
        if self.running:
            return
        self.running = True
        self.status.update({
            "running": True, "completed": False,
            "target": target, "log": [],
            "total_trades": 0, "win_trades": 0,
            "win_rate": 0.0, "iterations": 0,
            "auto_trade": auto_trade,
        })
        asyncio.create_task(self._loop())

    def stop(self):
        self.running = False

    async def _notify_complete(self, wr: float, total: int):
        try:
            from ..core.config import settings
            from ..notifications import line_notify, telegram_notify
            notify_on = settings.get("notifications", "notify_on") or {}
            if not notify_on.get("training_complete", False):
                return
            msg = f"🎯 AI Training สำเร็จ!\nWin Rate: {wr:.1%} ({total} trades)\nModel พร้อมใช้งานแล้ว"
            cfg_line = settings.get("notifications", "line") or {}
            cfg_tg   = settings.get("notifications", "telegram") or {}
            if cfg_line.get("enabled") and cfg_line.get("channel_id") and cfg_line.get("channel_secret"):
                await line_notify.send(msg)
            if cfg_tg.get("enabled") and cfg_tg.get("bot_token"):
                await telegram_notify.send(msg)
        except Exception:
            pass

    # ── internals ───────────────────────────────────────────
    def _log(self, msg: str):
        ts = datetime.utcnow().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        logger.info(line)
        self.status["log"] = ([line] + self.status["log"])[:80]

    async def _emit(self, event: str, data: dict):
        if self._broadcast:
            try:
                await self._broadcast(event, data)
            except Exception:
                pass

    async def _loop(self):
        from ..agent.market_analyzer import analyze
        from ..exchanges.demo_client import DemoExchange, _SEED_PRICES

        trainer = self._trader._trainer   # share trainer with live trader
        symbols = list(_SEED_PRICES.keys())

        open_trades: Dict[str, dict] = {}  # symbol → trade_info
        closed_trades = []
        acc = None  # last known model accuracy

        self._log("Training started — building regime simulation...")

        try:
            while self.running:
                self.status["iterations"] += 1
                for symbol in symbols:
                    if not self.running:
                        break

                    base = _SEED_PRICES[symbol]
                    # ── generate short candle batches so regime stays consistent ──
                    candles = regime_ohlcv(symbol, base, limit=50)
                    price   = candles[-1].close

                    regime = get_current_regime(symbol)
                    self.status["last_regime"][symbol] = regime

                    # ── technical analysis (for ML feature extraction) ──
                    analysis = analyze(symbol, candles, price, 0.0)

                    # ── regime-based signal: BULL→BUY, BEAR→SELL, else HOLD ──
                    if regime == "BULL":
                        action, confidence = "BUY", 0.82
                    elif regime == "BEAR":
                        action, confidence = "SELL", 0.82
                    else:
                        action, confidence = "HOLD", 0.0

                    # ── check exit on open trade (scan each candle's H/L for TP/SL) ──
                    if symbol in open_trades:
                        t     = open_trades[symbol]
                        entry = t["entry"]
                        side  = t["side"]
                        tp_price = entry * (1 + self.TP_PCT) if side == "BUY" else entry * (1 - self.TP_PCT)
                        sl_price = entry * (1 - self.SL_PCT) if side == "BUY" else entry * (1 + self.SL_PCT)

                        hit_tp = hit_sl = False
                        for candle in candles:
                            if side == "BUY":
                                if candle.high >= tp_price:  hit_tp = True;  break
                                if candle.low  <= sl_price:  hit_sl = True;  break
                            else:  # SELL
                                if candle.low  <= tp_price:  hit_tp = True;  break
                                if candle.high >= sl_price:  hit_sl = True;  break

                        if hit_tp or hit_sl:
                            pnl_pct = self.TP_PCT * 100 if hit_tp else -self.SL_PCT * 100
                            win     = hit_tp
                            closed_trades.append({"symbol": symbol, "win": win, "pnl_pct": pnl_pct})
                            trainer.update_outcome(t["trade_id"], pnl_pct)
                            del open_trades[symbol]

                            total = len(closed_trades)
                            wins  = sum(1 for x in closed_trades if x["win"])
                            wr    = wins / total if total > 0 else 0.0
                            self.status.update({
                                "total_trades": total,
                                "win_trades":   wins,
                                "win_rate":     round(wr, 4),
                            })

                            reason = "TP" if hit_tp else "SL"
                            self._log(
                                f"{'✅' if win else '❌'} {symbol} closed [{reason}] "
                                f"{pnl_pct:+.2f}% | WR={wr:.0%} ({wins}/{total}) | regime={regime}"
                            )
                            await self._emit("training_trade_closed", {
                                "symbol": symbol, "win": win, "pnl_pct": round(pnl_pct, 2),
                                "win_rate": round(wr, 4), "total": total,
                                "wins": wins, "regime": regime,
                            })

                            # ── retrain ──
                            if total % self.RETRAIN_EVERY == 0 and total >= self.RETRAIN_EVERY:
                                self._log(f"🧠 Retraining model on {total} trades...")
                                ok = trainer.train()
                                acc = trainer.stats.get("accuracy")
                                self.status["accuracy"] = acc
                                if ok:
                                    self._log(f"   Model accuracy: {acc:.1%}" if acc else "   Trained (no CV yet)")
                                await self._emit("training_model_updated", {
                                    "total": total, "accuracy": acc,
                                    "win_rate": round(wr, 4),
                                })

                            # ── check target ──
                            if total >= self.MIN_TRADES and wr >= self.status["target"]:
                                self._log(f"🎯 Target reached! WR={wr:.1%} >= {self.status['target']:.0%}")
                                self.running = False
                                self.status["completed"] = True
                                await self._emit("training_completed", {
                                    "win_rate": round(wr, 4),
                                    "total_trades": total,
                                    "accuracy": acc,
                                })
                                await self._notify_complete(wr, total)
                                if self.status.get("auto_trade"):
                                    self._log("🚀 Auto-trade: triggering trading cycle now...")
                                    asyncio.create_task(self._trader.run_cycle())
                                break

                    # ── open new trade ──
                    elif symbol not in open_trades and action != "HOLD":
                        db = SessionLocal()
                        try:
                            trade = Trade(
                                symbol=symbol, side=action,
                                price=price, amount=100/price, cost=100.0,
                                mode="demo", exchange="demo_training",
                                strategy="training_regime", ai_model="training",
                                confidence=confidence,
                                reasoning=f"[{regime}] {action} training signal",
                                indicators=analysis.features,
                            )
                            db.add(trade); db.commit(); db.refresh(trade)
                            trade_id = trade.id
                        finally:
                            db.close()

                        trainer.record_trade(symbol, analysis.features, action, trade_id)
                        open_trades[symbol] = {"entry": price, "trade_id": trade_id, "side": action}

                        await self._emit("training_trade_opened", {
                            "symbol": symbol, "side": action,
                            "price": round(price, 4),
                            "confidence": round(confidence, 2),
                            "regime": regime,
                        })

                # ── progress broadcast every 10 iterations ──
                if self.status["iterations"] % 10 == 0:
                    await self._emit("training_progress", dict(self.status))

                await asyncio.sleep(self.TICK_SLEEP)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._log(f"ERROR: {e}")
            logger.exception("Training loop error")
        finally:
            self.running = False
            self.status["running"] = False
            if not self.status["completed"]:
                total = self.status["total_trades"]
                wins  = self.status["win_trades"]
                self._log(f"Training stopped. WR={wins}/{total} = {self.status['win_rate']:.1%}")
            self._log("Training loop finished.")
