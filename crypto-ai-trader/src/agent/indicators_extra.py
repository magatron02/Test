"""
Advanced Technical Indicators
— knowledge distilled from modern AI-driven trading research.

Includes:
  Ichimoku Cloud   — Japanese trend / momentum system (Tenkan/Kijun/Kumo)
  SuperTrend       — ATR-based dynamic support/resistance (popular AI signal)
  Stochastic RSI   — RSI of RSI: more sensitive momentum oscillator
  Williams %R      — short-term overbought/oversold (complement to RSI)
  CCI              — Commodity Channel Index: deviation from statistical average
  RSI Divergence   — bullish/bearish divergence between price and RSI
  Fibonacci Levels — key retracement levels from a price swing
  Aroon            — trend strength & direction
"""
from __future__ import annotations
import math
from typing import Dict, List, Optional, Tuple

import numpy as np

from .market_analyzer import _ema, _rsi


# ── Ichimoku Cloud ────────────────────────────────────────────────────────────

def ichimoku(
    closes: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    tenkan: int = 9,
    kijun: int = 26,
    senkou_b: int = 52,
) -> Dict[str, float]:
    """
    Returns the last bar's Ichimoku values.

    Signal logic (used in IchimokuStrategy):
      bullish: tenkan > kijun AND price > cloud (max of senkou_a, senkou_b)
      bearish: tenkan < kijun AND price < cloud
      kumo_twist: senkou_a crosses senkou_b (strong signal)
    """
    def midpoint(h: np.ndarray, l: np.ndarray, p: int) -> np.ndarray:
        out = np.full(len(h), np.nan)
        for i in range(p - 1, len(h)):
            out[i] = (h[i - p + 1:i + 1].max() + l[i - p + 1:i + 1].min()) / 2
        return out

    tk = midpoint(highs, lows, tenkan)
    kj = midpoint(highs, lows, kijun)

    n = len(closes)
    sa = (tk + kj) / 2
    sb = midpoint(highs, lows, senkou_b)

    # Project 26 bars ahead → look at current cloud is sa[-1], sb[-1]
    cloud_top    = max(sa[-1] if not np.isnan(sa[-1]) else 0,
                       sb[-1] if not np.isnan(sb[-1]) else 0)
    cloud_bottom = min(sa[-1] if not np.isnan(sa[-1]) else 0,
                       sb[-1] if not np.isnan(sb[-1]) else 0)

    price = closes[-1]
    tenkan_val = float(tk[-1]) if not np.isnan(tk[-1]) else price
    kijun_val  = float(kj[-1]) if not np.isnan(kj[-1]) else price

    # Chikou span = close displaced 26 bars back (compare with price 26 bars ago)
    chikou_vs_price = "ABOVE" if n > kijun and closes[-1] > closes[-kijun] else "BELOW"

    # kumo twist: senkou_a just crossed senkou_b
    twist = "BULL" if len(sa) > 1 and sa[-1] > sb[-1] and sa[-2] <= sb[-2] else (
            "BEAR" if len(sa) > 1 and sa[-1] < sb[-1] and sa[-2] >= sb[-2] else "NONE")

    return {
        "tenkan":         tenkan_val,
        "kijun":          kijun_val,
        "senkou_a":       float(sa[-1]) if not np.isnan(sa[-1]) else price,
        "senkou_b":       float(sb[-1]) if not np.isnan(sb[-1]) else price,
        "cloud_top":      cloud_top,
        "cloud_bottom":   cloud_bottom,
        "price":          price,
        "above_cloud":    price > cloud_top,
        "below_cloud":    price < cloud_bottom,
        "inside_cloud":   cloud_bottom <= price <= cloud_top,
        "tk_cross":       "BULL" if tenkan_val > kijun_val else "BEAR",
        "chikou":         chikou_vs_price,
        "kumo_twist":     twist,
    }


def ichimoku_signal_score(ichi: Dict) -> Tuple[float, float]:
    """Returns (buy_score, sell_score) 0.0–1.0 from Ichimoku state."""
    buy = sell = 0.0
    # TK cross (0.35 weight)
    if ichi["tk_cross"] == "BULL":
        buy  += 0.35
    else:
        sell += 0.35
    # Price vs cloud (0.35 weight)
    if ichi["above_cloud"]:
        buy  += 0.35
    elif ichi["below_cloud"]:
        sell += 0.35
    # Chikou confirmation (0.20)
    if ichi["chikou"] == "ABOVE":
        buy  += 0.20
    else:
        sell += 0.20
    # Kumo twist bonus (0.10)
    if ichi["kumo_twist"] == "BULL":
        buy  += 0.10
    elif ichi["kumo_twist"] == "BEAR":
        sell += 0.10
    return buy, sell


# ── SuperTrend ────────────────────────────────────────────────────────────────

def supertrend(
    closes: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    period: int = 10,
    multiplier: float = 3.0,
) -> Dict[str, float]:
    """
    SuperTrend indicator: ATR-based trailing stop that flips with trend.

    direction = +1 (bullish) when price > upper band
    direction = -1 (bearish) when price < lower band
    """
    n = len(closes)
    if n < period + 1:
        return {"direction": 1, "level": float(closes[-1]), "distance_pct": 0.0}

    # ATR
    trs = np.array([
        max(highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i]  - closes[i - 1]))
        for i in range(1, n)
    ])
    atr = np.convolve(trs, np.ones(period) / period, mode="valid")

    upper = np.zeros(n)
    lower = np.zeros(n)
    direction = np.ones(n, dtype=int)

    for i in range(period, n):
        mid = (highs[i] + lows[i]) / 2
        atr_val = atr[i - period]
        upper[i] = mid + multiplier * atr_val
        lower[i] = mid - multiplier * atr_val

        if i > period:
            upper[i] = min(upper[i], upper[i - 1]) if closes[i - 1] > upper[i - 1] else upper[i]
            lower[i] = max(lower[i], lower[i - 1]) if closes[i - 1] < lower[i - 1] else lower[i]

        if closes[i] > upper[i - 1]:
            direction[i] = 1
        elif closes[i] < lower[i - 1]:
            direction[i] = -1
        else:
            direction[i] = direction[i - 1]

    level = lower[-1] if direction[-1] == 1 else upper[-1]
    dist  = abs(closes[-1] - level) / closes[-1] * 100 if closes[-1] > 0 else 0

    return {
        "direction":    int(direction[-1]),
        "level":        float(level),
        "distance_pct": round(dist, 2),
        "signal":       "BUY" if direction[-1] == 1 else "SELL",
    }


# ── Stochastic RSI ────────────────────────────────────────────────────────────

def stoch_rsi(
    closes: np.ndarray,
    rsi_period: int = 14,
    stoch_period: int = 14,
    smooth_k: int = 3,
    smooth_d: int = 3,
) -> Dict[str, float]:
    """
    StochRSI: RSI normalised into a 0–100 oscillator.
    More sensitive than RSI alone; useful for spotting momentum divergence.
    """
    n = len(closes)
    if n < rsi_period + stoch_period + smooth_k + smooth_d:
        return {"k": 50.0, "d": 50.0, "signal": "NEUTRAL"}

    # Compute RSI for every bar
    rsi_vals = np.array([
        _rsi(closes[:i + 1], rsi_period)
        for i in range(n)
    ])

    # Rolling min/max of RSI over stoch_period
    raw_k = np.full(n, 50.0)
    for i in range(stoch_period - 1, n):
        w = rsi_vals[i - stoch_period + 1:i + 1]
        lo, hi = w.min(), w.max()
        raw_k[i] = (rsi_vals[i] - lo) / (hi - lo) * 100 if hi > lo else 50.0

    k = np.convolve(raw_k, np.ones(smooth_k) / smooth_k, mode="valid")
    d = np.convolve(k, np.ones(smooth_d) / smooth_d, mode="valid")

    kv, dv = float(k[-1]), float(d[-1])
    if kv < 20:
        sig = "OVERSOLD"
    elif kv > 80:
        sig = "OVERBOUGHT"
    else:
        sig = "BULLISH_CROSS" if kv > dv and k[-2] <= d[len(d) - len(k) + len(k) - 2] else "NEUTRAL"

    return {"k": round(kv, 1), "d": round(dv, 1), "signal": sig}


# ── Williams %R ───────────────────────────────────────────────────────────────

def williams_r(
    closes: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    period: int = 14,
) -> float:
    """Williams %R: -100 (oversold) to 0 (overbought)."""
    if len(closes) < period:
        return -50.0
    h = highs[-period:].max()
    l = lows[-period:].min()
    if h == l:
        return -50.0
    return (h - closes[-1]) / (h - l) * -100


# ── CCI ───────────────────────────────────────────────────────────────────────

def cci(
    closes: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    period: int = 20,
) -> float:
    """Commodity Channel Index. >+100 overbought, <-100 oversold."""
    if len(closes) < period:
        return 0.0
    typical = (highs[-period:] + lows[-period:] + closes[-period:]) / 3
    mean = typical.mean()
    mad  = np.abs(typical - mean).mean()
    if mad == 0:
        return 0.0
    return (typical[-1] - mean) / (0.015 * mad)


# ── RSI Divergence ────────────────────────────────────────────────────────────

def rsi_divergence(
    closes: np.ndarray,
    period: int = 14,
    lookback: int = 30,
) -> str:
    """
    Detect regular RSI divergence in the last `lookback` bars.

    Returns:
      BULLISH  — price makes lower low but RSI makes higher low (buy signal)
      BEARISH  — price makes higher high but RSI makes lower high (sell signal)
      NONE     — no divergence detected
    """
    if len(closes) < period + lookback:
        return "NONE"

    window = closes[-lookback:]
    rsi_vals = np.array([_rsi(closes[:-(lookback - i - 1)] if i < lookback - 1 else closes, period)
                         for i in range(lookback)])

    # Find pivots using simple comparison
    price_lows  = [i for i in range(2, len(window) - 2)
                   if window[i] < window[i - 1] and window[i] < window[i + 1]]
    price_highs = [i for i in range(2, len(window) - 2)
                   if window[i] > window[i - 1] and window[i] > window[i + 1]]

    # Bullish divergence: last 2 price lows descending, RSI lows ascending
    if len(price_lows) >= 2:
        l1, l2 = price_lows[-2], price_lows[-1]
        if window[l2] < window[l1] and rsi_vals[l2] > rsi_vals[l1]:
            return "BULLISH"

    # Bearish divergence: last 2 price highs ascending, RSI highs descending
    if len(price_highs) >= 2:
        h1, h2 = price_highs[-2], price_highs[-1]
        if window[h2] > window[h1] and rsi_vals[h2] < rsi_vals[h1]:
            return "BEARISH"

    return "NONE"


# ── Fibonacci Retracement ─────────────────────────────────────────────────────

def fibonacci_levels(closes: np.ndarray, lookback: int = 50) -> Dict[str, float]:
    """
    Compute key Fibonacci retracement levels from the swing high/low
    in the last `lookback` bars.

    Returns dict of fib levels and whether price is near a key level.
    """
    if len(closes) < lookback:
        lookback = len(closes)
    window = closes[-lookback:]
    swing_high = float(window.max())
    swing_low  = float(window.min())
    diff = swing_high - swing_low
    price = float(closes[-1])

    levels = {
        "0.0":   swing_low,
        "23.6":  swing_low + 0.236 * diff,
        "38.2":  swing_low + 0.382 * diff,
        "50.0":  swing_low + 0.500 * diff,
        "61.8":  swing_low + 0.618 * diff,
        "78.6":  swing_low + 0.786 * diff,
        "100.0": swing_high,
    }

    # Find nearest fib level (within 1%)
    nearest = min(levels.items(), key=lambda x: abs(x[1] - price))
    near_fib = abs(nearest[1] - price) / price < 0.01

    return {**levels, "near_fib": near_fib, "nearest_level": nearest[0], "swing_high": swing_high, "swing_low": swing_low}


# ── Aroon ─────────────────────────────────────────────────────────────────────

def aroon(highs: np.ndarray, lows: np.ndarray, period: int = 25) -> Dict[str, float]:
    """
    Aroon Up/Down: measures how recently the highest high / lowest low occurred.
    Above 70 = strong trend; crossing = trend change.
    """
    if len(highs) < period + 1:
        return {"up": 50.0, "down": 50.0, "oscillator": 0.0, "signal": "NEUTRAL"}
    h = highs[-(period + 1):]
    l = lows[-(period + 1):]
    up   = (period - (len(h) - 1 - h.argmax())) / period * 100
    down = (period - (len(l) - 1 - l.argmin())) / period * 100
    osc  = up - down
    return {
        "up":   round(up, 1),
        "down": round(down, 1),
        "oscillator": round(osc, 1),
        "signal": "BULL" if up > 70 and up > down else ("BEAR" if down > 70 and down > up else "NEUTRAL"),
    }
