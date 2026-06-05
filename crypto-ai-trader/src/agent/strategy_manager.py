import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

from .market_analyzer import MarketAnalysis
from ..core.config import settings
from ..core.persistence import atomic_write_json, safe_read_json

logger = logging.getLogger(__name__)


@dataclass
class TradingSignal:
    action: str          # BUY | SELL | HOLD
    confidence: float    # 0.0 - 1.0
    strategy: str
    reasoning: str
    stop_loss_pct: float
    take_profit_pct: float


class StrategyManager:
    def __init__(self, data_dir: Optional[Path] = None):
        self._dca_path: Optional[Path] = (
            Path(data_dir) / "dca_timers.json" if data_dir else None
        )
        self._last_dca: Dict[str, datetime] = self._load_dca_timers()
        self._strategy_weights = {
            "dca": 0.30,
            "trend": 0.35,
            "mean_reversion": 0.35,
        }
        # Walk-forward optimizer overrides (F5.1) — None = use config/hardcoded defaults
        self._opt_rsi_oversold:  Optional[float] = None
        self._opt_rsi_overbought: Optional[float] = None

    # ── DCA timer persistence ─────────────────────────────────────────────

    def _load_dca_timers(self) -> Dict[str, datetime]:
        if self._dca_path is None:
            return {}
        data = safe_read_json(self._dca_path)
        if not isinstance(data, dict):
            return {}
        result: Dict[str, datetime] = {}
        for sym, iso in data.items():
            try:
                result[sym] = datetime.fromisoformat(iso)
            except Exception:
                pass
        if result:
            logger.info("StrategyManager: restored DCA timers for %d symbols", len(result))
        return result

    def _save_dca_timers(self):
        if self._dca_path is not None:
            atomic_write_json(
                self._dca_path,
                {sym: dt.isoformat() for sym, dt in self._last_dca.items()},
            )

    def set_opt_params(
        self,
        rsi_oversold:  Optional[float] = None,
        rsi_overbought: Optional[float] = None,
    ):
        """Apply walk-forward optimized RSI bands. Pass None to clear."""
        self._opt_rsi_oversold  = rsi_oversold
        self._opt_rsi_overbought = rsi_overbought
        logger.info(
            "StrategyManager: opt RSI bands updated oversold=%.0f overbought=%.0f",
            rsi_oversold or 0.0, rsi_overbought or 0.0,
        )

    def update_weights(self, weights: Dict[str, float]):
        """Updated by AI trainer based on performance."""
        self._strategy_weights.update(weights)
        logger.info(f"Strategy weights updated: {self._strategy_weights}")

    def dca_signal(self, analysis: MarketAnalysis) -> TradingSignal:
        cfg = settings.get("strategy", "dca") or {}
        # Optimizer override takes precedence over the config value when present
        rsi_buy  = self._opt_rsi_oversold  if self._opt_rsi_oversold  is not None \
                   else float(cfg.get("rsi_buy_threshold",  35))
        rsi_sell = self._opt_rsi_overbought if self._opt_rsi_overbought is not None \
                   else float(cfg.get("rsi_sell_threshold", 65))
        interval_h = float(cfg.get("interval_hours", 24))

        symbol = analysis.symbol
        last = self._last_dca.get(symbol)
        if last and datetime.utcnow() - last < timedelta(hours=interval_h):
            return TradingSignal("HOLD", 0.0, "dca", "DCA interval not reached", 0.03, 0.06)

        if analysis.rsi < rsi_buy:
            confidence = min((rsi_buy - analysis.rsi) / rsi_buy, 1.0)
            return TradingSignal(
                "BUY", confidence, "dca",
                f"DCA: RSI={analysis.rsi:.1f} (oversold < {rsi_buy})",
                0.03, 0.06
            )
        elif analysis.rsi > rsi_sell:
            confidence = min((analysis.rsi - rsi_sell) / (100 - rsi_sell), 1.0)
            return TradingSignal(
                "SELL", confidence, "dca",
                f"DCA: RSI={analysis.rsi:.1f} (overbought > {rsi_sell})",
                0.03, 0.06
            )
        return TradingSignal("HOLD", 0.2, "dca", f"DCA: RSI={analysis.rsi:.1f} neutral", 0.03, 0.06)

    def trend_signal(self, analysis: MarketAnalysis) -> TradingSignal:
        signals = []
        reasons = []

        if analysis.ema_trend == "BULLISH":
            signals.append(1)
            reasons.append(f"EMA bullish (9>{analysis.ema_9:.0f} > 21>{analysis.ema_21:.0f})")
        elif analysis.ema_trend == "BEARISH":
            signals.append(-1)
            reasons.append(f"EMA bearish (9<21<50)")

        if analysis.macd_trend == "BULLISH":
            signals.append(1)
            reasons.append(f"MACD bullish crossover")
        elif analysis.macd_trend == "BEARISH":
            signals.append(-1)
            reasons.append(f"MACD bearish crossover")

        if analysis.price_vs_vwap == "ABOVE" and analysis.volume_signal == "HIGH":
            signals.append(1)
            reasons.append("Price above VWAP with high volume")
        elif analysis.price_vs_vwap == "BELOW" and analysis.volume_signal == "HIGH":
            signals.append(-1)
            reasons.append("Price below VWAP with high volume")

        if not signals:
            return TradingSignal("HOLD", 0.1, "trend", "No trend signal", 0.025, 0.05)

        score = sum(signals) / len(signals)
        confidence = abs(score) * 0.8
        action = "BUY" if score > 0 else ("SELL" if score < 0 else "HOLD")
        return TradingSignal(action, confidence, "trend", "; ".join(reasons), 0.025, 0.05)

    def mean_reversion_signal(self, analysis: MarketAnalysis) -> TradingSignal:
        reasons = []
        buy_score = 0.0
        sell_score = 0.0

        if analysis.bb_signal == "OVERSOLD":
            buy_score += 0.5
            reasons.append(f"BB oversold (pos={analysis.bb_position:.2f})")
        elif analysis.bb_signal == "OVERBOUGHT":
            sell_score += 0.5
            reasons.append(f"BB overbought (pos={analysis.bb_position:.2f})")

        if analysis.rsi_signal == "OVERSOLD":
            buy_score += 0.4
            reasons.append(f"RSI oversold ({analysis.rsi:.1f})")
        elif analysis.rsi_signal == "OVERBOUGHT":
            sell_score += 0.4
            reasons.append(f"RSI overbought ({analysis.rsi:.1f})")

        if analysis.volatility == "HIGH":
            buy_score *= 0.7
            sell_score *= 0.7
            reasons.append("Reduced confidence: high volatility")

        if buy_score > sell_score and buy_score > 0.3:
            return TradingSignal("BUY", min(buy_score, 1.0), "mean_reversion", "; ".join(reasons), 0.03, 0.05)
        elif sell_score > buy_score and sell_score > 0.3:
            return TradingSignal("SELL", min(sell_score, 1.0), "mean_reversion", "; ".join(reasons), 0.03, 0.05)
        return TradingSignal("HOLD", 0.1, "mean_reversion", "No mean reversion signal", 0.03, 0.05)

    def hybrid_signal(self, analysis: MarketAnalysis, ml_signal: Optional[TradingSignal] = None) -> TradingSignal:
        dca = self.dca_signal(analysis)
        trend = self.trend_signal(analysis)
        mr = self.mean_reversion_signal(analysis)

        signals = {
            "dca": (dca, self._strategy_weights["dca"]),
            "trend": (trend, self._strategy_weights["trend"]),
            "mean_reversion": (mr, self._strategy_weights["mean_reversion"]),
        }

        buy_score = 0.0
        sell_score = 0.0
        all_reasons = []

        for name, (sig, weight) in signals.items():
            if sig.action == "BUY":
                buy_score += sig.confidence * weight
                all_reasons.append(f"[{name}] {sig.reasoning}")
            elif sig.action == "SELL":
                sell_score += sig.confidence * weight
                all_reasons.append(f"[{name}] {sig.reasoning}")

        if ml_signal and ml_signal.action != "HOLD":
            ml_weight = 0.30
            if ml_signal.action == "BUY":
                buy_score = buy_score * 0.7 + ml_signal.confidence * ml_weight
            else:
                sell_score = sell_score * 0.7 + ml_signal.confidence * ml_weight
            all_reasons.append(f"[ml] {ml_signal.reasoning}")

        min_conf = float(settings.get("trading", "min_confidence", default=0.60))

        if buy_score > sell_score and buy_score >= min_conf:
            return TradingSignal("BUY", buy_score, "hybrid", " | ".join(all_reasons[:3]), 0.03, 0.06)
        elif sell_score > buy_score and sell_score >= min_conf:
            return TradingSignal("SELL", sell_score, "hybrid", " | ".join(all_reasons[:3]), 0.03, 0.06)
        return TradingSignal("HOLD", max(buy_score, sell_score), "hybrid", "Insufficient confidence", 0.03, 0.06)

    def record_dca(self, symbol: str):
        self._last_dca[symbol] = datetime.utcnow()
        self._save_dca_timers()

    def ichimoku_strategy(self, analysis: MarketAnalysis) -> TradingSignal:
        """Ichimoku Cloud strategy — all-in-one Japanese trend system."""
        sig = analysis.ichimoku_signal
        if sig == "BULL":
            conf = 0.72
            if analysis.supertrend_signal == "BUY":
                conf = min(conf + 0.10, 0.90)
            return TradingSignal("BUY", conf, "ichimoku", "Ichimoku bullish: TK cross + above cloud", 0.025, 0.05)
        elif sig == "BEAR":
            conf = 0.72
            if analysis.supertrend_signal == "SELL":
                conf = min(conf + 0.10, 0.90)
            return TradingSignal("SELL", conf, "ichimoku", "Ichimoku bearish: TK cross + below cloud", 0.025, 0.05)
        return TradingSignal("HOLD", 0.30, "ichimoku", "Price inside Ichimoku cloud — no signal", 0.025, 0.05)

    def smc_strategy(self, analysis: MarketAnalysis) -> TradingSignal:
        """Smart Money Concepts strategy — institutional price action."""
        bs, ss = analysis.smc_buy, analysis.smc_sell
        min_score = 0.40
        if bs > ss and bs >= min_score:
            conf = min(0.50 + bs, 0.90)
            return TradingSignal("BUY", conf, "smc",
                                 f"SMC buy: {analysis.smc_summary}", 0.02, 0.05)
        elif ss > bs and ss >= min_score:
            conf = min(0.50 + ss, 0.90)
            return TradingSignal("SELL", conf, "smc",
                                 f"SMC sell: {analysis.smc_summary}", 0.02, 0.05)
        return TradingSignal("HOLD", max(bs, ss), "smc",
                             f"SMC: {analysis.smc_summary}", 0.02, 0.05)

    def signal_for_strategy(
        self,
        strategy: str,
        analysis: MarketAnalysis,
        ml_signal: Optional[TradingSignal] = None,
    ) -> TradingSignal:
        """Dispatch to a single named strategy (used by regime/RL-driven selection).

        Selecting one strategy that fits the current regime avoids the
        trend-vs-mean-reversion conflict that cancels out the blended
        ``hybrid_signal`` (e.g. in an uptrend ``trend`` wants BUY while
        ``mean_reversion`` wants SELL, netting to HOLD)."""
        if strategy == "dca":
            return self.dca_signal(analysis)
        if strategy == "trend":
            return self.trend_signal(analysis)
        if strategy == "mean_reversion":
            return self.mean_reversion_signal(analysis)
        if strategy == "ichimoku":
            return self.ichimoku_strategy(analysis)
        if strategy == "smc":
            return self.smc_strategy(analysis)
        return self.hybrid_signal(analysis, ml_signal)

    def get_signal(self, analysis: MarketAnalysis, ml_signal: Optional[TradingSignal] = None) -> TradingSignal:
        strategy = settings.get("strategy", "primary", default="hybrid")
        return self.signal_for_strategy(strategy, analysis, ml_signal)
