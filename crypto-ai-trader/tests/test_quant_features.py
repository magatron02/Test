"""Tests for src/agent/quant_features.py."""
import numpy as np

from src.agent.quant_features import kalman_trend, garch_volatility, worldquant_alphas

SEED = 99
VALID_TREND = {"BULLISH", "BEARISH", "FLAT"}


def _series(n=120, drift=0.1, noise=0.5, seed=SEED):
    rng = np.random.default_rng(seed)
    price = 100.0
    out = []
    for _ in range(n):
        price = price * (1.0 + drift / 100.0) + rng.normal(0.0, noise)
        out.append(max(price, 1.0))
    return np.array(out, dtype=float)


def test_kalman_trend_valid_label():
    closes = _series()
    res = kalman_trend(closes)
    assert res["trend"] in VALID_TREND
    assert "velocity" in res
    assert "kalman_price" in res


def test_kalman_trend_insufficient_data_flat():
    res = kalman_trend(np.array([100.0, 101.0, 99.0], dtype=float))
    assert res["trend"] == "FLAT"
    assert res["velocity"] == 0.0


def test_garch_volatility_dict_nonnegative():
    rng = np.random.default_rng(SEED)
    returns = rng.normal(0.0, 1.5, size=120)  # >=50 -> GARCH path (with fallback)
    res = garch_volatility(returns)
    assert isinstance(res, dict)
    assert res["forecast_vol_pct"] >= 0.0
    assert res["regime_hint"] in {"RISING_VOL", "FALLING_VOL", "STABLE"}


def test_garch_volatility_tiny_input_fallback():
    res = garch_volatility(np.array([0.5, -0.3, 0.1], dtype=float))
    assert isinstance(res, dict)
    assert res["forecast_vol_pct"] >= 0.0


def test_worldquant_alphas_populated_on_enough_bars():
    n = 60
    rng = np.random.default_rng(SEED)
    closes = _series(n=n)
    opens = closes + rng.normal(0, 0.1, n)
    highs = np.maximum(opens, closes) + np.abs(rng.normal(0, 0.2, n))
    lows = np.minimum(opens, closes) - np.abs(rng.normal(0, 0.2, n))
    vols = np.abs(rng.normal(1000, 200, n))
    alphas = worldquant_alphas(opens, highs, lows, closes, vols)
    assert isinstance(alphas, dict)
    assert len(alphas) > 0
    assert "alpha101" in alphas
    for v in alphas.values():
        assert np.isfinite(v)


def test_worldquant_alphas_empty_on_short_input():
    short = np.arange(10, dtype=float)
    alphas = worldquant_alphas(short, short, short, short, short)
    assert alphas == {}
