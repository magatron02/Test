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
        self._price_history: Dict[str, list] = {}   # symbol → recent closes (HRP/pairs)
        self._hrp_weights:   Dict[str, float] = {}  # symbol → correlation-aware weight
        self._broadcast_fn = None
        self._daily_pnl: float = 0.0
        self._daily_reset_date: str = ""

        # Dry-run: paper trade without hitting the exchange
        self._dry_run: bool = bool(settings.get("trading", "dry_run", default=False))
        # Kill switch: halts all new trades when activated
        self._killed: bool  = False

        # Signal funnel + agent activity (dashboard)
        self._signal_stats: Dict[str, object] = {
            "date": "", "analyzed": 0, "signals": 0, "approved": 0, "rejected": 0
        }
        self._last_signal_info: Optional[dict] = None
        # Attribution: which sub-signals drove the last decision (F5.4)
        self._signal_attribution: Optional[dict] = None
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

            # Maintain a rolling close-price history for HRP allocation & pairs
            closes = [c.close for c in candles]
            self._price_history[symbol] = closes[-200:]

            # Detect market regime for this symbol
            regime = detect_regime(candles, analysis)
            self._regimes[symbol] = regime
            analysis.market_regime = regime.regime  # plumb regime into the analysis so AI prompts see it
            logger.debug("Regime %s: %s (conf=%.2f)", symbol, regime.regime, regime.confidence)
            return analysis
        except Exception as e:
            logger.error("Analysis failed for %s: %s", symbol, e)
            return None

    # ── Correlation-aware allocation (HRP, ML4T Ch.13) ─────────────────────

    def _update_hrp_weights(self):
        """Recompute Hierarchical Risk Parity weights across tracked symbols.

        Converts each symbol's close history to a return series, then runs HRP
        so correlated assets (e.g. BTC+ETH) collectively get less weight than
        independent ones. Stored as a per-symbol multiplier for position sizing.
        """
        try:
            import numpy as np
            from .hrp_allocator import allocate_capital

            returns_by_symbol = {}
            for sym, closes in self._price_history.items():
                if len(closes) >= 30:
                    arr = np.array(closes, dtype=float)
                    rets = np.diff(arr) / np.where(arr[:-1] != 0, arr[:-1], 1)
                    returns_by_symbol[sym] = list(rets)
            if len(returns_by_symbol) < 2:
                return
            alloc = allocate_capital(1.0, returns_by_symbol, max_weight=0.40)
            self._hrp_weights = {s: d["weight"] for s, d in alloc.items()}
            logger.debug("HRP weights updated: %s", self._hrp_weights)
        except Exception as e:
            logger.debug("HRP weight update skipped: %s", e)

    def _hrp_multiplier(self, symbol: str) -> float:
        """Return a sizing multiplier from HRP weight vs equal-weight baseline.

        weight == equal-weight → 1.0; over-weighted symbol → >1; correlated /
        crowded symbol → <1. Clamped to [0.4, 1.6] so it tilts, never dominates.
        """
        if not self._hrp_weights or symbol not in self._hrp_weights:
            return 1.0
        n = len(self._hrp_weights)
        equal = 1.0 / n if n else 1.0
        if equal <= 0:
            return 1.0
        return max(0.4, min(self._hrp_weights[symbol] / equal, 1.6))

    def cointegration_pairs(self) -> list:
        """Scan tracked symbols for cointegrated pairs (ML4T Ch.9 stat-arb)."""
        try:
            from .cointegration import find_cointegrated_pairs
            prices = {s: c for s, c in self._price_history.items() if len(c) >= 50}
            if len(prices) < 2:
                return []
            return find_cointegrated_pairs(prices)
        except Exception as e:
            logger.debug("Cointegration scan skipped: %s", e)
            return []

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

        # Correlation guard — avoid stacking highly-correlated positions
        ok, corr_reason = self._check_correlation_guard(symbol)
        if not ok:
            return False, corr_reason

        # Legacy max_open_trades guard
        max_open = int(settings.get("trading", "max_open_trades", default=3))
        if len(self._open_trades) >= max_open:
            return False, "Max open trades reached"

        return True, ""

    def _returns_for(self, symbol: str) -> list:
        """Convert tracked close history to a simple return series."""
        closes = self._price_history.get(symbol) or []
        if len(closes) < 6:
            return []
        return [
            (closes[i] - closes[i - 1]) / closes[i - 1]
            for i in range(1, len(closes))
            if closes[i - 1]
        ]

    def _check_correlation_guard(self, symbol: str) -> Tuple[bool, str]:
        """Block a BUY too correlated with currently-held symbols (F3.2)."""
        held = [s for s in self._open_trades if s != symbol]
        if not held:
            return True, ""
        candidate = self._returns_for(symbol)
        if len(candidate) < 5:
            return True, ""
        portfolio_returns = {}
        for s in held:
            rets = self._returns_for(s)
            if len(rets) >= 5:
                portfolio_returns[s] = rets
        allowed, reason, avg_corr = self._risk.check_correlation(candidate, portfolio_returns)
        if not allowed:
            self._set_agent("risk", "active", f"Block {symbol}: {reason}")
        return allowed, reason

    # ── Signal generation ─────────────────────────────────────────────────

    async def _get_final_signal(
        self,
        analysis: MarketAnalysis,
        portfolio: dict,
        regime: RegimeResult,
    ) -> TradingSignal:
        ai_model  = settings.ai_model
        ml_signal = None

        # Attribution: record every sub-signal that contributes to the decision
        components: Dict[str, Optional[dict]] = {
            "ml": None, "rule": None, "claude": None, "multi_model": None,
        }

        def _capture(name, s, strategy=None):
            if s is None:
                return
            entry = {"action": s.action, "confidence": round(s.confidence, 3)}
            if strategy:
                entry["strategy"] = strategy
            components[name] = entry

        if ai_model in ("ml", "hybrid") and settings.get("ai", "ml", "enabled", default=True):
            ml_signal = self._trainer.predict(analysis.features)
            _capture("ml", ml_signal)

        # RL selects the best strategy for this regime
        rl_strategy = self._rl.select_strategy(regime.regime)
        logger.debug("RL selected strategy=%s for regime=%s", rl_strategy, regime.regime)

        chosen = ai_model
        if ai_model == "claude":
            sig = await self._claude.analyze(analysis, portfolio)
            _capture("claude", sig)
            chosen = "claude"
        elif ai_model == "rule_based":
            sig = self._strategy.get_signal(analysis)
            _capture("rule", sig, strategy=sig.strategy)
            chosen = "rule_based"
        elif ai_model == "ml" and ml_signal:
            sig = ml_signal
            chosen = "ml"
        elif ai_model == "multi_model":
            from .multi_model import multi_model_signal
            sig = await multi_model_signal(analysis)
            _capture("multi_model", sig)
            chosen = "multi_model"
        else:  # hybrid or fallback — let RL guide the primary strategy
            # RL picks the strategy best suited to the current regime; dispatch
            # to that single strategy instead of the blended hybrid (which lets
            # conflicting sub-strategies cancel each other out to HOLD).
            rule_sig = self._strategy.signal_for_strategy(rl_strategy, analysis, ml_signal)
            _capture("rule", rule_sig, strategy=rl_strategy)

            if settings.claude_api_key and ai_model in ("claude", "hybrid"):
                try:
                    claude_sig = await self._claude.analyze(analysis, portfolio)
                    _capture("claude", claude_sig)
                    if claude_sig.confidence > rule_sig.confidence:
                        sig, chosen = claude_sig, "claude"
                    else:
                        sig, chosen = rule_sig, f"rule:{rl_strategy}"
                except Exception:
                    sig, chosen = rule_sig, f"rule:{rl_strategy}"
            else:
                sig, chosen = rule_sig, f"rule:{rl_strategy}"

        # In crash/volatile regimes, require higher confidence bar
        min_conf = float(settings.get("trading", "min_confidence", default=0.60))
        if regime.regime == "CRASH":
            min_conf = max(min_conf, 0.85)
        elif regime.regime == "VOLATILE":
            min_conf = max(min_conf, 0.75)

        gated = sig.action != "HOLD" and sig.confidence < min_conf
        final_sig = sig
        if gated:
            final_sig = TradingSignal(
                "HOLD", sig.confidence, sig.strategy,
                f"Confidence {sig.confidence:.0%} below regime threshold {min_conf:.0%}",
                sig.stop_loss_pct, sig.take_profit_pct,
            )

        self._signal_attribution = {
            "mode":        ai_model,
            "chosen":      chosen,
            "rl_strategy": rl_strategy,
            "regime":      regime.regime,
            "min_conf":    round(min_conf, 2),
            "gated":       gated,
            "components":  components,
            "final":       {"action": final_sig.action,
                            "confidence": round(final_sig.confidence, 3)},
        }
        return final_sig

    @staticmethod
    def _attribution_summary(attr: Optional[dict]) -> str:
        """Compact one-line attribution for persisting alongside a trade."""
        if not attr:
            return ""
        parts = []
        for name, c in (attr.get("components") or {}).items():
            if c:
                parts.append(f"{name}={c['action']}@{c['confidence']:.2f}")
        tag = " GATED" if attr.get("gated") else ""
        return (f"[attr chosen={attr.get('chosen')} "
                f"{' '.join(parts)} rl={attr.get('rl_strategy')} "
                f"{attr.get('regime')}{tag}]")

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
            hrp_cap = self._risk.max_position_pct * self._hrp_multiplier(symbol)

            # Smart position sizing
            size_usdt = self._sizer.compute(
                symbol=symbol,
                portfolio_value=portfolio.get("total_value", 0),
                analysis=analysis,
                available_cash=portfolio.get("available_usdt", 0),
                regime=regime.regime,
                regime_multiplier=regime_mult,
                max_position_pct=hrp_cap,
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
                hrp_cap = self._risk.max_position_pct * self._hrp_multiplier(symbol)
                amount_usdt = self._sizer.compute(
                    symbol=symbol,
                    portfolio_value=portfolio.get("total_value", avail),
                    analysis=analysis,
                    available_cash=avail,
                    regime=regime.regime,
                    regime_multiplier=regime_mult,
                    max_position_pct=hrp_cap,
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

            if self._dry_run:
                import uuid
                from ..exchanges.base import Order as _Order
                order = _Order(
                    id=f"dry_{uuid.uuid4().hex[:8]}",
                    symbol=symbol,
                    side=signal.action.lower(),
                    type="market",
                    price=analysis.price,
                    amount=amount,
                    cost=analysis.price * amount,
                    status="closed",
                )
                logger.info("[DRY-RUN] Paper %s %s %.6f @ %.4f",
                            signal.action, symbol, amount, analysis.price)
            else:
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
                "high_water":        order.price,
                "trailing_sl":       None,
            }

            db = SessionLocal()
            try:
                attr_summary = self._attribution_summary(self._signal_attribution)
                reasoning = (f"{signal.reasoning} {attr_summary}".strip()
                             if attr_summary else signal.reasoning)
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
                    reasoning=reasoning,
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
                "symbol":      symbol,
                "side":        signal.action,
                "price":       order.price,
                "amount":      order.amount,
                "cost":        order.cost,
                "strategy":    signal.strategy,
                "confidence":  signal.confidence,
                "reasoning":   signal.reasoning,
                "mode":        settings.trading_mode,
                "regime":      regime.regime,
                "attribution": self._signal_attribution,
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
            base = symbol.split("/")[0]
            if self._dry_run:
                import uuid
                from ..exchanges.base import Order as _Order
                amt = trade.get("amount", 0.0)
                order = _Order(
                    id=f"dry_{uuid.uuid4().hex[:8]}",
                    symbol=symbol,
                    side="sell",
                    type="market",
                    price=price,
                    amount=amt,
                    cost=price * amt,
                    status="closed",
                )
                logger.info("[DRY-RUN] Paper CLOSE %s @ %.4f (%s)", symbol, price, reason)
            else:
                balances = await self._exchange.get_balance()
                bal      = balances.get(base)
                if not bal or bal.free <= 0:
                    return {}
                order = await self._exchange.create_order(symbol, "sell", bal.free)
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
        price  = analysis.price
        sl     = trade["stop_loss_price"]
        tp     = trade["take_profit_price"]
        entry  = trade["price"]
        opened = trade.get("opened_at", datetime.utcnow())

        # ── 1. Fixed stop loss ────────────────────────────────────────────
        if price <= sl:
            await self._close_trade(symbol, price, f"Stop loss ({price:.4f} ≤ {sl:.4f})")
            return

        # ── 2. Trailing stop ──────────────────────────────────────────────
        trail_cfg = settings.get("strategy", "trailing_stop") or {}
        if trail_cfg.get("enabled"):
            trail_pct      = float(trail_cfg.get("pct", 0.02))
            trail_act_pct  = float(trail_cfg.get("activate_pct", 0.01))
            hw = max(trade.get("high_water", entry), price)
            trade["high_water"] = hw
            cur_profit = (hw - entry) / entry
            if cur_profit >= trail_act_pct:
                new_trail = hw * (1 - trail_pct)
                old_trail = trade.get("trailing_sl")
                if old_trail is None or new_trail > old_trail:
                    trade["trailing_sl"] = new_trail
            trail_sl = trade.get("trailing_sl")
            if trail_sl and price <= trail_sl:
                await self._close_trade(symbol, price, f"Trailing stop ({price:.4f} ≤ {trail_sl:.4f})")
                return

        # ── 3. ROI table (time-based take profit) ─────────────────────────
        roi_tbl = settings.get("strategy", "roi_table") or {}
        if roi_tbl:
            roi_sorted = sorted(
                [(int(k), float(v)) for k, v in roi_tbl.items()],
                reverse=True,
            )
            age_minutes = (datetime.utcnow() - opened).total_seconds() / 60.0
            roi_thresh = None
            for min_age, roi_pct in roi_sorted:
                if age_minutes >= min_age:
                    roi_thresh = roi_pct
                    break
            if roi_thresh is not None:
                cur_pnl = (price - entry) / entry
                if cur_pnl >= roi_thresh:
                    await self._close_trade(symbol, price,
                        f"ROI table: {cur_pnl:.1%} ≥ {roi_thresh:.1%} at {age_minutes:.0f}min")
                    return

        # ── 4. Fixed take profit ──────────────────────────────────────────
        if price >= tp:
            await self._close_trade(symbol, price, f"Take profit ({price:.4f} ≥ {tp:.4f})")

    # ── Main cycle ────────────────────────────────────────────────────────

    async def run_cycle(self):
        self._ensure_today()
        if self._killed:
            logger.warning("Kill switch active — trading cycle skipped")
            return
        symbols = settings.symbols

        # Refresh correlation-aware HRP weights from last cycle's price history
        self._update_hrp_weights()

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
                "symbol":      symbol,
                "action":      signal.action,
                "confidence":  round(signal.confidence, 2),
                "regime":      regime.regime,
                "ts":          datetime.utcnow().isoformat(),
                "attribution": self._signal_attribution,
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

    def kill(self):
        """Activate kill switch — no new trades until resume() is called."""
        self._killed = True
        logger.warning("KILL SWITCH ACTIVATED — all new trading halted")

    def resume(self):
        """Deactivate kill switch — allow trading to resume."""
        self._killed = False
        logger.info("Kill switch deactivated — trading resumed")

    @property
    def dry_run(self) -> bool:
        return self._dry_run

    @property
    def killed(self) -> bool:
        return self._killed

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
