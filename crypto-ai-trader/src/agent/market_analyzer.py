import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from ..exchanges.base import OHLCV

logger = logging.getLogger(__name__)


@dataclass
class MarketAnalysis:
    symbol: str
    price: float
    change_24h: float

    rsi: float = 0.0
    rsi_signal: str = "NEUTRAL"

    macd: float = 0.0
    macd_signal: float = 0.0
    macd_hist: float = 0.0
    macd_trend: str = "NEUTRAL"

    ema_9: float = 0.0
    ema_21: float = 0.0
    ema_50: float = 0.0
    ema_trend: str = "NEUTRAL"

    bb_upper: float = 0.0
    bb_middle: float = 0.0
    bb_lower: float = 0.0
    bb_position: float = 0.5
    bb_signal: str = "NEUTRAL"

    atr: float = 0.0
    atr_pct: float = 0.0
    volatility: str = "MEDIUM"

    vwap: float = 0.0
    price_vs_vwap: str = "ABOVE"

    volume_ratio: float = 1.0
    volume_signal: str = "NORMAL"

    overall_signal: str = "HOLD"
    signal_strength: float = 0.0
    features: Dict = field(default_factory=dict)

    # Chart patterns (populated by detect_patterns)
    patterns: List = field(default_factory=list)
    pattern_summary: str = ""

    # Extended indicators (populated when available)
    supertrend_signal: str = "NEUTRAL"   # BUY | SELL | NEUTRAL
    stoch_rsi_k: float = 50.0
    stoch_rsi_signal: str = "NEUTRAL"
    williams_r: float = -50.0
    cci: float = 0.0
    rsi_divergence: str = "NONE"         # BULLISH | BEARISH | NONE
    ichimoku_signal: str = "NEUTRAL"     # BULL | BEAR | NEUTRAL
    smc_buy: float = 0.0
    smc_sell: float = 0.0
    smc_summary: str = ""
    aroon_signal: str = "NEUTRAL"
    market_regime: str = ""              # set by AITrader after detect_regime (BULL_TREND, …)

    # Quant features (ML4T Ch.4/Ch.9) — Kalman trend, GARCH vol forecast, WorldQuant alphas
    kalman_trend: str = "FLAT"           # BULLISH | BEARISH | FLAT (denoised)
    kalman_velocity: float = 0.0
    kalman_deviation_pct: float = 0.0    # raw price vs filtered (overextension)
    garch_forecast_vol_pct: float = 0.0  # forward 5-bar volatility forecast
    garch_vol_ratio: float = 1.0         # forecast/current (>1 = rising vol)
    garch_regime_hint: str = "STABLE"    # RISING_VOL | FALLING_VOL | STABLE
    alphas: Dict = field(default_factory=dict)   # WorldQuant formulaic alpha values


def _ema(series: np.ndarray, period: int) -> np.ndarray:
    k = 2 / (period + 1)
    result = np.zeros_like(series, dtype=float)
    result[0] = series[0]
    for i in range(1, len(series)):
        result[i] = series[i] * k + result[i - 1] * (1 - k)
    return result


def _rsi(closes: np.ndarray, period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    deltas = np.diff(closes[-(period + 1):])
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = gains.mean()
    avg_loss = losses.mean()
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _macd(closes: np.ndarray, fast=12, slow=26, signal=9):
    if len(closes) < slow + signal:
        return 0.0, 0.0, 0.0
    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)
    macd_line = ema_fast - ema_slow
    signal_line = _ema(macd_line, signal)
    hist = macd_line - signal_line
    return float(macd_line[-1]), float(signal_line[-1]), float(hist[-1])


def _bollinger(closes: np.ndarray, period=20, std_dev=2.0):
    if len(closes) < period:
        mid = float(closes.mean())
        return mid * 1.02, mid, mid * 0.98
    window = closes[-period:]
    mid = float(window.mean())
    std = float(window.std())
    return mid + std_dev * std, mid, mid - std_dev * std


def _atr(highs, lows, closes, period=14) -> float:
    if len(closes) < 2:
        return 0.0
    trs = []
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
        trs.append(tr)
    trs = np.array(trs[-period:])
    return float(trs.mean())


def _ohlcv_to_arrays(candles: List[OHLCV]):
    opens  = np.array([c.open   for c in candles], dtype=float)
    highs  = np.array([c.high   for c in candles], dtype=float)
    lows   = np.array([c.low    for c in candles], dtype=float)
    closes = np.array([c.close  for c in candles], dtype=float)
    vols   = np.array([c.volume for c in candles], dtype=float)
    return opens, highs, lows, closes, vols


def analyze(symbol: str, candles: List[OHLCV], price: float, change_24h: float,
            rsi_period: int = 14, bb_period: int = 20, atr_period: int = 14) -> MarketAnalysis:
    if len(candles) < 30:
        return MarketAnalysis(symbol=symbol, price=price, change_24h=change_24h)

    opens, highs, lows, closes, vols = _ohlcv_to_arrays(candles)
    result = MarketAnalysis(symbol=symbol, price=price, change_24h=change_24h)

    # RSI
    result.rsi = _rsi(closes, rsi_period)
    if result.rsi < 30:
        result.rsi_signal = "OVERSOLD"
    elif result.rsi > 70:
        result.rsi_signal = "OVERBOUGHT"

    # MACD
    result.macd, result.macd_signal, result.macd_hist = _macd(closes)
    _, _, prev_hist = _macd(closes[:-1])
    if result.macd_hist > 0 and prev_hist <= 0:
        result.macd_trend = "BULLISH"
    elif result.macd_hist < 0 and prev_hist >= 0:
        result.macd_trend = "BEARISH"
    elif result.macd > result.macd_signal:
        result.macd_trend = "BULLISH"
    elif result.macd < result.macd_signal:
        result.macd_trend = "BEARISH"

    # EMA
    result.ema_9  = float(_ema(closes, 9)[-1])
    result.ema_21 = float(_ema(closes, 21)[-1])
    result.ema_50 = float(_ema(closes, min(50, len(closes) - 1))[-1])
    if result.ema_9 > result.ema_21 > result.ema_50:
        result.ema_trend = "BULLISH"
    elif result.ema_9 < result.ema_21 < result.ema_50:
        result.ema_trend = "BEARISH"

    # Bollinger Bands
    result.bb_upper, result.bb_middle, result.bb_lower = _bollinger(closes, bb_period)
    band_range = result.bb_upper - result.bb_lower
    if band_range > 0:
        result.bb_position = (price - result.bb_lower) / band_range
    if result.bb_position < 0.1:
        result.bb_signal = "OVERSOLD"
    elif result.bb_position > 0.9:
        result.bb_signal = "OVERBOUGHT"

    # ATR
    result.atr = _atr(highs, lows, closes, atr_period)
    result.atr_pct = result.atr / price * 100 if price > 0 else 0
    if result.atr_pct < 1.0:
        result.volatility = "LOW"
    elif result.atr_pct > 3.0:
        result.volatility = "HIGH"

    # VWAP (cumulative)
    typical = (highs + lows + closes) / 3
    vwap_series = np.cumsum(typical * vols) / np.cumsum(vols)
    result.vwap = float(vwap_series[-1])
    result.price_vs_vwap = "ABOVE" if price > result.vwap else "BELOW"

    # Volume
    vol_avg = float(vols[-20:].mean()) if len(vols) >= 20 else float(vols.mean())
    curr_vol = float(vols[-1])
    result.volume_ratio = curr_vol / vol_avg if vol_avg > 0 else 1.0
    if result.volume_ratio < 0.5:
        result.volume_signal = "LOW"
    elif result.volume_ratio > 2.0:
        result.volume_signal = "HIGH"

    # Composite signal
    buy_score = 0.0
    sell_score = 0.0

    if result.rsi_signal == "OVERSOLD":     buy_score  += 0.25
    elif result.rsi_signal == "OVERBOUGHT": sell_score += 0.25

    if result.macd_trend == "BULLISH":  buy_score  += 0.25
    elif result.macd_trend == "BEARISH": sell_score += 0.25

    if result.ema_trend == "BULLISH":  buy_score  += 0.20
    elif result.ema_trend == "BEARISH": sell_score += 0.20

    if result.bb_signal == "OVERSOLD":     buy_score  += 0.20
    elif result.bb_signal == "OVERBOUGHT": sell_score += 0.20

    if result.price_vs_vwap == "ABOVE" and result.volume_signal == "HIGH":
        buy_score  += 0.10
    elif result.price_vs_vwap == "BELOW" and result.volume_signal == "HIGH":
        sell_score += 0.10

    # ── Chart pattern detection ────────────────────────────────────────
    try:
        from .chart_patterns import detect_patterns, patterns_to_signal_boost
        patterns = detect_patterns(closes, highs, lows, min_confidence=0.50)
        result.patterns = patterns
        pat_buy, pat_sell, result.pattern_summary = patterns_to_signal_boost(patterns)
        buy_score  += pat_buy
        sell_score += pat_sell
    except Exception as e:
        logger.debug("Chart pattern detection skipped: %s", e)

    # ── Advanced indicators (AI trading knowledge) ─────────────────────
    try:
        from .indicators_extra import (
            supertrend, stoch_rsi, williams_r as calc_wr, cci as calc_cci,
            rsi_divergence, ichimoku, ichimoku_signal_score, aroon,
        )
        # SuperTrend
        st = supertrend(closes, highs, lows)
        result.supertrend_signal = st["signal"]
        if st["signal"] == "BUY":
            buy_score  += 0.15
        elif st["signal"] == "SELL":
            sell_score += 0.15

        # Stochastic RSI
        srsi = stoch_rsi(closes)
        result.stoch_rsi_k      = srsi["k"]
        result.stoch_rsi_signal = srsi["signal"]
        if srsi["signal"] == "OVERSOLD":
            buy_score  += 0.10
        elif srsi["signal"] == "OVERBOUGHT":
            sell_score += 0.10

        # Williams %R
        wr = calc_wr(closes, highs, lows)
        result.williams_r = wr
        if wr < -80:
            buy_score  += 0.08
        elif wr > -20:
            sell_score += 0.08

        # CCI
        cci_val = calc_cci(closes, highs, lows)
        result.cci = cci_val
        if cci_val < -100:
            buy_score  += 0.08
        elif cci_val > 100:
            sell_score += 0.08

        # RSI Divergence
        div = rsi_divergence(closes)
        result.rsi_divergence = div
        if div == "BULLISH":
            buy_score  += 0.12
        elif div == "BEARISH":
            sell_score += 0.12

        # Ichimoku Cloud
        ichi = ichimoku(closes, highs, lows)
        ichi_buy, ichi_sell = ichimoku_signal_score(ichi)
        result.ichimoku_signal = "BULL" if ichi_buy > ichi_sell else ("BEAR" if ichi_sell > ichi_buy else "NEUTRAL")
        buy_score  += ichi_buy  * 0.20
        sell_score += ichi_sell * 0.20

        # Aroon
        arr = aroon(highs, lows)
        result.aroon_signal = arr["signal"]
        if arr["signal"] == "BULL":
            buy_score  += 0.08
        elif arr["signal"] == "BEAR":
            sell_score += 0.08

    except Exception as e:
        logger.debug("Extended indicators skipped: %s", e)

    # ── SMC (Smart Money Concepts) ─────────────────────────────────────
    try:
        from .smc_detector import analyse_smc
        smc = analyse_smc(closes, opens, highs, lows)
        result.smc_buy     = smc.buy_score
        result.smc_sell    = smc.sell_score
        result.smc_summary = smc.summary
        buy_score  += smc.buy_score  * 0.25
        sell_score += smc.sell_score * 0.25
    except Exception as e:
        logger.debug("SMC detection skipped: %s", e)

    # ── Quant features: Kalman trend, GARCH vol forecast, WorldQuant alphas ──
    try:
        from .quant_features import kalman_trend, garch_volatility, worldquant_alphas

        kal = kalman_trend(closes)
        result.kalman_trend         = kal.get("trend", "FLAT")
        result.kalman_velocity      = kal.get("velocity", 0.0)
        result.kalman_deviation_pct = kal.get("deviation_pct", 0.0)
        # Kalman trend adds confluence weight (denoised, less whipsaw than EMA)
        if result.kalman_trend == "BULLISH":
            buy_score  += 0.10
        elif result.kalman_trend == "BEARISH":
            sell_score += 0.10

        rets = np.diff(closes) / np.where(closes[:-1] != 0, closes[:-1], 1) * 100
        garch = garch_volatility(rets)
        result.garch_forecast_vol_pct = garch.get("forecast_vol_pct", 0.0)
        result.garch_vol_ratio        = garch.get("vol_ratio", 1.0)
        result.garch_regime_hint      = garch.get("regime_hint", "STABLE")

        result.alphas = worldquant_alphas(opens, highs, lows, closes, vols)
    except Exception as e:
        logger.debug("Quant features skipped: %s", e)

    if buy_score > sell_score and buy_score > 0.4:
        result.overall_signal = "BUY"
        result.signal_strength = min(buy_score, 1.0)
    elif sell_score > buy_score and sell_score > 0.4:
        result.overall_signal = "SELL"
        result.signal_strength = min(sell_score, 1.0)
    else:
        result.overall_signal = "HOLD"
        result.signal_strength = max(buy_score, sell_score)

    result.features = {
        "rsi":              result.rsi,
        "macd_hist":        result.macd_hist,
        "ema_9":            result.ema_9,
        "ema_21":           result.ema_21,
        "bb_position":      result.bb_position,
        "atr_pct":          result.atr_pct,
        "volume_ratio":     result.volume_ratio,
        "price_vs_vwap":    1 if result.price_vs_vwap == "ABOVE" else 0,
        "change_24h":       change_24h,
        # Extended features for ML training
        "stoch_rsi_k":      result.stoch_rsi_k,
        "williams_r":       result.williams_r,
        "cci":              result.cci,
        "smc_buy":          result.smc_buy,
        "smc_sell":         result.smc_sell,
        "ichimoku_bull":    1 if result.ichimoku_signal == "BULL" else 0,
        "supertrend_buy":   1 if result.supertrend_signal == "BUY" else 0,
        "rsi_div_bull":     1 if result.rsi_divergence == "BULLISH" else 0,
        "rsi_div_bear":     1 if result.rsi_divergence == "BEARISH" else 0,
        # Quant features (ML4T)
        "kalman_velocity":  result.kalman_velocity,
        "kalman_dev_pct":   result.kalman_deviation_pct,
        "garch_vol_ratio":  result.garch_vol_ratio,
    }
    # Merge WorldQuant alphas (prefixed) into the feature vector
    for name, val in (result.alphas or {}).items():
        result.features[f"wq_{name}"] = val

    return result
