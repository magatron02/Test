"""Tests for src/agent/market_analyzer.py analyze()."""
from datetime import datetime

from src.agent.market_analyzer import analyze, MarketAnalysis
from src.exchanges.base import OHLCV

VALID_SIGNALS = {"BUY", "SELL", "HOLD"}
VALID_KALMAN = {"BULLISH", "BEARISH", "FLAT"}


def test_analyze_returns_valid_analysis(synthetic_candles):
    price = synthetic_candles[-1].close
    result = analyze("BTC/USDT", synthetic_candles, price=price, change_24h=2.5)

    assert isinstance(result, MarketAnalysis)
    assert 0.0 <= result.rsi <= 100.0
    assert result.overall_signal in VALID_SIGNALS
    assert isinstance(result.features, dict)
    assert len(result.features) > 0
    # core features present
    assert "rsi" in result.features
    assert "atr_pct" in result.features
    assert 0.0 <= result.signal_strength <= 1.0


def test_analyze_short_history_safe_default():
    candles = [
        OHLCV(timestamp=datetime(2024, 1, 1), open=100, high=101, low=99, close=100, volume=10)
        for _ in range(10)
    ]
    result = analyze("BTC/USDT", candles, price=100.0, change_24h=0.0)
    assert isinstance(result, MarketAnalysis)
    # safe default: HOLD with no crash
    assert result.overall_signal == "HOLD"
    assert result.symbol == "BTC/USDT"
    assert result.price == 100.0


def test_analyze_quant_fields_populated(synthetic_candles):
    price = synthetic_candles[-1].close
    result = analyze("ETH/USDT", synthetic_candles, price=price, change_24h=1.0)

    # Kalman
    assert result.kalman_trend in VALID_KALMAN
    # GARCH / EWMA fallback
    assert result.garch_forecast_vol_pct >= 0.0
    assert result.garch_regime_hint in {"RISING_VOL", "FALLING_VOL", "STABLE"}
    # WorldQuant alphas populated (>=30 bars supplied)
    assert isinstance(result.alphas, dict)
    assert len(result.alphas) > 0
    # alpha-prefixed features merged into feature vector
    assert any(k.startswith("wq_") for k in result.features)
