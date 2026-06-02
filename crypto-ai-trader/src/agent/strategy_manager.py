import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional

from .market_analyzer import MarketAnalysis
from .market_signals import fear_greed_bias, funding_bias
from ..core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class TradingSignal:
    action: str          # BUY | SELL | HOLD
    confidence: float    # 0.0 - 1.0
    strategy: str
    reasoning: str
    stop_loss_pct: float
    take_profit_pct: float


def _btc_bias(btc: dict) -> float:
    """
    Small confidence adjustment for altcoins based on BTC trend direction.
    Returns positive (BUY bias) or negative (SELL bias), max ±0.10.
    Dampened when BTC is at RSI extremes (altcoins tend to decouple there).
    """
    bias = 0.0
    if btc.get("ema_trend") == "BULLISH":
        bias += 0.05
    elif btc.get("ema_trend") == "BEARISH":
        bias -= 0.05
    if btc.get("macd_trend") == "BULLISH":
        bias += 0.03
    elif btc.get("macd_trend") == "BEARISH":
        bias -= 0.03
    rsi = btc.get("rsi", 50)
    if rsi > 75 or rsi < 25:   # extreme RSI → altcoins decouple, dampen
        bias *= 0.3
    return round(max(-0.10, min(0.10, bias)), 3)


def _atr_sl_tp(atr_pct: float) -> tuple:
    """
    Dynamic SL/TP based on current ATR volatility.
    SL = ATR × sl_mult, capped 1%–8%
    TP = ATR × tp_mult, capped 2%–15%
    Adapts automatically: tight stops in calm markets, wide in volatile.
    """
    sl_mult = float(settings.get("strategy", "atr_sl_mult", default=2.0))
    tp_mult = float(settings.get("strategy", "atr_tp_mult", default=3.0))
    sl = max(0.010, min(0.080, atr_pct / 100 * sl_mult))
    tp = max(0.020, min(0.150, atr_pct / 100 * tp_mult))
    return round(sl, 4), round(tp, 4)


class StrategyManager:
    def __init__(self):
        self._last_dca: Dict[str, datetime] = {}
        self._strategy_weights = {
            "dca": 0.30,
            "trend": 0.35,
            "mean_reversion": 0.35,
        }

    def update_weights(self, weights: Dict[str, float]):
        self._strategy_weights.update(weights)
        logger.info(f"Strategy weights updated: {self._strategy_weights}")

    def dca_signal(self, analysis: MarketAnalysis) -> TradingSignal:
        cfg = settings.get("strategy", "dca") or {}
        rsi_buy = float(cfg.get("rsi_buy_threshold", 35))
        rsi_sell = float(cfg.get("rsi_sell_threshold", 65))
        interval_h = float(cfg.get("interval_hours", 24))
        sl, tp = _atr_sl_tp(analysis.atr_pct) if analysis.atr_pct > 0 else (0.03, 0.06)

        symbol = analysis.symbol
        last = self._last_dca.get(symbol)
        if last and datetime.utcnow() - last < timedelta(hours=interval_h):
            return TradingSignal("HOLD", 0.0, "dca", "DCA interval not reached", sl, tp)

        if analysis.rsi < rsi_buy:
            confidence = min((rsi_buy - analysis.rsi) / rsi_buy, 1.0)
            return TradingSignal(
                "BUY", confidence, "dca",
                f"DCA: RSI={analysis.rsi:.1f} (oversold < {rsi_buy})",
                sl, tp,
            )
        elif analysis.rsi > rsi_sell:
            confidence = min((analysis.rsi - rsi_sell) / (100 - rsi_sell), 1.0)
            return TradingSignal(
                "SELL", confidence, "dca",
                f"DCA: RSI={analysis.rsi:.1f} (overbought > {rsi_sell})",
                sl, tp,
            )
        return TradingSignal("HOLD", 0.2, "dca", f"DCA: RSI={analysis.rsi:.1f} neutral", sl, tp)

    def trend_signal(self, analysis: MarketAnalysis) -> TradingSignal:
        sl, tp = _atr_sl_tp(analysis.atr_pct) if analysis.atr_pct > 0 else (0.025, 0.05)
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
            return TradingSignal("HOLD", 0.1, "trend", "No trend signal", sl, tp)

        score = sum(signals) / len(signals)
        confidence = abs(score) * 0.8
        action = "BUY" if score > 0 else ("SELL" if score < 0 else "HOLD")
        return TradingSignal(action, confidence, "trend", "; ".join(reasons), sl, tp)

    def mean_reversion_signal(self, analysis: MarketAnalysis) -> TradingSignal:
        sl, tp = _atr_sl_tp(analysis.atr_pct) if analysis.atr_pct > 0 else (0.03, 0.05)
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
            return TradingSignal("BUY", min(buy_score, 1.0), "mean_reversion", "; ".join(reasons), sl, tp)
        elif sell_score > buy_score and sell_score > 0.3:
            return TradingSignal("SELL", min(sell_score, 1.0), "mean_reversion", "; ".join(reasons), sl, tp)
        return TradingSignal("HOLD", 0.1, "mean_reversion", "No mean reversion signal", sl, tp)

    def hybrid_signal(
        self,
        analysis: MarketAnalysis,
        ml_signal: Optional[TradingSignal] = None,
        ext_signals: Optional[dict] = None,
    ) -> TradingSignal:
        sl, tp = _atr_sl_tp(analysis.atr_pct) if analysis.atr_pct > 0 else (0.03, 0.06)
        dca   = self.dca_signal(analysis)
        trend = self.trend_signal(analysis)
        mr    = self.mean_reversion_signal(analysis)

        signals = {
            "dca":            (dca,   self._strategy_weights["dca"]),
            "trend":          (trend, self._strategy_weights["trend"]),
            "mean_reversion": (mr,    self._strategy_weights["mean_reversion"]),
        }

        buy_score  = 0.0
        sell_score = 0.0
        all_reasons = []

        for name, (sig, weight) in signals.items():
            if sig.action == "BUY":
                buy_score  += sig.confidence * weight
                all_reasons.append(f"[{name}] {sig.reasoning}")
            elif sig.action == "SELL":
                sell_score += sig.confidence * weight
                all_reasons.append(f"[{name}] {sig.reasoning}")

        if ml_signal and ml_signal.action != "HOLD":
            ml_weight = 0.30
            if ml_signal.action == "BUY":
                buy_score = buy_score * 0.7 + ml_signal.confidence * ml_weight
                sell_score *= 0.7    # ML contradicts any bearish rule lean → dampen it
            else:
                sell_score = sell_score * 0.7 + ml_signal.confidence * ml_weight
                buy_score *= 0.7     # ML contradicts any bullish rule lean → dampen it
            all_reasons.append(f"[ml] {ml_signal.reasoning}")

        # ── External signal adjustments ────────────────────────────────
        ext_notes = []
        if ext_signals:
            fg = ext_signals.get("fear_greed")
            if fg:
                bias = fear_greed_bias(fg["value"])
                if bias > 0:
                    buy_score  = min(1.0, buy_score  + bias)
                    ext_notes.append(f"FearGreed={fg['value']}({fg['label']})→+{bias:.2f} BUY")
                elif bias < 0:
                    sell_score = min(1.0, sell_score + abs(bias))
                    ext_notes.append(f"FearGreed={fg['value']}({fg['label']})→+{abs(bias):.2f} SELL")

            fr = ext_signals.get("funding_rates", {}).get(analysis.symbol)
            if fr is not None:
                bias = funding_bias(fr)
                if bias > 0:
                    buy_score  = min(1.0, buy_score  + bias)
                    ext_notes.append(f"Funding={fr:+.4f}%→+{bias:.2f} BUY")
                elif bias < 0:
                    sell_score = min(1.0, sell_score + abs(bias))
                    ext_notes.append(f"Funding={fr:+.4f}%→+{abs(bias):.2f} SELL")

        # ── BTC dominance bias (altcoins only) ────────────────────────
        if ext_signals and analysis.symbol != "BTC/USDT":
            btc = ext_signals.get("btc_signal")
            if btc:
                bias = _btc_bias(btc)
                if bias > 0:
                    buy_score  = min(1.0, buy_score  + bias)
                    ext_notes.append(f"BTC {btc.get('ema_trend','?')} RSI={btc.get('rsi',0):.0f}→+{bias:.2f} BUY")
                elif bias < 0:
                    sell_score = min(1.0, sell_score + abs(bias))
                    ext_notes.append(f"BTC {btc.get('ema_trend','?')} RSI={btc.get('rsi',0):.0f}→+{abs(bias):.2f} SELL")

        # ── Volume spike amplification ─────────────────────────────────
        # Only amplifies when spike direction aligns with the leading score.
        # A spike against VWAP is ambiguous — no boost applied.
        if analysis.volume_spike:
            spike_boost = max(0.0, min(0.12, (analysis.volume_ratio - 3.0) / 10 + 0.06))
            vwap = analysis.price_vs_vwap
            if buy_score > sell_score and vwap == "ABOVE":
                buy_score  = min(1.0, buy_score  + spike_boost)
                ext_notes.append(f"VolSpike {analysis.volume_ratio:.1f}x above VWAP→+{spike_boost:.2f} BUY")
            elif sell_score > buy_score and vwap == "BELOW":
                sell_score = min(1.0, sell_score + spike_boost)
                ext_notes.append(f"VolSpike {analysis.volume_ratio:.1f}x below VWAP→+{spike_boost:.2f} SELL")

        if ext_notes:
            all_reasons.append("[ext] " + " | ".join(ext_notes))

        min_conf = float(settings.get("trading", "min_confidence", default=0.60))

        if buy_score > sell_score and buy_score >= min_conf:
            return TradingSignal("BUY",  buy_score,  "hybrid", " | ".join(all_reasons[:4]), sl, tp)
        elif sell_score > buy_score and sell_score >= min_conf:
            return TradingSignal("SELL", sell_score, "hybrid", " | ".join(all_reasons[:4]), sl, tp)
        return TradingSignal("HOLD", max(buy_score, sell_score), "hybrid", "Insufficient confidence", sl, tp)

    def record_dca(self, symbol: str):
        self._last_dca[symbol] = datetime.utcnow()

    def get_signal(
        self,
        analysis: MarketAnalysis,
        ml_signal: Optional[TradingSignal] = None,
        ext_signals: Optional[dict] = None,
    ) -> TradingSignal:
        strategy = settings.get("strategy", "primary", default="hybrid")
        if strategy == "dca":
            return self.dca_signal(analysis)
        elif strategy == "trend":
            return self.trend_signal(analysis)
        elif strategy == "mean_reversion":
            return self.mean_reversion_signal(analysis)
        return self.hybrid_signal(analysis, ml_signal, ext_signals)

