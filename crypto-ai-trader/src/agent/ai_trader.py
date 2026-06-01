import asyncio
import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple

from .claude_analyzer import ClaudeAnalyzer
from .market_analyzer import MarketAnalysis, analyze
from .strategy_manager import StrategyManager, TradingSignal
from .trainer import AITrainer
from ..core.config import settings
from ..core.database import SessionLocal, Trade, Portfolio
from ..exchanges.base import BaseExchange
from ..notifications import line_notify, telegram_notify

logger = logging.getLogger(__name__)


async def _notify_trade(action: str, symbol: str, price: float, pnl_pct: float = None):
    notify_on = settings.get("notifications", "notify_on", default={})
    if action == "BUY" and not notify_on.get("trade_open", True):
        return
    if action in ("SELL", "CLOSE") and not notify_on.get("trade_close", True):
        return
    try:
        await line_notify.send(f"{action} {symbol} @ {price:.4f}" + (f" | PnL: {pnl_pct:+.2f}%" if pnl_pct is not None else ""))
        await telegram_notify.send_trade(action, symbol, price, pnl_pct)
    except Exception:
        pass


class AITrader:
    def __init__(self, exchange: BaseExchange):
        self._exchange = exchange
        self._strategy = StrategyManager()
        self._trainer = AITrainer()
        self._claude = ClaudeAnalyzer(exchange=exchange)
        self._running = False
        self._analyses: Dict[str, MarketAnalysis] = {}
        self._open_trades: Dict[str, dict] = {}   # symbol -> trade info
        self._broadcast_fn = None                  # injected by websocket handler
        self._daily_pnl: float = 0.0
        self._daily_reset_date: str = ""
        # Signal funnel + agent activity (dashboard)
        self._signal_stats: Dict[str, object] = {"date": "", "analyzed": 0, "signals": 0, "approved": 0, "rejected": 0}
        self._last_signal_info: Optional[dict] = None
        self._agent_activity: Dict[str, dict] = {
            "analyzer":   {"status": "idle", "detail": "พร้อมทำงาน", "ts": None},
            "strategist": {"status": "idle", "detail": "พร้อมทำงาน", "ts": None},
            "executor":   {"status": "idle", "detail": "พร้อมทำงาน", "ts": None},
            "trainer":    {"status": "idle", "detail": "พร้อมทำงาน", "ts": None},
        }

    def set_broadcast(self, fn):
        self._broadcast_fn = fn

    def _ensure_today(self):
        """Reset the daily signal funnel AND realized PnL when the date rolls over.
        Single source of truth so the dashboard never shows yesterday's realized PnL."""
        today = date.today().isoformat()
        if self._daily_reset_date != today:
            self._signal_stats = {"date": today, "analyzed": 0, "signals": 0, "approved": 0, "rejected": 0}
            self._daily_pnl = 0.0
            self._daily_reset_date = today

    def _set_agent(self, name: str, status: str, detail: str):
        if name in self._agent_activity:
            self._agent_activity[name] = {"status": status, "detail": detail, "ts": datetime.utcnow().isoformat()}

    async def get_dashboard_state(self) -> dict:
        """Signal funnel, today's PnL (realized + floating), and agent activity."""
        self._ensure_today()

        floating = 0.0
        for sym, trade in list(self._open_trades.items()):
            a = self._analyses.get(sym)
            if a:
                floating += (a.price - trade["price"]) * trade.get("amount", 0)

        # Reflect live trainer state into the trainer agent card
        try:
            ts = self._trainer.stats or {}
            samples = ts.get("labelled_records", 0)
            if ts.get("model_ready"):
                acc = ts.get("accuracy")
                self._agent_activity["trainer"]["detail"] = (
                    f"Accuracy {acc:.0%} | {samples} samples"
                    if acc is not None else f"{samples} samples"
                )
                self._agent_activity["trainer"]["status"] = "ready"
            else:
                self._agent_activity["trainer"]["detail"] = f"รอข้อมูล ({samples} samples)"
        except Exception:
            pass

        return {
            "funnel": {
                "analyzed": self._signal_stats["analyzed"],
                "signals":  self._signal_stats["signals"],
                "approved": self._signal_stats["approved"],
                "rejected": self._signal_stats["rejected"],
            },
            "pnl_today": {
                "realized": round(self._daily_pnl, 2),
                "floating": round(floating, 2),
                "total":    round(self._daily_pnl + floating, 2),
            },
            "agents": self._agent_activity,
            "last_signal": self._last_signal_info,
            "open_positions": len(self._open_trades),
        }

    async def _broadcast(self, event: str, data: dict):
        if self._broadcast_fn:
            await self._broadcast_fn(event, data)

    async def analyze_symbol(self, symbol: str) -> Optional[MarketAnalysis]:
        try:
            ticker = await self._exchange.get_ticker(symbol)
            candles = await self._exchange.get_ohlcv(symbol, timeframe="15m", limit=100)
            if not candles:
                return None
            cfg = settings.get("strategy", "indicators") or {}
            analysis = analyze(
                symbol, candles, ticker.price, ticker.change_24h,
                rsi_period=int(cfg.get("rsi_period", 14)),
                bb_period=int(cfg.get("bb_period", 20)),
                atr_period=int(cfg.get("atr_period", 14)),
            )
            self._analyses[symbol] = analysis
            return analysis
        except Exception as e:
            logger.error(f"Analysis failed for {symbol}: {e}")
            return None

    async def _get_portfolio_summary(self) -> dict:
        try:
            balances = await self._exchange.get_balance()
            cash = balances.get("USDT")
            prices = {sym: a.price for sym, a in self._analyses.items()}
            total = float(cash.free) if cash else 0
            for sym, analysis in self._analyses.items():
                base = sym.split("/")[0]
                bal = balances.get(base)
                if bal:
                    total += bal.total * analysis.price
            return {
                "cash_usdt": float(cash.free) if cash else 0,
                "total_value": total,
                "open_positions": len(self._open_trades),
            }
        except Exception:
            return {"cash_usdt": 0, "total_value": 0, "open_positions": 0}

    async def _check_risk_limits(self) -> Tuple[bool, str]:
        """Check daily loss limit and max open trades. Returns (allowed, reason)."""
        self._ensure_today()

        max_daily_loss_pct = float(settings.get("trading", "max_daily_loss_pct", default=0.05))
        max_open_trades = int(settings.get("trading", "max_open_trades", default=3))

        portfolio = await self._get_portfolio_summary()
        portfolio_value = portfolio.get("total_value", 0) or 1.0

        if self._daily_pnl <= -(portfolio_value * max_daily_loss_pct):
            return False, "Daily loss limit reached"

        if len(self._open_trades) >= max_open_trades:
            return False, "Max open trades reached"

        return True, ""

    async def _get_final_signal(self, analysis: MarketAnalysis, portfolio: dict) -> TradingSignal:
        ai_model = settings.ai_model
        ml_signal = None

        if ai_model in ("ml", "hybrid") and settings.get("ai", "ml", "enabled", default=True):
            ml_signal = self._trainer.predict(analysis.features)

        if ai_model == "claude":
            sig = await self._claude.analyze(analysis, portfolio)
        elif ai_model == "rule_based":
            sig = self._strategy.get_signal(analysis)
        elif ai_model == "ml" and ml_signal:
            sig = ml_signal
        else:  # hybrid or fallback
            rule_sig = self._strategy.get_signal(analysis, ml_signal)
            if settings.claude_api_key and ai_model in ("claude", "hybrid"):
                try:
                    claude_sig = await self._claude.analyze(analysis, portfolio)
                    # blend: take higher confidence signal
                    if claude_sig.confidence > rule_sig.confidence:
                        sig = claude_sig
                    else:
                        sig = rule_sig
                except Exception:
                    sig = rule_sig
            else:
                sig = rule_sig

        return sig

    async def _execute_trade(self, symbol: str, signal: TradingSignal, analysis: MarketAnalysis, force: bool = False) -> bool:
        """Execute a BUY/SELL. Returns True only when an order is actually placed."""
        if symbol in self._open_trades and signal.action == "BUY":
            return False  # Already have position

        # If we hold a BUY position and get a SELL signal, close it properly
        if symbol in self._open_trades and signal.action == "SELL":
            await self._close_trade(symbol, analysis.price, "signal_reversal")
            return True

        if signal.action not in ("BUY", "SELL"):
            return False

        # Check risk limits before executing any trade (skipped for manual/forced trades)
        if signal.action == "BUY" and not force:
            allowed, reason = await self._check_risk_limits()
            if not allowed:
                logger.info(f"Skip BUY {symbol}: {reason}")
                return False

        try:
            balances = await self._exchange.get_balance()
            cash = balances.get("USDT")

            if signal.action == "BUY":
                avail = float(cash.free) if cash else 0
                risk_pct = float(settings.get("trading", "risk_per_trade_pct", default=0.02))
                portfolio = await self._get_portfolio_summary()
                portfolio_value = portfolio.get("total_value", avail) or avail
                amount_usdt = min(portfolio_value * risk_pct, avail * 0.95)
                if amount_usdt < 10:
                    logger.info(f"Skip BUY {symbol}: insufficient cash ({amount_usdt:.2f} USDT)")
                    return False
                amount = amount_usdt / analysis.price
            else:
                base = symbol.split("/")[0]
                pos_bal = balances.get(base)
                if not pos_bal or pos_bal.free <= 0:
                    return False
                amount = pos_bal.free

            order = await self._exchange.create_order(symbol, signal.action.lower(), amount)

            trade_data = {
                "symbol": symbol,
                "side": signal.action,
                "price": order.price,
                "amount": order.amount,
                "cost": order.cost,
                "strategy": signal.strategy,
                "confidence": signal.confidence,
                "reasoning": signal.reasoning,
                "stop_loss_price": order.price * (1 - signal.stop_loss_pct),
                "take_profit_price": order.price * (1 + signal.take_profit_pct),
                "opened_at": datetime.utcnow(),
            }

            db = SessionLocal()
            try:
                trade = Trade(
                    symbol=symbol,
                    side=signal.action,
                    price=order.price,
                    amount=order.amount,
                    cost=order.cost,
                    mode=settings.trading_mode,
                    exchange=self._exchange.name,
                    strategy=signal.strategy,
                    ai_model=settings.ai_model,
                    confidence=signal.confidence,
                    reasoning=signal.reasoning,
                    indicators=analysis.features,
                )
                db.add(trade)
                db.commit()
                db.refresh(trade)
                trade_id = trade.id
            finally:
                db.close()

            self._trainer.record_trade(symbol, analysis.features, signal.action, trade_id)
            if signal.action == "BUY":
                self._open_trades[symbol] = {**trade_data, "trade_id": trade_id}

            await self._broadcast("trade_executed", {
                "symbol": symbol,
                "side": signal.action,
                "price": order.price,
                "amount": order.amount,
                "cost": order.cost,
                "strategy": signal.strategy,
                "confidence": signal.confidence,
                "reasoning": signal.reasoning,
                "mode": settings.trading_mode,
            })
            logger.info(f"Trade executed: {signal.action} {symbol} @ {order.price:.4f} (conf={signal.confidence:.2f})")
            self._set_agent("executor", "active", f"{signal.action} {symbol} @ {order.price:.2f}")
            await _notify_trade(signal.action, symbol, order.price)
            return True

        except Exception as e:
            logger.error(f"Trade execution failed for {symbol}: {e}")
            return False

    async def _close_trade(self, symbol: str, price: float, reason: str) -> dict:
        """Close an open position at the given price. Returns PnL dict on success."""
        if symbol not in self._open_trades:
            return {}
        trade = self._open_trades[symbol]
        entry = trade["price"]
        try:
            base = symbol.split("/")[0]
            balances = await self._exchange.get_balance()
            bal = balances.get(base)
            if not bal or bal.free <= 0:
                return {}
            order = await self._exchange.create_order(symbol, "sell", bal.free)
            pnl = (order.price - entry) * order.amount
            pnl_pct = (order.price - entry) / entry * 100

            db = SessionLocal()
            try:
                db_trade = db.query(Trade).filter_by(id=trade["trade_id"]).first()
                if db_trade:
                    db_trade.status = "closed"
                    db_trade.close_price = order.price
                    db_trade.pnl = pnl
                    db_trade.pnl_pct = pnl_pct
                    db_trade.closed_at = datetime.utcnow()
                    db.commit()
            finally:
                db.close()

            self._trainer.update_outcome(trade["trade_id"], pnl_pct)
            self._daily_pnl += pnl
            del self._open_trades[symbol]

            await self._broadcast("trade_closed", {
                "symbol": symbol, "reason": reason,
                "entry_price": entry, "close_price": order.price,
                "pnl": pnl, "pnl_pct": pnl_pct,
            })
            logger.info(f"Closed {symbol}: {reason} | PnL: {pnl_pct:+.2f}%")
            await _notify_trade("SELL", symbol, order.price, pnl_pct)
            return {"price": order.price, "pnl": pnl, "pnl_pct": pnl_pct}
        except Exception as e:
            logger.error(f"Close failed for {symbol}: {e}")
            return {}

    async def _check_exit_conditions(self, symbol: str):
        if symbol not in self._open_trades:
            return
        trade = self._open_trades[symbol]
        analysis = self._analyses.get(symbol)
        if not analysis:
            return
        price = analysis.price
        sl, tp, entry = trade["stop_loss_price"], trade["take_profit_price"], trade["price"]
        if price <= sl:
            await self._close_trade(symbol, price, f"Stop loss hit ({price:.4f} <= {sl:.4f})")
        elif price >= tp:
            await self._close_trade(symbol, price, f"Take profit hit ({price:.4f} >= {tp:.4f})")

    async def run_cycle(self):
        self._ensure_today()
        symbols = settings.symbols
        for symbol in symbols:
            self._set_agent("analyzer", "active", f"กำลังวิเคราะห์ {symbol}")
            analysis = await self.analyze_symbol(symbol)
            if not analysis:
                continue
            self._signal_stats["analyzed"] += 1

            await self._check_exit_conditions(symbol)

            portfolio = await self._get_portfolio_summary()
            self._set_agent("strategist", "active", f"ประเมินสัญญาณ {symbol}")
            signal = await self._get_final_signal(analysis, portfolio)
            self._set_agent("strategist", "idle", f"{symbol}: {signal.action} ({signal.confidence:.0%})")
            self._last_signal_info = {
                "symbol": symbol, "action": signal.action,
                "confidence": round(signal.confidence, 2),
                "ts": datetime.utcnow().isoformat(),
            }

            await self._broadcast("analysis_update", {
                "symbol": symbol,
                "price": analysis.price,
                "change_24h": analysis.change_24h,
                "signal": signal.action,
                "confidence": signal.confidence,
                "reasoning": signal.reasoning,
                "rsi": analysis.rsi,
                "macd_hist": analysis.macd_hist,
                "bb_position": analysis.bb_position,
                "ema_trend": analysis.ema_trend,
                "volatility": analysis.volatility,
            })

            if signal.action != "HOLD":
                self._signal_stats["signals"] += 1
                executed = await self._execute_trade(symbol, signal, analysis)
                if executed:
                    self._signal_stats["approved"] += 1
                else:
                    self._signal_stats["rejected"] += 1

            await asyncio.sleep(0.5)

        self._set_agent("analyzer", "idle", "วิเคราะห์ครบทุก symbol แล้ว")
        state = await self.get_dashboard_state()
        await self._broadcast("dashboard_update", state)
        # Also push open positions so the positions table auto-refreshes
        if self._open_trades:
            positions = []
            for sym, trade in list(self._open_trades.items()):
                a = self._analyses.get(sym)
                cur = a.price if a else trade["price"]
                entry = trade["price"]
                amount = trade.get("amount", 0)
                positions.append({
                    "symbol":        sym,
                    "entry_price":   round(entry, 6),
                    "current_price": round(cur, 6),
                    "amount":        round(amount, 6),
                    "floating_pnl":  round((cur - entry) * amount, 4),
                    "pnl_pct":       round((cur - entry) / entry * 100 if entry > 0 else 0, 2),
                    "stop_loss":     round(trade.get("stop_loss_price", 0), 6),
                    "take_profit":   round(trade.get("take_profit_price", 0), 6),
                    "strategy":      trade.get("strategy", ""),
                    "confidence":    round(trade.get("confidence", 0), 2),
                })
            await self._broadcast("positions_update", {"positions": positions})

    async def start(self):
        self._running = True
        interval = settings.analysis_interval
        logger.info(f"AI Trader started — interval={interval}s, mode={settings.trading_mode}, model={settings.ai_model}")
        while self._running:
            try:
                await self.run_cycle()
            except Exception as e:
                logger.error(f"Trading cycle error: {e}")
            await asyncio.sleep(interval)

    def stop(self):
        self._running = False

    @property
    def analyses(self) -> Dict[str, MarketAnalysis]:
        return self._analyses

    @property
    def open_trades(self) -> Dict[str, dict]:
        return self._open_trades

    @property
    def trainer_stats(self) -> dict:
        return self._trainer.stats
