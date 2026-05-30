"""
Technical indicator computation using pure numpy/pandas — no external ta library needed.
"""
import numpy as np
import pandas as pd
from typing import Optional


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = _ema(series, fast)
    ema_slow = _ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = _ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _bollinger_bands(series: pd.Series, period: int = 20, std_dev: float = 2.0):
    mid = _sma(series, period)
    std = series.rolling(period).std()
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    return upper, mid, lower


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def _stochastic(high: pd.Series, low: pd.Series, close: pd.Series, k: int = 14, d: int = 3):
    lowest_low = low.rolling(k).min()
    highest_high = high.rolling(k).max()
    denom = highest_high - lowest_low
    stoch_k = 100 * (close - lowest_low) / denom.replace(0, np.nan)
    stoch_d = _sma(stoch_k, d)
    return stoch_k, stoch_d


def _obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = np.sign(close.diff())
    direction.iloc[0] = 0
    return (direction * volume).cumsum()


def compute_indicators(ohlcv: list) -> dict:
    if len(ohlcv) < 50:
        return {}

    df = pd.DataFrame(ohlcv)
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    volume = df["volume"].astype(float)

    ema9 = _ema(close, 9)
    ema21 = _ema(close, 21)
    ema50 = _ema(close, 50)
    ema200 = _ema(close, 200) if len(close) >= 200 else _ema(close, len(close) // 2)

    macd_line, macd_signal, macd_hist = _macd(close)
    rsi = _rsi(close, 14)
    stoch_k, stoch_d = _stochastic(high, low, close)
    bb_upper, bb_mid, bb_lower = _bollinger_bands(close, 20, 2.0)
    bb_width = (bb_upper - bb_lower) / bb_mid * 100
    atr = _atr(high, low, close, 14)
    obv = _obv(close, volume)

    current = close.iloc[-1]
    prev = close.iloc[-2]

    e9, e21, e50 = ema9.iloc[-1], ema21.iloc[-1], ema50.iloc[-1]
    trend = "bullish" if e9 > e21 > e50 else "bearish" if e9 < e21 < e50 else "sideways"

    return {
        "price": current,
        "price_change_pct": (current - prev) / prev * 100,
        "trend": trend,
        "ema9": round(e9, 4),
        "ema21": round(e21, 4),
        "ema50": round(e50, 4),
        "ema200": round(ema200.iloc[-1], 4),
        "macd": round(macd_line.iloc[-1], 4),
        "macd_signal": round(macd_signal.iloc[-1], 4),
        "macd_histogram": round(macd_hist.iloc[-1], 4),
        "macd_histogram_prev": round(macd_hist.iloc[-2], 4),
        "rsi": round(rsi.iloc[-1], 2),
        "stoch_k": round(stoch_k.iloc[-1], 2),
        "stoch_d": round(stoch_d.iloc[-1], 2),
        "bb_upper": round(bb_upper.iloc[-1], 4),
        "bb_mid": round(bb_mid.iloc[-1], 4),
        "bb_lower": round(bb_lower.iloc[-1], 4),
        "bb_width": round(bb_width.iloc[-1], 2),
        "atr": round(atr.iloc[-1], 4),
        "atr_pct": round(atr.iloc[-1] / current * 100, 2),
        "obv": round(obv.iloc[-1], 2),
        "obv_trend": "up" if obv.iloc[-1] > obv.iloc[-5] else "down",
        "is_overbought": bool(rsi.iloc[-1] > 70),
        "is_oversold": bool(rsi.iloc[-1] < 30),
        "above_ema200": bool(current > ema200.iloc[-1]),
        "volume_surge": bool(volume.iloc[-1] > volume.rolling(20).mean().iloc[-1] * 1.5),
        "support_level": round(low.rolling(20).min().iloc[-1], 4),
        "resistance_level": round(high.rolling(20).max().iloc[-1], 4),
    }


def calculate_grid_params(
    current_price: float,
    volatility_pct: float,
    investment: float,
    grid_count: int = 10,
) -> dict:
    range_pct = max(volatility_pct * 2, 5) / 100
    upper = current_price * (1 + range_pct)
    lower = current_price * (1 - range_pct)
    grid_spacing = (upper - lower) / grid_count
    per_grid_investment = investment / grid_count
    coins_per_grid = per_grid_investment / grid_spacing

    return {
        "upper_price": round(upper, 4),
        "lower_price": round(lower, 4),
        "grid_count": grid_count,
        "grid_spacing": round(grid_spacing, 4),
        "per_grid_investment": round(per_grid_investment, 2),
        "coins_per_grid": round(coins_per_grid, 6),
        "estimated_daily_profit_pct": round(volatility_pct * 0.3, 2),
    }


def calculate_position_size(
    portfolio_value: float,
    risk_pct: float,
    entry_price: float,
    stop_loss: float,
    max_position_pct: float = 0.05,
) -> dict:
    risk_amount = portfolio_value * risk_pct
    stop_distance = abs(entry_price - stop_loss) / entry_price
    size_by_risk = risk_amount / (entry_price * stop_distance) if stop_distance > 0 else 0
    max_size = (portfolio_value * max_position_pct) / entry_price
    final_size = min(size_by_risk, max_size)

    return {
        "size": round(final_size, 6),
        "value": round(final_size * entry_price, 2),
        "risk_amount": round(risk_amount, 2),
        "stop_distance_pct": round(stop_distance * 100, 2),
    }
