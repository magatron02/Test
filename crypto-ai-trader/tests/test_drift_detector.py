"""Tests for F3.4 drift detection (PSI-based)."""
import numpy as np
import pytest

from src.agent.drift_detector import psi, detect_feature_drift, DriftDetector


# ── psi pure function ─────────────────────────────────────────────────────────

def test_psi_identical_distributions():
    """Identical distributions → PSI ≈ 0."""
    data = list(np.random.default_rng(0).normal(0, 1, 200))
    score = psi(data, data)
    assert score < 0.01


def test_psi_different_distributions():
    """Clearly shifted distributions → PSI > 0.20."""
    rng = np.random.default_rng(1)
    baseline = list(rng.normal(0, 1, 500))
    current  = list(rng.normal(5, 1, 500))   # mean shifted by 5σ
    score = psi(baseline, current)
    assert score > 0.20


def test_psi_too_few_samples():
    assert psi([1, 2], [1, 2]) == 0.0


def test_psi_non_negative():
    rng = np.random.default_rng(2)
    for _ in range(10):
        a = list(rng.normal(0, 1, 100))
        b = list(rng.normal(rng.uniform(-3, 3), 1, 100))
        assert psi(a, b) >= 0.0


def test_psi_minor_drift_range():
    """Small perturbation → 0.0 < PSI < 0.20."""
    rng = np.random.default_rng(3)
    baseline = list(rng.normal(0, 1, 1000))
    current  = list(rng.normal(0.3, 1, 1000))   # small shift
    score = psi(baseline, current)
    assert 0.0 <= score < 0.50   # not catastrophic


# ── detect_feature_drift ──────────────────────────────────────────────────────

def test_detect_no_drift():
    rng = np.random.default_rng(4)
    baseline = {f: list(rng.normal(0, 1, 300)) for f in ["rsi", "atr"]}
    current  = {f: list(rng.normal(0, 1, 100)) for f in ["rsi", "atr"]}
    drift, scores = detect_feature_drift(baseline, current, threshold=0.20)
    assert not drift


def test_detect_drift_detected():
    rng = np.random.default_rng(5)
    baseline = {"rsi": list(rng.normal(0, 1, 500))}
    current  = {"rsi": list(rng.normal(10, 1, 500))}   # large shift
    drift, scores = detect_feature_drift(baseline, current, threshold=0.20)
    assert drift
    assert scores["rsi"] > 0.20


def test_detect_missing_feature_skipped():
    rng = np.random.default_rng(6)
    baseline = {"rsi": list(rng.normal(0, 1, 200)), "atr": list(rng.normal(0, 1, 200))}
    current  = {"rsi": list(rng.normal(0, 1, 100))}   # atr missing
    drift, scores = detect_feature_drift(baseline, current)
    assert "atr" in scores
    assert scores["atr"] == 0.0


# ── DriftDetector class ───────────────────────────────────────────────────────

def test_no_baseline_returns_false():
    dd = DriftDetector()
    drift, scores = dd.check({"rsi": [1.0, 2.0, 3.0]})
    assert not drift
    assert scores == {}


def test_baseline_then_no_drift():
    rng = np.random.default_rng(7)
    dd = DriftDetector()
    data = {f: list(rng.normal(0, 1, 300)) for f in ["rsi", "macd"]}
    dd.record_baseline(data)
    current = {f: list(rng.normal(0, 1, 100)) for f in ["rsi", "macd"]}
    drift, _ = dd.check(current)
    assert not drift


def test_baseline_then_drift():
    rng = np.random.default_rng(8)
    dd = DriftDetector(threshold=0.20)
    dd.record_baseline({"rsi": list(rng.normal(0, 1, 500))})
    current = {"rsi": list(rng.normal(8, 1, 500))}
    drift, scores = dd.check(current)
    assert drift
    assert dd.drift_count == 1


def test_summary_structure():
    dd = DriftDetector()
    rng = np.random.default_rng(9)
    dd.record_baseline({"rsi": list(rng.normal(0, 1, 200))})
    dd.check({"rsi": list(rng.normal(0, 1, 100))})
    s = dd.summary()
    assert "drift_count" in s
    assert "max_psi" in s
    assert "per_feature" in s
    assert "has_baseline" in s
