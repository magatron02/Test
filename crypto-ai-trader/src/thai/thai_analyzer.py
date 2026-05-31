"""
Technical analysis for Thai SET stocks (daily timeframe).
Uses same numpy-based indicators as the crypto market analyzer.
"""
import math
import numpy as np
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class SetAnalysis:
    symbol: str
    name: str
    sector: str
    price: float
    change_1d: float
    signal: str          # BUY | SELL | HOLD
    confidence: float    # 0-1
    reasoning: str

    rsi: float = 50.0
    rsi_signal: str = "NEUTRAL"
    macd_trend: str = "NEUTRAL"
    ema_trend: str = "NEUTRAL"
    bb_signal: str = "NEUTRAL"
    bb_position: float = 0.5
    volatility: str = "MEDIUM"
    support: float = 0.0   # estimated support (lower BB)
    resistance: float = 0.0  # estimated resistance (upper BB)


def _ema(arr: np.ndarray, n: int) -> np.ndarray:
    k = 2 / (n + 1)
    out = np.empty_like(arr, dtype=float)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = arr[i] * k + out[i - 1] * (1 - k)
    return out


def _rsi(closes: np.ndarray, n: int = 14) -> float:
    if len(closes) < n + 1:
        return 50.0
    d = np.diff(closes[-(n + 1):])
    avg_g = np.where(d > 0, d, 0).mean()
    avg_l = np.where(d < 0, -d, 0).mean()
    if avg_l == 0:
        return 100.0
    return 100 - 100 / (1 + avg_g / avg_l)


def _macd_cross(closes: np.ndarray) -> str:
    if len(closes) < 35:
        return "NEUTRAL"
    fast = _ema(closes, 12)
    slow = _ema(closes, 26)
    macd = fast - slow
    sig  = _ema(macd, 9)
    if macd[-1] > sig[-1] and macd[-2] <= sig[-2]:
        return "BULLISH"
    if macd[-1] < sig[-1] and macd[-2] >= sig[-2]:
        return "BEARISH"
    return "BULLISH" if macd[-1] > sig[-1] else "BEARISH"


def _bollinger(closes: np.ndarray, n: int = 20):
    w = closes[-n:]
    mid = w.mean()
    std = w.std()
    return mid + 2 * std, mid, mid - 2 * std


def analyze_set(quote: dict, history: List[dict]) -> SetAnalysis:
    closes = np.array([r["close"] for r in history], dtype=float)
    highs  = np.array([r["high"]  for r in history], dtype=float)
    lows   = np.array([r["low"]   for r in history], dtype=float)

    rsi = _rsi(closes)
    rsi_signal = "OVERSOLD" if rsi < 35 else ("OVERBOUGHT" if rsi > 65 else "NEUTRAL")

    macd_trend = _macd_cross(closes)

    ema9  = float(_ema(closes, 9)[-1])
    ema21 = float(_ema(closes, 21)[-1])
    ema50 = float(_ema(closes, min(50, len(closes) - 1))[-1])
    if ema9 > ema21 > ema50:
        ema_trend = "BULLISH"
    elif ema9 < ema21 < ema50:
        ema_trend = "BEARISH"
    else:
        ema_trend = "NEUTRAL"

    bb_up, bb_mid, bb_lo = _bollinger(closes)
    price = quote["price"]
    band = bb_up - bb_lo
    bb_pos = (price - bb_lo) / band if band > 0 else 0.5
    bb_signal = "OVERSOLD" if bb_pos < 0.15 else ("OVERBOUGHT" if bb_pos > 0.85 else "NEUTRAL")

    # ATR-based volatility
    trs = [max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
           for i in range(1, len(closes))]
    atr_pct = (np.array(trs[-14:]).mean() / price * 100) if price > 0 else 0
    volatility = "LOW" if atr_pct < 0.8 else ("HIGH" if atr_pct > 2.5 else "MEDIUM")

    # Composite signal
    buy, sell = 0.0, 0.0
    reasons = []

    if rsi_signal == "OVERSOLD":    buy  += 0.30; reasons.append(f"RSI={rsi:.0f} (oversold)")
    elif rsi_signal == "OVERBOUGHT": sell += 0.30; reasons.append(f"RSI={rsi:.0f} (overbought)")

    if macd_trend == "BULLISH":  buy  += 0.25; reasons.append("MACD bullish")
    elif macd_trend == "BEARISH": sell += 0.25; reasons.append("MACD bearish")

    if ema_trend == "BULLISH":  buy  += 0.25; reasons.append("EMA bullish")
    elif ema_trend == "BEARISH": sell += 0.25; reasons.append("EMA bearish")

    if bb_signal == "OVERSOLD":    buy  += 0.20; reasons.append("BB oversold")
    elif bb_signal == "OVERBOUGHT": sell += 0.20; reasons.append("BB overbought")

    if buy > sell and buy > 0.35:
        signal, confidence = "BUY",  min(buy, 1.0)
    elif sell > buy and sell > 0.35:
        signal, confidence = "SELL", min(sell, 1.0)
    else:
        signal, confidence = "HOLD", max(buy, sell)

    return SetAnalysis(
        symbol=quote["symbol"],
        name=quote.get("name", ""),
        sector=quote.get("sector", ""),
        price=price,
        change_1d=quote.get("change_1d", 0),
        signal=signal,
        confidence=round(confidence, 3),
        reasoning="; ".join(reasons) or "No clear signal",
        rsi=round(rsi, 1),
        rsi_signal=rsi_signal,
        macd_trend=macd_trend,
        ema_trend=ema_trend,
        bb_signal=bb_signal,
        bb_position=round(bb_pos, 3),
        volatility=volatility,
        support=round(bb_lo, 2),
        resistance=round(bb_up, 2),
    )
