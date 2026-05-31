import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import ta

from ..exchanges.base import OHLCV

logger = logging.getLogger(__name__)


@dataclass
class MarketAnalysis:
    symbol: str
    price: float
    change_24h: float

    rsi: float = 0.0
    rsi_signal: str = "NEUTRAL"   # OVERSOLD | NEUTRAL | OVERBOUGHT

    macd: float = 0.0
    macd_signal: float = 0.0
    macd_hist: float = 0.0
    macd_trend: str = "NEUTRAL"   # BULLISH | BEARISH | NEUTRAL

    ema_9: float = 0.0
    ema_21: float = 0.0
    ema_50: float = 0.0
    ema_trend: str = "NEUTRAL"    # BULLISH | BEARISH | NEUTRAL

    bb_upper: float = 0.0
    bb_middle: float = 0.0
    bb_lower: float = 0.0
    bb_position: float = 0.5      # 0=lower band, 1=upper band
    bb_signal: str = "NEUTRAL"    # OVERSOLD | NEUTRAL | OVERBOUGHT

    atr: float = 0.0
    atr_pct: float = 0.0          # ATR as % of price (volatility)
    volatility: str = "MEDIUM"    # LOW | MEDIUM | HIGH

    vwap: float = 0.0
    price_vs_vwap: str = "ABOVE"  # ABOVE | BELOW

    volume_ratio: float = 1.0     # current vs 20-period average
    volume_signal: str = "NORMAL" # LOW | NORMAL | HIGH

    overall_signal: str = "HOLD"  # BUY | SELL | HOLD
    signal_strength: float = 0.0  # 0-1
    features: Dict = field(default_factory=dict)


def _ohlcv_to_df(candles: List[OHLCV]) -> pd.DataFrame:
    df = pd.DataFrame([{
        "timestamp": c.timestamp,
        "open": c.open,
        "high": c.high,
        "low": c.low,
        "close": c.close,
        "volume": c.volume,
    } for c in candles])
    df.set_index("timestamp", inplace=True)
    return df


def analyze(symbol: str, candles: List[OHLCV], price: float, change_24h: float,
            rsi_period: int = 14, bb_period: int = 20, atr_period: int = 14) -> MarketAnalysis:
    if len(candles) < 30:
        return MarketAnalysis(symbol=symbol, price=price, change_24h=change_24h)

    df = _ohlcv_to_df(candles)
    result = MarketAnalysis(symbol=symbol, price=price, change_24h=change_24h)

    # RSI
    rsi_ind = ta.momentum.RSIIndicator(df["close"], window=rsi_period)
    result.rsi = float(rsi_ind.rsi().iloc[-1])
    if result.rsi < 30:
        result.rsi_signal = "OVERSOLD"
    elif result.rsi > 70:
        result.rsi_signal = "OVERBOUGHT"
    else:
        result.rsi_signal = "NEUTRAL"

    # MACD
    macd_ind = ta.trend.MACD(df["close"], window_slow=26, window_fast=12, window_sign=9)
    result.macd = float(macd_ind.macd().iloc[-1])
    result.macd_signal = float(macd_ind.macd_signal().iloc[-1])
    result.macd_hist = float(macd_ind.macd_diff().iloc[-1])
    prev_hist = float(macd_ind.macd_diff().iloc[-2]) if len(df) > 1 else 0
    if result.macd_hist > 0 and prev_hist <= 0:
        result.macd_trend = "BULLISH"
    elif result.macd_hist < 0 and prev_hist >= 0:
        result.macd_trend = "BEARISH"
    elif result.macd > result.macd_signal:
        result.macd_trend = "BULLISH"
    elif result.macd < result.macd_signal:
        result.macd_trend = "BEARISH"

    # EMA
    result.ema_9 = float(ta.trend.EMAIndicator(df["close"], window=9).ema_indicator().iloc[-1])
    result.ema_21 = float(ta.trend.EMAIndicator(df["close"], window=21).ema_indicator().iloc[-1])
    ema50_ind = ta.trend.EMAIndicator(df["close"], window=min(50, len(df) - 1))
    result.ema_50 = float(ema50_ind.ema_indicator().iloc[-1])
    if result.ema_9 > result.ema_21 > result.ema_50:
        result.ema_trend = "BULLISH"
    elif result.ema_9 < result.ema_21 < result.ema_50:
        result.ema_trend = "BEARISH"

    # Bollinger Bands
    bb_ind = ta.volatility.BollingerBands(df["close"], window=bb_period, window_dev=2)
    result.bb_upper = float(bb_ind.bollinger_hband().iloc[-1])
    result.bb_middle = float(bb_ind.bollinger_mavg().iloc[-1])
    result.bb_lower = float(bb_ind.bollinger_lband().iloc[-1])
    band_range = result.bb_upper - result.bb_lower
    if band_range > 0:
        result.bb_position = (price - result.bb_lower) / band_range
    if result.bb_position < 0.1:
        result.bb_signal = "OVERSOLD"
    elif result.bb_position > 0.9:
        result.bb_signal = "OVERBOUGHT"

    # ATR
    atr_ind = ta.volatility.AverageTrueRange(df["high"], df["low"], df["close"], window=atr_period)
    result.atr = float(atr_ind.average_true_range().iloc[-1])
    result.atr_pct = result.atr / price * 100 if price > 0 else 0
    if result.atr_pct < 1.0:
        result.volatility = "LOW"
    elif result.atr_pct > 3.0:
        result.volatility = "HIGH"

    # VWAP (rolling daily approximation)
    typical = (df["high"] + df["low"] + df["close"]) / 3
    vwap_series = (typical * df["volume"]).cumsum() / df["volume"].cumsum()
    result.vwap = float(vwap_series.iloc[-1])
    result.price_vs_vwap = "ABOVE" if price > result.vwap else "BELOW"

    # Volume
    vol_avg = df["volume"].rolling(20).mean().iloc[-1]
    curr_vol = df["volume"].iloc[-1]
    result.volume_ratio = curr_vol / vol_avg if vol_avg > 0 else 1.0
    if result.volume_ratio < 0.5:
        result.volume_signal = "LOW"
    elif result.volume_ratio > 2.0:
        result.volume_signal = "HIGH"

    # Composite signal
    buy_score = 0.0
    sell_score = 0.0

    if result.rsi_signal == "OVERSOLD":
        buy_score += 0.25
    elif result.rsi_signal == "OVERBOUGHT":
        sell_score += 0.25

    if result.macd_trend == "BULLISH":
        buy_score += 0.25
    elif result.macd_trend == "BEARISH":
        sell_score += 0.25

    if result.ema_trend == "BULLISH":
        buy_score += 0.20
    elif result.ema_trend == "BEARISH":
        sell_score += 0.20

    if result.bb_signal == "OVERSOLD":
        buy_score += 0.20
    elif result.bb_signal == "OVERBOUGHT":
        sell_score += 0.20

    if result.price_vs_vwap == "ABOVE" and result.volume_signal == "HIGH":
        buy_score += 0.10
    elif result.price_vs_vwap == "BELOW" and result.volume_signal == "HIGH":
        sell_score += 0.10

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
        "rsi": result.rsi,
        "macd_hist": result.macd_hist,
        "ema_9": result.ema_9,
        "ema_21": result.ema_21,
        "bb_position": result.bb_position,
        "atr_pct": result.atr_pct,
        "volume_ratio": result.volume_ratio,
        "price_vs_vwap": 1 if result.price_vs_vwap == "ABOVE" else 0,
        "change_24h": change_24h,
    }

    return result
