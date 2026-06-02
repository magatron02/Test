import asyncio
import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple

from .claude_analyzer import ClaudeAnalyzer
from .market_analyzer import MarketAnalysis, analyze
from .market_regime import RegimeResult, detect_regime
from .risk_engine import RiskEngine
from .position_sizer import PositionSizer
from .rl_trainer import RLTrainer
from .strategy_manager import StrategyManager, TradingSignal
from .trainer import AITrainer
from ..core.config import settings
from ..core.database import SessionLocal, Trade, Portfolio
from ..exchanges.base import BaseExchange
from ..notifications import line_notify, telegram_notify

logger = logging.getLogger(__name__)


async def _notify_trade(action: str, symbol: str, price: float, pnl_pct: float = None):
    notify_on = settings.get("notifications", "notify_on", default={})
    if action == "BUY"  and not notify_on.get("trade_open",  True):
        return
    if action in ("SELL", "CLOSE") and not notify_on.get("trade_close", True):
        return
    try:
        msg = f"{action} {symbol} @ {price:.4f}"
        if pnl_pct is not None:
            msg += f" | PnL: {pnl_pct:+.2f}%"
        await line_notify.send(msg)
        await telegram_notify.send_trade(action, symbol, price, pnl_pct)
    except Exception:
        pass


class AITrader:
    def __init__(self, exchange: BaseExchange):
        self._exchange    = exchange
        self._strategy    = StrategyManager()
        self._trainer     = AITrainer()
        self._claude      = ClaudeAnalyzer(exchange=exchange)

        # ── New autotrade components ──────────────────────────────────────
        risk_cfg = settings.get("risk", default={}) or {}
        sizer_cfg = settings.get("position_sizer", default={}) or {}
        self._risk     = RiskEngine(config=risk_cfg)
        self._sizer    = PositionSizer(config=sizer_cfg)
        self._rl       = RLTrainer(models_dir=settings.models_dir)

        self._running     = False
        self._analyses:   Dict[str, MarketAnalysis] = {}
        self._regimes:    Dict[str, RegimeResult]   = {}
        self._open_trades: Dict[str, dict] = {}
        self._broadcast_fn = None
        self._daily_pnl: float = 0.0
        self._daily_reset_date: str = ""

        # Signal funnel + agent activity (dashboard)
        self._signal_stats: Dict[str, object] = {
            "date": "", "analyzed": 0, "signals": 0, "approved": 0, "rejected": 0
        }
        self._last_signal_info: Optional[dict] = None
        self._agent_activity: Dict[str, dict] = {
            "analyzer":   {"status": "idle", "detail": "พร้อมทำงาน", "ts": None},
            "strategist": {"status": "idle", "detail": "พร้อมทำงาน", "ts": None},
            "executor":   {"status": "idle", "detail": "พร้อมทำงาน", "ts": None},
            "trainer":    {"status": "idle", "detail": "พร้อมทำงาน", "ts": None},
            "risk":       {"status": "idle", "detail": "พร้อมทำงาน", "ts": None},
        }

    def set_broadcast(self, fn):
        self._broadcast_fn = fn

    def _ensure_today(self):
        today = date.today().isoformat()
        if self._daily_reset_date != today:
            self._signal_stats = {
                "date": today, "analyzed": 0, "signals": 0, "approved": 0, "rejected": 0
            }
            self._daily_pnl = 0.0
            self._daily_reset_date = today

    def _set_agent(self, name: str, status: str, detail: str):
        if name in self._agent_activity:
            self._agent_activity[name] = {
                "status": status, "detail": detail,
                "ts": datetime.utcnow().isoformat(),
            }

    async def get_dashboard_state(self) -> dict:
        self._ensure_today()

        floating = 0.0
        for sym, trade in list(self._open_trades.items()):
            a = self._analyses.get(sym)
            if a:
                floating += (a.price - trade["price"]) * trade.get("amount", 0)

        # Mirror live trainer state into the trainer agent card
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

        # Mirror risk engine state into the risk agent card
        try:
            rs = self._risk.state
            dd = rs.current_drawdown_pct
            heat = rs.portfolio_heat_pct
            if rs.circuit_open:
                self._agent_activity["risk"]["status"] = "error"
                self._agent_activity["risk"]["detail"] = f"CIRCUIT OPEN: {rs.circuit_reason}"
            else:
                self._agent_activity["risk"]["status"] = "active" if heat > 0.05 else "idle"
                self._agent_activity["risk"]["detail"] = (
                    f"DD={dd:.1%} | Heat={heat:.1%} | Regime={rs.regime}"
                )
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
            "agents":        self._agent_activity,
            "last_signal":   self._last_signal_info,
            "open_positions": len(self._open_trades),
            "risk":          self._risk.summary(),
            "rl_stats":      self._rl.stats,
        }

    async def _broadcast(self, event: str, data: dict):
        if self._broadcast_fn:
            await self._broadcast_fn(event, data)

    # ── Market analysis ────────────────────────────────────────────────────

    async def analyze_symbol(self, symbol: str) -> Optional[MarketAnalysis]:
        try:
            ticker  = await self._exchange.get_ticker(symbol)
            candles = await self._exchange.get_ohlcv(symbol, timeframe="15m", limit=100)
            if not candles:
                return None
            cfg = settings.get("strategy", "indicators") or {}
            analysis = analyze(
                symbol, candles, ticker.price, ticker.change_24h,
                rsi_period=int(cfg.get("rsi_period", 14)),
                bb_period=int(cfg.get("bb_period",   20)),
                atr_period=int(cfg.get("atr_period", 14)),
            )
            self._analyses[symbol] = analysis

            # Detect market regime for this symbol
            regime = detect_regime(candles, analysis)
            self._regimes[symbol] = regime
            logger.debug("Regime %s: %s (conf=%.2f)", symbol, regime.regime, regime.confidence)
            return analysis
        except Exception as e:
            logger.error("Analysis failed for %s: %s", symbol, e)
            return None

    # ── Portfolio helpers ─────────────────────────────────────────────────

    async def _get_portfolio_summary(self) -> dict:
        quote = self._exchange.quote_currency
        try:
            balances = await self._exchange.get_balance()
            cash     = balances.get(quote)
            avail    = float(cash.free) if cash else 0.0
            total    = avail
            for sym, analysis in self._analyses.items():
                base = sym.split("/")[0]
                bal  = balances.get(base)
                if bal:
                    total += bal.total * analysis.price
            return {
                "cash_usdt":       avail,
                "available_usdt":  avail,
                "total_value":     total,
                "open_positions":  len(self._open_trades),
            }
        except Exception:
            return {"cash_usdt": 0, "available_usdt": 0, "total_value": 0, "open_positions": 0}

    # ── Risk checks ───────────────────────────────────────────────────────

    async def _update_risk_engine(self, portfolio: dict, regime: str):
        """Push current state into the RiskEngine."""
        equity = portfolio.get("total_value", 0)
        self._risk.update(
            equity=equity,
            daily_pnl=self._daily_pnl,
            open_trades=self._open_trades,
            regime=regime,
        )

    async def _check_risk_limits(self, symbol: str, trade_risk: float = 0.0) -> Tuple[bool, str]:
        """Gate a new BUY through the advanced risk engine."""
        allowed, reason = self._risk.can_trade(new_trade_risk=trade_risk)
        if not allowed:
            return False, reason

        # Legacy max_open_trades guard
        max_open = int(settings.get("trading", "max_open_trades", default=3))
        if len(self._open_trades) >= max_open:
            return False, "Max open trades reached"

        return True, ""

    # ── Signal generation ─────────────────────────────────────────────────

    async def _get_final_signal(
        self,
        analysis: MarketAnalysis,
        portfolio: dict,
        regime: RegimeResult,
    ) -> TradingSignal:
        ai_model  = settings.ai_model
        ml_signal = None

        if ai_model in ("ml", "hybrid") and settings.get("ai", "ml", "enabled", default=True):
            ml_signal = self._trainer.predict(analysis.features)

        # RL selects the best strategy for this regime
        rl_strategy = self._rl.select_strategy(regime.regime)
        logger.debug("RL selected strategy=%s for regime=%s", rl_strategy, regime.regime)

        if ai_model == "claude":
            sig = await self._claude.analyze(analysis, portfolio)
        elif ai_model == "rule_based":
            sig = self._strategy.get_signal(analysis)
        elif ai_model == "ml" and ml_signal:
            sig = ml_signal
        else:  # hybrid or fallback — let RL guide primary strategy
            if rl_strategy in ("dca", "trend", "mean_reversion"):
                rule_sig = self._strategy.get_signal(analysis, ml_signal)
            else:
                rule_sig = self._strategy.get_signal(analysis, ml_signal)

            if settings.claude_api_key and ai_model in ("claude", "hybrid"):
                try:
                    claude_sig = await self._claude.analyze(analysis, portfolio)
                    sig = claude_sig if claude_sig.confidence > rule_sig.confidence else rule_sig
                except Exception:
                    sig = rule_sig
            else:
                sig = rule_sig

        # In crash/volatile regimes, require higher confidence bar
        min_conf = float(settings.get("trading", "min_confidence", default=0.60))
        if regime.regime == "CRASH":
            min_conf = max(min_conf, 0.85)
        elif regime.regime == "VOLATILE":
            min_conf = max(min_conf, 0.75)

        if sig.action != "HOLD" and sig.confidence < min_conf:
            return TradingSignal(
                "HOLD", sig.confidence, sig.strategy,
                f"Confidence {sig.confidence:.0%} below regime threshold {min_conf:.0%}",
                sig.stop_loss_pct, sig.take_profit_pct,
            )

        return sig

    # ── Trade execution ───────────────────────────────────────────────────

    async def _execute_trade(
        self,
        symbol: str,
        signal: TradingSignal,
        analysis: MarketAnalysis,
        regime: RegimeResult,
        force: bool = False,
    ) -> bool:
        if symbol in self._open_trades and signal.action == "BUY":
            return False

        if symbol in self._open_trades and signal.action == "SELL":
            await self._close_trade(symbol, analysis.price, "signal_reversal")
            return True

        if signal.action not in ("BUY", "SELL"):
            return False

        if signal.action == "BUY" and not force:
            portfolio = await self._get_portfolio_summary()
            regime_mult = self._risk.get_regime_multiplier(regime.regime)

            # Smart position sizing
            size_usdt = self._sizer.compute(
                symbol=symbol,
                portfolio_value=portfolio.get("total_value", 0),
                analysis=analysis,
                available_cash=portfolio.get("available_usdt", 0),
                regime=regime.regime,
                regime_multiplier=regime_mult,
                max_position_pct=self._risk.max_position_pct,
            )

            if not self._sizer.is_tradeable(size_usdt):
                logger.info("Skip BUY %s: position too small (%.2f USDT)", symbol, size_usdt)
                return False

            # Risk engine gate
            risk_amount = size_usdt * float(signal.stop_loss_pct)
            allowed, reason = await self._check_risk_limits(symbol, trade_risk=risk_amount)
            if not allowed:
                logger.info("Skip BUY %s: %s", symbol, reason)
                self._set_agent("risk", "active", f"Block {symbol}: {reason}")
                return False

        try:
            quote    = self._exchange.quote_currency
            balances = await self._exchange.get_balance()
            cash     = balances.get(quote)

            if signal.action == "BUY":
                avail = float(cash.free) if cash else 0.0
                portfolio = await self._get_portfolio_summary()
                regime_mult = self._risk.get_regime_multiplier(regime.regime)
                amount_usdt = self._sizer.compute(
                    symbol=symbol,
                    portfolio_value=portfolio.get("total_value", avail),
                    analysis=analysis,
                    available_cash=avail,
                    regime=regime.regime,
                    regime_multiplier=regime_mult,
                    max_position_pct=self._risk.max_position_pct,
                )
                if amount_usdt < 10:
                    logger.info("Skip BUY %s: insufficient cash (%.2f USDT)", symbol, amount_usdt)
                    return False
                amount = amount_usdt / analysis.price
            else:
                base    = symbol.split("/")[0]
                pos_bal = balances.get(base)
                if not pos_bal or pos_bal.free <= 0:
                    return False
                amount = pos_bal.free

            order = await self._exchange.create_order(symbol, signal.action.lower(), amount)

            trade_data = {
                "symbol":            symbol,
                "side":              signal.action,
                "price":             order.price,
                "amount":            order.amount,
                "cost":              order.cost,
                "strategy":          signal.strategy,
                "confidence":        signal.confidence,
                "reasoning":         signal.reasoning,
                "stop_loss_price":   order.price * (1 - signal.stop_loss_pct),
                "take_profit_price": order.price * (1 + signal.take_profit_pct),
                "regime":            regime.regime,
                "opened_at":         datetime.utcnow(),
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
            self._rl.record_trade(trade_id, signal.strategy, regime.regime)

            if signal.action == "BUY":
                self._open_trades[symbol] = {**trade_data, "trade_id": trade_id}
                risk_amount = order.cost * signal.stop_loss_pct
                self._risk.register_open_trade(symbol, risk_amount)

            await self._broadcast("trade_executed", {
                "symbol":     symbol,
                "side":       signal.action,
                "price":      order.price,
                "amount":     order.amount,
                "cost":       order.cost,
                "strategy":   signal.strategy,
                "confidence": signal.confidence,
                "reasoning":  signal.reasoning,
                "mode":       settings.trading_mode,
                "regime":     regime.regime,
            })
            logger.info(
                "Trade executed: %s %s @ %.4f (conf=%.2f, regime=%s)",
                signal.action, symbol, order.price, signal.confidence, regime.regime,
            )
            self._set_agent("executor", "active",
                            f"{signal.action} {symbol} @ {order.price:.2f} [{regime.regime}]")
            await _notify_trade(signal.action, symbol, order.price)
            return True

        except Exception as e:
            logger.error("Trade execution failed for %s: %s", symbol, e)
            return False

    # ── Trade exit ────────────────────────────────────────────────────────

    async def _close_trade(self, symbol: str, price: float, reason: str) -> dict:
        if symbol not in self._open_trades:
            return {}
        trade = self._open_trades[symbol]
        entry = trade["price"]
        try:
            base    = symbol.split("/")[0]
            balances = await self._exchange.get_balance()
            bal      = balances.get(base)
            if not bal or bal.free <= 0:
                return {}
            order    = await self._exchange.create_order(symbol, "sell", bal.free)
            pnl      = (order.price - entry) * order.amount
            pnl_pct  = (order.price - entry) / entry * 100

            db = SessionLocal()
            try:
                db_trade = db.query(Trade).filter_by(id=trade["trade_id"]).first()
                if db_trade:
                    db_trade.status      = "closed"
                    db_trade.close_price = order.price
                    db_trade.pnl         = pnl
                    db_trade.pnl_pct     = pnl_pct
                    db_trade.closed_at   = datetime.utcnow()
                    db.commit()
            finally:
                db.close()

            trade_id = trade["trade_id"]
            regime   = trade.get("regime", "RANGING")

            self._trainer.update_outcome(trade_id, pnl_pct)
            self._rl.update_outcome(trade_id, pnl_pct, self._strategy)
            self._sizer.update_outcome(symbol, pnl_pct)
            self._risk.deregister_trade(symbol)

            self._daily_pnl += pnl
            del self._open_trades[symbol]

            await self._broadcast("trade_closed", {
                "symbol":      symbol,
                "reason":      reason,
                "entry_price": entry,
                "close_price": order.price,
                "pnl":         pnl,
                "pnl_pct":     pnl_pct,
                "regime":      regime,
            })
            logger.info("Closed %s: %s | PnL: %+.2f%%", symbol, reason, pnl_pct)
            await _notify_trade("SELL", symbol, order.price, pnl_pct)
            return {"price": order.price, "pnl": pnl, "pnl_pct": pnl_pct}
        except Exception as e:
            logger.error("Close failed for %s: %s", symbol, e)
            return {}

    async def _check_exit_conditions(self, symbol: str):
        if symbol not in self._open_trades:
            return
        trade    = self._open_trades[symbol]
        analysis = self._analyses.get(symbol)
        if not analysis:
            return
        price = analysis.price
        sl, tp, entry = trade["stop_loss_price"], trade["take_profit_price"], trade["price"]
        if price <= sl:
            await self._close_trade(symbol, price, f"Stop loss ({price:.4f} ≤ {sl:.4f})")
        elif price >= tp:
            await self._close_trade(symbol, price, f"Take profit ({price:.4f} ≥ {tp:.4f})")

    # ── Main cycle ────────────────────────────────────────────────────────

    async def run_cycle(self):
        self._ensure_today()
        symbols = settings.symbols

        # Aggregate regime for risk engine update (use first symbol's regime as proxy)
        dominant_regime = "RANGING"

        for symbol in symbols:
            self._set_agent("analyzer", "active", f"กำลังวิเคราะห์ {symbol}")
            analysis = await self.analyze_symbol(symbol)
            if not analysis:
                continue
            self._signal_stats["analyzed"] += 1

            regime = self._regimes.get(symbol)
            if regime is None:
                from .market_regime import RegimeResult as RR
                regime = RR("RANGING", 0.5, 20.0, 2.0, 0.0, "default")
            dominant_regime = regime.regime

            await self._check_exit_conditions(symbol)

            portfolio = await self._get_portfolio_summary()
            await self._update_risk_engine(portfolio, regime.regime)

            self._set_agent("strategist", "active", f"ประเมินสัญญาณ {symbol} [{regime.regime}]")
            signal = await self._get_final_signal(analysis, portfolio, regime)
            self._set_agent(
                "strategist", "idle",
                f"{symbol}: {signal.action} ({signal.confidence:.0%}) [{regime.regime}]",
            )
            self._last_signal_info = {
                "symbol":     symbol,
                "action":     signal.action,
                "confidence": round(signal.confidence, 2),
                "regime":     regime.regime,
                "ts":         datetime.utcnow().isoformat(),
            }

            await self._broadcast("analysis_update", {
                "symbol":      symbol,
                "price":       analysis.price,
                "change_24h":  analysis.change_24h,
                "signal":      signal.action,
                "confidence":  signal.confidence,
                "reasoning":   signal.reasoning,
                "rsi":         analysis.rsi,
                "macd_hist":   analysis.macd_hist,
                "bb_position": analysis.bb_position,
                "ema_trend":   analysis.ema_trend,
                "volatility":  analysis.volatility,
                "regime":      regime.regime,
                "regime_conf": round(regime.confidence, 2),
                "adx":         round(regime.adx, 1),
            })

            if signal.action != "HOLD":
                self._signal_stats["signals"] += 1
                executed = await self._execute_trade(symbol, signal, analysis, regime)
                if executed:
                    self._signal_stats["approved"] += 1
                else:
                    self._signal_stats["rejected"] += 1

            await asyncio.sleep(0.5)

        self._set_agent("analyzer", "idle", "วิเคราะห์ครบทุก symbol แล้ว")
        state = await self.get_dashboard_state()
        await self._broadcast("dashboard_update", state)

        if self._open_trades:
            positions = []
            for sym, trade in list(self._open_trades.items()):
                a      = self._analyses.get(sym)
                cur    = a.price if a else trade["price"]
                entry  = trade["price"]
                amount = trade.get("amount", 0)
                r      = self._regimes.get(sym)
                positions.append({
                    "symbol":        sym,
                    "entry_price":   round(entry,  6),
                    "current_price": round(cur,    6),
                    "amount":        round(amount, 6),
                    "floating_pnl":  round((cur - entry) * amount, 4),
                    "pnl_pct":       round((cur - entry) / entry * 100 if entry > 0 else 0, 2),
                    "stop_loss":     round(trade.get("stop_loss_price",   0), 6),
                    "take_profit":   round(trade.get("take_profit_price", 0), 6),
                    "strategy":      trade.get("strategy",   ""),
                    "confidence":    round(trade.get("confidence", 0), 2),
                    "regime":        trade.get("regime", r.regime if r else ""),
                })
            await self._broadcast("positions_update", {"positions": positions})

    async def start(self):
        self._running = True
        interval = settings.analysis_interval
        logger.info(
            "AI Trader started — interval=%ds, mode=%s, model=%s",
            interval, settings.trading_mode, settings.ai_model,
        )
        while self._running:
            try:
                await self.run_cycle()
            except Exception as e:
                logger.error("Trading cycle error: %s", e)
            await asyncio.sleep(interval)

    def stop(self):
        self._running = False

    # ── Properties (back-compat) ──────────────────────────────────────────

    @property
    def analyses(self) -> Dict[str, MarketAnalysis]:
        return self._analyses

    @property
    def open_trades(self) -> Dict[str, dict]:
        return self._open_trades

    @property
    def trainer_stats(self) -> dict:
        return self._trainer.stats

    @property
    def regimes(self) -> Dict[str, RegimeResult]:
        return self._regimes

    @property
    def risk_summary(self) -> dict:
        return self._risk.summary()
