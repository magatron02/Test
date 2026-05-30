import numpy as np
import pandas as pd
from typing import Optional
import ta


def compute_indicators(ohlcv: list) -> dict:
    if len(ohlcv) < 50:
        return {}

    df = pd.DataFrame(ohlcv)
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    # Trend
    ema9 = ta.trend.EMAIndicator(close, 9).ema_indicator()
    ema21 = ta.trend.EMAIndicator(close, 21).ema_indicator()
    ema50 = ta.trend.EMAIndicator(close, 50).ema_indicator()
    ema200 = ta.trend.EMAIndicator(close, 200).ema_indicator() if len(close) >= 200 else ema50

    macd = ta.trend.MACD(close)
    macd_line = macd.macd()
    macd_signal = macd.macd_signal()
    macd_hist = macd.macd_diff()

    # Momentum
    rsi = ta.momentum.RSIIndicator(close, 14).rsi()
    stoch = ta.momentum.StochasticOscillator(high, low, close)
    stoch_k = stoch.stoch()
    stoch_d = stoch.stoch_signal()

    # Volatility
    bb = ta.volatility.BollingerBands(close, 20, 2)
    bb_upper = bb.bollinger_hband()
    bb_lower = bb.bollinger_lband()
    bb_mid = bb.bollinger_mavg()
    bb_width = (bb_upper - bb_lower) / bb_mid * 100

    atr = ta.volatility.AverageTrueRange(high, low, close, 14).average_true_range()

    # Volume
    obv = ta.volume.OnBalanceVolumeIndicator(close, volume).on_balance_volume()

    current = close.iloc[-1]
    prev = close.iloc[-2]

    trend = "bullish" if ema9.iloc[-1] > ema21.iloc[-1] > ema50.iloc[-1] else \
            "bearish" if ema9.iloc[-1] < ema21.iloc[-1] < ema50.iloc[-1] else "sideways"

    return {
        "price": current,
        "price_change_pct": (current - prev) / prev * 100,
        "trend": trend,
        "ema9": round(ema9.iloc[-1], 4),
        "ema21": round(ema21.iloc[-1], 4),
        "ema50": round(ema50.iloc[-1], 4),
        "ema200": round(ema200.iloc[-1], 4),
        "macd": round(macd_line.iloc[-1], 4),
        "macd_signal": round(macd_signal.iloc[-1], 4),
        "macd_histogram": round(macd_hist.iloc[-1], 4),
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
        "is_overbought": rsi.iloc[-1] > 70,
        "is_oversold": rsi.iloc[-1] < 30,
        "above_ema200": current > ema200.iloc[-1],
        "volume_surge": volume.iloc[-1] > volume.rolling(20).mean().iloc[-1] * 1.5,
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
    size_by_risk = risk_amount / (entry_price * stop_distance)
    max_size = (portfolio_value * max_position_pct) / entry_price
    final_size = min(size_by_risk, max_size)

    return {
        "size": round(final_size, 6),
        "value": round(final_size * entry_price, 2),
        "risk_amount": round(risk_amount, 2),
        "stop_distance_pct": round(stop_distance * 100, 2),
    }
