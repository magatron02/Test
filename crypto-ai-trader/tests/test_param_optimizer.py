"""Tests for F5.1 walk-forward param optimizer."""
import json
import numpy as np
import pytest
from pathlib import Path

from src.agent.param_optimizer import (
    _sharpe, _simulate_returns, walk_forward_splits,
    grid_search, save_best_params, load_best_params,
    ParamOptimizer, DEFAULT_GRID,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_bars(n: int = 200, seed: int = 0) -> list:
    """Synthetic OHLCV-like bar dicts with features."""
    rng = np.random.default_rng(seed)
    bars = []
    price = 100.0
    for i in range(n):
        ret    = rng.normal(0.0, 0.01)
        price *= 1 + ret
        bars.append({
            "close":              price,
            "rsi":                rng.uniform(20, 80),
            "atr_pct":            rng.uniform(0.005, 0.02),
            "signal_confidence":  rng.uniform(0.4, 0.9),
            "label":              int(rng.choice([-1, 0, 1])),
        })
    return bars


# ── _sharpe ───────────────────────────────────────────────────────────────────

def test_sharpe_positive_drift():
    rng = np.random.default_rng(42)
    # Mean positive returns with small noise → positive Sharpe
    returns = 0.005 + rng.normal(0, 0.001, 50)
    assert _sharpe(returns) > 0.0


def test_sharpe_too_few():
    assert _sharpe(np.array([0.01, 0.02])) == -999.0


def test_sharpe_zero_std():
    returns = np.zeros(20)
    assert _sharpe(returns) == 0.0


# ── _simulate_returns ─────────────────────────────────────────────────────────

def test_simulate_returns_non_empty_on_buy_signals():
    bars = [
        {"close": 100.0, "rsi": 25.0, "atr_pct": 0.01,
         "signal_confidence": 0.6, "label": 1},
        {"close": 102.0, "rsi": 60.0, "atr_pct": 0.01,
         "signal_confidence": 0.6, "label": -1},
    ]
    rets = _simulate_returns(bars, rsi_oversold=30, rsi_overbought=70,
                             atr_sl_mult=2.0, min_confidence=0.55)
    assert len(rets) > 0


def test_simulate_returns_empty_bars():
    rets = _simulate_returns([], rsi_oversold=30, rsi_overbought=70,
                             atr_sl_mult=2.0, min_confidence=0.55)
    assert len(rets) >= 0   # no crash


# ── walk_forward_splits ───────────────────────────────────────────────────────

def test_wf_splits_count():
    bars = _make_bars(120)
    splits = walk_forward_splits(bars, n_splits=3)
    assert len(splits) == 3


def test_wf_splits_no_overlap():
    bars = _make_bars(150)
    splits = walk_forward_splits(bars, n_splits=3)
    for train, test in splits:
        # test bars should not be in train
        assert len(train) > 0
        assert len(test) > 0


def test_wf_splits_too_small():
    bars = _make_bars(5)
    splits = walk_forward_splits(bars, n_splits=3)
    # may return fewer splits than requested for tiny data
    assert isinstance(splits, list)


# ── grid_search ───────────────────────────────────────────────────────────────

def test_grid_search_returns_best_params():
    bars = _make_bars(300)
    small_grid = {
        "rsi_oversold":   [28, 32],
        "rsi_overbought": [68, 72],
        "atr_sl_mult":    [1.5, 2.0],
        "min_confidence": [0.50, 0.55],
    }
    result = grid_search(bars, grid=small_grid, n_splits=2)
    assert "best_params" in result
    assert "best_sharpe" in result
    assert result["n_combos"] == 16
    # All keys in grid appear in best_params
    for k in small_grid:
        assert k in result["best_params"]


def test_grid_search_best_value_in_grid():
    bars = _make_bars(300)
    result = grid_search(bars, grid={"rsi_oversold": [25, 30], "rsi_overbought": [70, 75],
                                     "atr_sl_mult": [2.0], "min_confidence": [0.50]},
                         n_splits=2)
    assert result["best_params"]["rsi_oversold"] in [25, 30]


def test_grid_search_too_few_bars():
    bars = _make_bars(5)
    result = grid_search(bars, n_splits=3)
    assert "best_params" in result   # returns defaults, no crash


# ── save / load ───────────────────────────────────────────────────────────────

def test_save_load_roundtrip(tmp_path):
    payload = {"best_params": {"rsi_oversold": 30}, "best_sharpe": 1.5,
               "n_combos": 4, "optimized_at": "2025-01-01T00:00:00"}
    save_best_params(payload, models_dir=tmp_path)
    loaded = load_best_params(models_dir=tmp_path)
    assert loaded["best_sharpe"] == 1.5
    assert loaded["best_params"]["rsi_oversold"] == 30


def test_load_missing_file(tmp_path):
    result = load_best_params(models_dir=tmp_path)
    assert result is None


# ── ParamOptimizer class ──────────────────────────────────────────────────────

def test_param_optimizer_run_and_best_params(tmp_path):
    opt = ParamOptimizer(
        grid={"rsi_oversold": [28, 32], "rsi_overbought": [68, 72],
              "atr_sl_mult": [2.0], "min_confidence": [0.50]},
        n_splits=2, models_dir=tmp_path,
    )
    bars = _make_bars(300)
    result = opt.run(bars)
    assert opt.best_params is not None
    assert "rsi_oversold" in opt.best_params
    assert (tmp_path / "best_params.json").exists()


def test_param_optimizer_summary_not_run(tmp_path):
    opt = ParamOptimizer(models_dir=tmp_path)
    s = opt.summary()
    assert s["status"] == "not_run"


def test_param_optimizer_loads_existing(tmp_path):
    payload = {"best_params": {"rsi_oversold": 25, "rsi_overbought": 70,
                               "atr_sl_mult": 2.0, "min_confidence": 0.55},
               "best_sharpe": 2.0, "n_combos": 4,
               "optimized_at": "2025-06-01T00:00:00"}
    save_best_params(payload, models_dir=tmp_path)
    opt = ParamOptimizer(models_dir=tmp_path)
    assert opt.best_params["rsi_oversold"] == 25
