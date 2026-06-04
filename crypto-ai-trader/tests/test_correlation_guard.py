"""Tests for RiskEngine correlation guard (F3.2)."""
import math

from src.agent.risk_engine import RiskEngine


def _linear(n, slope, noise=0.0):
    return [slope * i + (noise if i % 2 == 0 else -noise) for i in range(n)]


def test_pearson_perfect_correlation():
    a = [0.01, 0.02, -0.01, 0.03, -0.02, 0.04]
    b = [2 * x for x in a]  # perfectly correlated (positive scale)
    c = RiskEngine._pearson(a, b)
    assert c is not None
    assert math.isclose(c, 1.0, abs_tol=1e-9)


def test_pearson_anticorrelation():
    a = [0.01, 0.02, -0.01, 0.03, -0.02, 0.04]
    b = [-x for x in a]
    c = RiskEngine._pearson(a, b)
    assert math.isclose(c, -1.0, abs_tol=1e-9)


def test_pearson_insufficient_data():
    assert RiskEngine._pearson([0.1, 0.2], [0.1, 0.2]) is None


def test_guard_blocks_highly_correlated_candidate():
    re = RiskEngine({"max_correlation": 0.80})
    base = [0.01, -0.02, 0.03, -0.01, 0.02, -0.03, 0.015]
    candidate = [2 * x for x in base]            # ~1.0 correlation
    portfolio = {"ETH/USDT": base}
    allowed, reason, avg = re.check_correlation(candidate, portfolio)
    assert allowed is False
    assert avg is not None and avg > 0.80
    assert "Correlation" in reason


def test_guard_allows_uncorrelated_candidate():
    re = RiskEngine({"max_correlation": 0.80})
    held = [0.01, -0.02, 0.03, -0.01, 0.02, -0.03, 0.015]
    candidate = [-0.03, 0.04, 0.00, 0.05, -0.04, 0.01, -0.02]  # different shape
    allowed, reason, avg = re.check_correlation(candidate, {"ETH/USDT": held})
    assert allowed is True


def test_guard_allows_when_no_positions():
    re = RiskEngine({"max_correlation": 0.80})
    allowed, reason, avg = re.check_correlation([0.01, 0.02, 0.03, 0.04, 0.05], {})
    assert allowed is True
    assert avg is None


def test_guard_disabled_always_allows():
    re = RiskEngine({"max_correlation": 0.10, "correlation_guard_enabled": False})
    base = [0.01, -0.02, 0.03, -0.01, 0.02, -0.03, 0.015]
    candidate = [2 * x for x in base]
    allowed, _, _ = re.check_correlation(candidate, {"ETH/USDT": base})
    assert allowed is True
