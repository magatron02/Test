"""Tests for F3.3 VaR/CVaR + Monte Carlo engine."""
import numpy as np
import pytest

from src.agent.var_engine import var_cvar, monte_carlo_maxdd, summarize


# ── var_cvar ──────────────────────────────────────────────────────────────────

def test_var_cvar_returns_positive():
    returns = [0.01, -0.02, 0.03, -0.04, 0.005, -0.015, 0.02]
    var, cvar = var_cvar(returns, confidence=0.95)
    assert var >= 0.0
    assert cvar >= var, "CVaR must be ≥ VaR"


def test_var_cvar_cvar_exceeds_var():
    """CVaR captures the worst tail so it should be >= VaR."""
    rng = np.random.default_rng(0)
    returns = list(rng.normal(0, 0.02, 200))
    var, cvar = var_cvar(returns)
    assert cvar >= var


def test_var_cvar_higher_confidence_higher_var():
    rng = np.random.default_rng(1)
    returns = list(rng.normal(0, 0.01, 500))
    var90, _ = var_cvar(returns, confidence=0.90)
    var99, _ = var_cvar(returns, confidence=0.99)
    assert var99 >= var90


def test_var_cvar_too_few_samples():
    var, cvar = var_cvar([0.01, -0.02], confidence=0.95)
    assert var == 0.0 and cvar == 0.0


def test_var_cvar_all_positive_returns():
    """All positive returns → VaR and CVaR should be ≈ 0."""
    returns = [0.01] * 100
    var, cvar = var_cvar(returns)
    assert var <= 0.001
    assert cvar <= 0.001


# ── monte_carlo_maxdd ─────────────────────────────────────────────────────────

def test_mc_maxdd_structure():
    rng = np.random.default_rng(2)
    returns = list(rng.normal(0, 0.01, 100))
    result = monte_carlo_maxdd(returns, n_paths=200, horizon=20)
    assert set(result.keys()) >= {"mean_maxdd", "p95_maxdd", "p99_maxdd", "prob_ruin", "n_paths", "horizon"}


def test_mc_maxdd_ordering():
    rng = np.random.default_rng(3)
    returns = list(rng.normal(0, 0.015, 200))
    result = monte_carlo_maxdd(returns, n_paths=500, horizon=30)
    assert result["p99_maxdd"] >= result["p95_maxdd"] >= result["mean_maxdd"] >= 0


def test_mc_maxdd_too_few_samples():
    result = monte_carlo_maxdd([0.01, -0.01], n_paths=100, horizon=10)
    assert result["mean_maxdd"] == 0.0


def test_mc_maxdd_prob_ruin_range():
    rng = np.random.default_rng(4)
    returns = list(rng.normal(0, 0.01, 200))
    result = monte_carlo_maxdd(returns, n_paths=300, horizon=20)
    assert 0.0 <= result["prob_ruin"] <= 1.0


def test_mc_maxdd_consistent_seed():
    returns = list(np.random.default_rng(5).normal(0, 0.01, 100))
    r1 = monte_carlo_maxdd(returns, n_paths=100, horizon=10, seed=99)
    r2 = monte_carlo_maxdd(returns, n_paths=100, horizon=10, seed=99)
    assert r1["mean_maxdd"] == r2["mean_maxdd"]


# ── summarize ─────────────────────────────────────────────────────────────────

def test_summarize_keys():
    rng = np.random.default_rng(6)
    returns = list(rng.normal(0, 0.01, 100))
    result = summarize(returns, mc_paths=100, mc_horizon=10)
    for k in ["var_pct", "cvar_pct", "confidence", "mean_maxdd", "p95_maxdd",
              "p99_maxdd", "prob_ruin", "n_paths", "horizon"]:
        assert k in result, f"Missing key: {k}"
