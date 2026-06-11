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
    volume_spike: bool = False    # True when volume ≥ 3× 20-candle average

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

    # Fibonacci retracement confluence
    near_fib: bool = False               # price within 1% of any key fib level
    fib_nearest_level: str = ""          # "23.6" | "38.2" | "50.0" | "61.8" | "78.6" | "100.0"
    fib_zone: str = "NEUTRAL"            # SUPPORT | RESISTANCE | NEUTRAL

    # Quant features (ML4T Ch.4/Ch.9) — Kalman trend, GARCH vol forecast, WorldQuant alphas
    kalman_trend: str = "FLAT"           # BULLISH | BEARISH | FLAT (denoised)
    kalman_velocity: float = 0.0
    kalman_deviation_pct: float = 0.0    # raw price vs filtered (overextension)
    garch_forecast_vol_pct: float = 0.0  # forward 5-bar volatility forecast
    garch_vol_ratio: float = 1.0         # forecast/current (>1 = rising vol)
    garch_regime_hint: str = "STABLE"    # RISING_VOL | FALLING_VOL | STABLE
    alphas: Dict = field(default_factory=dict)   # WorldQuant formulaic alpha values

    # Microstructure features (from order book L2)
    book_imbalance: float = 0.5          # bid_vol / (bid_vol+ask_vol), 0.5=balanced
    whale_bid_price: float = 0.0         # price of largest bid wall (0 = none detected)
    whale_bid_size: float = 0.0          # qty of largest bid wall
    whale_ask_price: float = 0.0         # price of largest ask wall
    whale_ask_size: float = 0.0          # qty of largest ask wall
    twap_detected: bool = False          # True when periodic volume pattern found
    twap_score: float = 0.0             # how many σ above noise (0–3)


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
        # Flat market (no gains and no losses) is neutral, not overbought.
        return 50.0 if avg_gain == 0 else 100.0
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


def analyze_order_book(analysis: "MarketAnalysis", bids: List, asks: List) -> None:
    """Populate microstructure fields on an existing MarketAnalysis in-place.

    bids/asks are lists of (price, qty) tuples sorted descending/ascending.
    Only considers levels within ±3 % of the current mid-price.
    """
    price = analysis.price
    if not price or not bids or not asks:
        return

    near = 0.03  # 3 % window around mid
    bids_near = [(p, q) for p, q in bids if abs(p - price) / price <= near]
    asks_near = [(p, q) for p, q in asks if abs(p - price) / price <= near]

    # ── Book imbalance ────────────────────────────────────────────────
    bid_vol = sum(q for _, q in bids_near[:10])
    ask_vol = sum(q for _, q in asks_near[:10])
    total = bid_vol + ask_vol
    analysis.book_imbalance = bid_vol / total if total > 0 else 0.5

    # ── Whale wall detection (qty > 3× average in near window) ───────
    if bids_near:
        bid_qtys = [q for _, q in bids_near]
        avg_bid = float(np.mean(bid_qtys))
        best_bid = max(bids_near, key=lambda x: x[1])
        if avg_bid > 0 and best_bid[1] > avg_bid * 3:
            analysis.whale_bid_price = best_bid[0]
            analysis.whale_bid_size  = best_bid[1]

    if asks_near:
        ask_qtys = [q for _, q in asks_near]
        avg_ask = float(np.mean(ask_qtys))
        best_ask = max(asks_near, key=lambda x: x[1])
        if avg_ask > 0 and best_ask[1] > avg_ask * 3:
            analysis.whale_ask_price = best_ask[0]
            analysis.whale_ask_size  = best_ask[1]


def _twap_detect(vols: np.ndarray, n_bars: int = 64) -> dict:
    """Detect periodic volume bursts (TWAP execution) via FFT on volume series."""
    if len(vols) < n_bars:
        return {"detected": False, "score": 0.0}

    series = vols[-n_bars:].astype(float)
    series -= series.mean()

    fft_mag = np.abs(np.fft.rfft(series))
    fft_mag[0] = 0  # remove DC

    noise = fft_mag[1:]
    if noise.std() == 0:
        return {"detected": False, "score": 0.0}

    threshold = noise.mean() + 3 * noise.std()
    peaks = np.where(noise > threshold)[0]

    if len(peaks) == 0:
        return {"detected": False, "score": 0.0}

    best = int(peaks[np.argmax(noise[peaks])])
    score = float(noise[best] / threshold - 1.0)

    period_bars = n_bars // (best + 1) if (best + 1) > 0 else 0
    detected = score > 0.5 and period_bars >= 2
    return {"detected": detected, "score": min(score, 3.0)}


def analyze(symbol: str, candles: List[OHLCV], price: float, change_24h: float,
            rsi_period: int = 14, bb_period: int = 20, atr_period: int = 14,
            rsi_oversold: float = 30.0, rsi_overbought: float = 70.0) -> MarketAnalysis:
    if len(candles) < 30:
        return MarketAnalysis(symbol=symbol, price=price, change_24h=change_24h)

    opens, highs, lows, closes, vols = _ohlcv_to_arrays(candles)
    result = MarketAnalysis(symbol=symbol, price=price, change_24h=change_24h)

    # RSI
    result.rsi = _rsi(closes, rsi_period)
    if result.rsi < rsi_oversold:
        result.rsi_signal = "OVERSOLD"
    elif result.rsi > rsi_overbought:
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
    # Only treat ema_50 as a true 50-period EMA when there is enough data;
    # otherwise fall back to ema_21 so the stack comparison stays consistent.
    result.ema_50 = float(_ema(closes, 50)[-1]) if len(closes) >= 51 else result.ema_21
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

    # VWAP — anchored to the current session (UTC day). A cumulative VWAP over
    # the whole 100-candle window is too slow-moving to be a meaningful
    # intraday reference, so we reset it at each day boundary.
    typical = (highs + lows + closes) / 3
    try:
        last_day = candles[-1].timestamp.date()
        start = 0
        for i in range(len(candles) - 1, -1, -1):
            if candles[i].timestamp.date() != last_day:
                start = i + 1
                break
        if len(candles) - start < 10:    # too few candles → use a rolling window
            start = max(0, len(candles) - 32)
    except Exception:
        start = max(0, len(candles) - 32)
    seg_typ, seg_vol = typical[start:], vols[start:]
    cum_vol = np.cumsum(seg_vol)
    vwap_series = np.cumsum(seg_typ * seg_vol) / np.where(cum_vol == 0, 1.0, cum_vol)
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
    result.volume_spike = result.volume_ratio >= 3.0

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
            fibonacci_levels,
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

        # Fibonacci retracement confluence
        fib = fibonacci_levels(closes)
        result.near_fib          = fib["near_fib"]
        result.fib_nearest_level = fib["nearest_level"]
        _GOLDEN = {"38.2", "61.8"}
        if fib["near_fib"]:
            lvl    = fib["nearest_level"]
            weight = 0.15 if lvl in _GOLDEN else 0.08
            if result.bb_position < 0.5 and lvl in {"23.6", "38.2", "50.0"}:
                result.fib_zone = "SUPPORT"
                buy_score  += weight
            elif result.bb_position >= 0.5 and lvl in {"61.8", "78.6", "100.0"}:
                result.fib_zone = "RESISTANCE"
                sell_score += weight

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

    # ── TWAP detection via FFT on volume series ───────────────────────────────
    try:
        twap = _twap_detect(vols)
        result.twap_detected = twap["detected"]
        result.twap_score    = twap["score"]
        if result.twap_detected:
            logger.debug("TWAP pattern detected for %s (score=%.2f)", symbol, result.twap_score)
    except Exception as e:
        logger.debug("TWAP detection skipped: %s", e)

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
        # Fibonacci retracement
        "near_fib":         1 if result.near_fib else 0,
        "fib_zone":         1 if result.fib_zone == "SUPPORT" else (-1 if result.fib_zone == "RESISTANCE" else 0),
        # Quant features (ML4T)
        "kalman_velocity":  result.kalman_velocity,
        "kalman_dev_pct":   result.kalman_deviation_pct,
        "garch_vol_ratio":  result.garch_vol_ratio,
    }
    # Merge WorldQuant alphas (prefixed) into the feature vector
    for name, val in (result.alphas or {}).items():
        result.features[f"wq_{name}"] = val

    # Microstructure features (populated later by analyze_order_book; zero until then)
    result.features["book_imbalance"] = result.book_imbalance
    result.features["whale_bid"]      = 1 if result.whale_bid_size > 0 else 0
    result.features["whale_ask"]      = 1 if result.whale_ask_size > 0 else 0
    result.features["twap_detected"]  = 1 if result.twap_detected else 0
    result.features["twap_score"]     = result.twap_score

    return result
