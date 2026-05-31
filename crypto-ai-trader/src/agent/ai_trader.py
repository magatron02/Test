import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional

from .claude_analyzer import ClaudeAnalyzer
from .market_analyzer import MarketAnalysis, analyze
from .strategy_manager import StrategyManager, TradingSignal
from .trainer import AITrainer
from ..core.config import settings
from ..core.database import SessionLocal, Trade, Portfolio
from ..exchanges.base import BaseExchange

logger = logging.getLogger(__name__)


class AITrader:
    def __init__(self, exchange: BaseExchange):
        self._exchange = exchange
        self._strategy = StrategyManager()
        self._trainer = AITrainer()
        self._claude = ClaudeAnalyzer()
        self._running = False
        self._analyses: Dict[str, MarketAnalysis] = {}
        self._open_trades: Dict[str, dict] = {}   # symbol -> trade info
        self._broadcast_fn = None                  # injected by websocket handler

    def set_broadcast(self, fn):
        self._broadcast_fn = fn

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

    def _get_final_signal(self, analysis: MarketAnalysis, portfolio: dict) -> TradingSignal:
        ai_model = settings.ai_model
        ml_signal = None

        if ai_model in ("ml", "hybrid") and settings.get("ai", "ml", "enabled", default=True):
            ml_signal = self._trainer.predict(analysis.features)

        if ai_model == "claude":
            sig = self._claude.analyze(analysis, portfolio)
        elif ai_model == "rule_based":
            sig = self._strategy.get_signal(analysis)
        elif ai_model == "ml" and ml_signal:
            sig = ml_signal
        else:  # hybrid or fallback
            rule_sig = self._strategy.get_signal(analysis, ml_signal)
            if settings.claude_api_key and ai_model in ("claude", "hybrid"):
                try:
                    claude_sig = self._claude.analyze(analysis, portfolio)
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

    async def _execute_trade(self, symbol: str, signal: TradingSignal, analysis: MarketAnalysis):
        if symbol in self._open_trades and signal.action == "BUY":
            return  # Already have position

        if signal.action not in ("BUY", "SELL"):
            return

        try:
            balances = await self._exchange.get_balance()
            cash = balances.get("USDT")
            max_pct = float(settings.get("trading", "max_position_pct", default=0.15))

            if signal.action == "BUY":
                avail = float(cash.free) if cash else 0
                amount_usdt = avail * max_pct
                if amount_usdt < 10:
                    logger.info(f"Skip BUY {symbol}: insufficient cash ({amount_usdt:.2f} USDT)")
                    return
                amount = amount_usdt / analysis.price
            else:
                base = symbol.split("/")[0]
                pos_bal = balances.get(base)
                if not pos_bal or pos_bal.free <= 0:
                    return
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

        except Exception as e:
            logger.error(f"Trade execution failed for {symbol}: {e}")

    async def _check_exit_conditions(self, symbol: str):
        if symbol not in self._open_trades:
            return
        trade = self._open_trades[symbol]
        analysis = self._analyses.get(symbol)
        if not analysis:
            return

        price = analysis.price
        sl = trade["stop_loss_price"]
        tp = trade["take_profit_price"]
        entry = trade["price"]

        should_close = False
        close_reason = ""

        if price <= sl:
            should_close = True
            close_reason = f"Stop loss hit ({price:.4f} <= {sl:.4f})"
        elif price >= tp:
            should_close = True
            close_reason = f"Take profit hit ({price:.4f} >= {tp:.4f})"

        if should_close:
            try:
                base = symbol.split("/")[0]
                balances = await self._exchange.get_balance()
                bal = balances.get(base)
                if bal and bal.free > 0:
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
                    del self._open_trades[symbol]

                    await self._broadcast("trade_closed", {
                        "symbol": symbol,
                        "reason": close_reason,
                        "entry_price": entry,
                        "close_price": order.price,
                        "pnl": pnl,
                        "pnl_pct": pnl_pct,
                    })
                    logger.info(f"Closed {symbol}: {close_reason} | PnL: {pnl_pct:+.2f}%")
            except Exception as e:
                logger.error(f"Exit failed for {symbol}: {e}")

    async def run_cycle(self):
        symbols = settings.symbols
        for symbol in symbols:
            analysis = await self.analyze_symbol(symbol)
            if not analysis:
                continue

            await self._check_exit_conditions(symbol)

            portfolio = await self._get_portfolio_summary()
            signal = self._get_final_signal(analysis, portfolio)

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
                await self._execute_trade(symbol, signal, analysis)

            await asyncio.sleep(0.5)

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
