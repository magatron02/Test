"""
Market Regime Detector — classifies current market state to guide strategy selection.

Regimes:
  BULL_TREND  — Strong uptrend confirmed by ADX + EMA stack + positive slope
  BEAR_TREND  — Strong downtrend confirmed by ADX + EMA stack + negative slope
  RANGING     — Sideways/consolidating, mean-reversion strategies preferred
  VOLATILE    — High ATR without directional conviction, reduce position size
  CRASH       — Rapid decline > threshold in short window, near-defensive stance
"""
import logging
from dataclasses import dataclass
from typing import List

import numpy as np

from ..exchanges.base import OHLCV
from .market_analyzer import MarketAnalysis, _ema

logger = logging.getLogger(__name__)


@dataclass
class RegimeResult:
    regime: str        # BULL_TREND | BEAR_TREND | RANGING | VOLATILE | CRASH
    confidence: float  # 0.0 – 1.0
    adx: float
    atr_pct: float
    trend_slope: float  # % change per bar (linear regression)
    detail: str


def _adx(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float:
    """Wilder's ADX — measures trend strength (directionless)."""
    n = len(closes)
    if n < period * 2:
        return 20.0

    plus_dm  = np.zeros(n)
    minus_dm = np.zeros(n)
    tr_arr   = np.zeros(n)

    for i in range(1, n):
        up   = highs[i]  - highs[i - 1]
        down = lows[i - 1] - lows[i]
        plus_dm[i]  = up   if (up > down and up > 0)   else 0.0
        minus_dm[i] = down if (down > up and down > 0) else 0.0
        tr_arr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i]  - closes[i - 1]),
        )

    def wilder(arr: np.ndarray, p: int) -> np.ndarray:
        s = np.zeros(len(arr))
        s[p] = arr[1 : p + 1].sum()
        for i in range(p + 1, len(arr)):
            s[i] = s[i - 1] - s[i - 1] / p + arr[i]
        return s

    atr_s   = wilder(tr_arr,   period)
    plus_s  = wilder(plus_dm,  period)
    minus_s = wilder(minus_dm, period)

    with np.errstate(divide="ignore", invalid="ignore"):
        plus_di  = np.where(atr_s > 0, 100 * plus_s  / atr_s, 0.0)
        minus_di = np.where(atr_s > 0, 100 * minus_s / atr_s, 0.0)
        dx = np.where(
            (plus_di + minus_di) > 0,
            100 * np.abs(plus_di - minus_di) / (plus_di + minus_di),
            0.0,
        )

    # wilder() returns a Wilder *sum* (≈ average × period). For +DI/-DI the
    # period cancels in the ratio, but the final ADX must be the smoothed
    # *average* of DX — so divide the accumulated sum back down by `period`.
    adx_arr = wilder(dx, period)
    val = float(adx_arr[-1]) / period
    return val if val > 0 else 20.0


def detect_regime(candles: List[OHLCV], analysis: MarketAnalysis) -> RegimeResult:
    """Classify the current market regime from raw OHLCV + pre-computed analysis."""
    if len(candles) < 50:
        return RegimeResult("RANGING", 0.4, 20.0, analysis.atr_pct, 0.0, "Insufficient data")

    closes = np.array([c.close for c in candles], dtype=float)
    highs  = np.array([c.high  for c in candles], dtype=float)
    lows   = np.array([c.low   for c in candles], dtype=float)

    adx_val  = _adx(highs, lows, closes)
    atr_pct  = analysis.atr_pct

    # Linear regression slope over last 20 bars (% per bar)
    window = closes[-20:]
    x = np.arange(len(window), dtype=float)
    slope, _ = np.polyfit(x, window, 1)
    trend_slope = slope / window.mean() * 100

    # ── CRASH: rapid drop > 4% in last 3 candles ──────────────────────
    if len(closes) >= 4:
        short_drop = (closes[-1] - closes[-4]) / closes[-4] * 100
        if short_drop < -4.0:
            return RegimeResult(
                "CRASH",
                min(abs(short_drop) / 4.0, 1.0),
                adx_val, atr_pct, trend_slope,
                f"Rapid drop {short_drop:.1f}% in 3 bars",
            )

    # ── VOLATILE: high ATR without trend conviction ────────────────────
    if atr_pct > 3.5 and adx_val < 25:
        return RegimeResult(
            "VOLATILE",
            min(atr_pct / 5.0, 1.0),
            adx_val, atr_pct, trend_slope,
            f"High ATR {atr_pct:.1f}%, no clear trend (ADX={adx_val:.0f})",
        )

    # ── TRENDING ───────────────────────────────────────────────────────
    if adx_val >= 25:
        conf = min((adx_val - 25) / 25.0 + 0.4, 1.0)
        if trend_slope > 0.05:
            return RegimeResult(
                "BULL_TREND", conf, adx_val, atr_pct, trend_slope,
                f"Bullish trend ADX={adx_val:.0f}, slope={trend_slope:.3f}%/bar",
            )
        if trend_slope < -0.05:
            return RegimeResult(
                "BEAR_TREND", conf, adx_val, atr_pct, trend_slope,
                f"Bearish trend ADX={adx_val:.0f}, slope={trend_slope:.3f}%/bar",
            )

    # ── RANGING ────────────────────────────────────────────────────────
    conf = max(0.3, 1.0 - adx_val / 50.0)
    return RegimeResult(
        "RANGING", conf, adx_val, atr_pct, trend_slope,
        f"Ranging market ADX={adx_val:.0f}",
    )
