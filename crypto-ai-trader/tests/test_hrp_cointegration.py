"""Tests for HRP allocation and cointegration / pairs trading."""
import numpy as np
import pytest

from src.agent.hrp_allocator import hrp_weights, allocate_capital
from src.agent.cointegration import check_cointegration, pairs_signal

SEED = 7


def test_hrp_weights_sum_to_one(synthetic_returns):
    symbols = ["A", "B", "C", "D"]
    weights = hrp_weights(synthetic_returns, symbols)
    assert set(weights.keys()) == set(symbols)
    assert abs(sum(weights.values()) - 1.0) < 0.02
    for w in weights.values():
        assert w >= 0.0


def test_hrp_correlated_cluster_underweighted_per_asset(synthetic_returns):
    # Columns A,B,C share a common factor; D is independent.
    symbols = ["A", "B", "C", "D"]
    weights = hrp_weights(synthetic_returns, symbols)
    cluster_avg = (weights["A"] + weights["B"] + weights["C"]) / 3.0
    # Each member of the correlated cluster should get less weight than the
    # lone independent asset (HRP avoids double-counting correlated risk).
    assert cluster_avg < weights["D"]


def test_allocate_capital_respects_max_weight():
    rng = np.random.default_rng(SEED)
    T = 100
    common = rng.normal(0, 0.01, T)
    returns_by_symbol = {
        "A": (common + rng.normal(0, 0.001, T)).tolist(),
        "B": (common + rng.normal(0, 0.001, T)).tolist(),
        "C": rng.normal(0, 0.02, T).tolist(),
    }
    max_w = 0.40
    alloc = allocate_capital(10_000.0, returns_by_symbol, max_weight=max_w)
    assert set(alloc.keys()) == {"A", "B", "C"}
    total_weight = sum(v["weight"] for v in alloc.values())
    assert abs(total_weight - 1.0) < 0.02
    for v in alloc.values():
        assert v["weight"] <= max_w + 1e-6
        assert v["capital"] >= 0.0


def test_cointegration_true_on_constructed_pair():
    pytest.importorskip("statsmodels")
    rng = np.random.default_rng(SEED)
    n = 200
    # Shared stochastic trend -> cointegrated pair.
    common = np.cumsum(rng.normal(0, 1.0, n)) + 100.0
    a = common + rng.normal(0, 0.5, n)
    b = 2.0 * common + 5.0 + rng.normal(0, 0.5, n)
    res = check_cointegration(a, b)
    assert res["cointegrated"] is True
    assert res["p_value"] is not None and res["p_value"] < 0.05
    assert res["hedge_ratio"] is not None


def test_cointegration_false_on_independent_walks():
    pytest.importorskip("statsmodels")
    rng = np.random.default_rng(SEED)
    n = 200
    a = np.cumsum(rng.normal(0, 1.0, n)) + 100.0
    b = np.cumsum(rng.normal(0, 1.0, n)) + 100.0
    res = check_cointegration(a, b)
    assert res["cointegrated"] is False


def test_cointegration_short_input_safe():
    a = np.arange(10, dtype=float)
    b = np.arange(10, dtype=float)
    res = check_cointegration(a, b)
    assert res["cointegrated"] is False
    assert res["p_value"] is None


def test_pairs_signal_structure():
    pytest.importorskip("statsmodels")
    rng = np.random.default_rng(SEED)
    n = 120
    common = np.cumsum(rng.normal(0, 1.0, n)) + 100.0
    a = common + rng.normal(0, 0.5, n)
    b = common + rng.normal(0, 0.5, n)
    sig = pairs_signal(a, b)
    assert sig["signal"] in {"HOLD", "CLOSE", "SHORT_A_LONG_B", "LONG_A_SHORT_B"}
    assert 0.0 <= sig["confidence"] <= 1.0
