"""Tests for AITrainer.score() — side-effect-free confidence used by the optimizer."""
import pytest

from src.agent.trainer import AITrainer


def _features():
    return {
        "rsi": 45.0, "macd_hist": 0.1, "bb_position": 0.5, "atr_pct": 1.2,
        "volume_ratio": 1.0, "price_vs_vwap": 0.5, "change_24h": 1.0,
        "ema_9": 101.0, "ema_21": 100.0,
    }


def test_score_returns_probability_in_range():
    trainer = AITrainer()
    s = trainer.score(_features())
    assert 0.0 <= s <= 1.0


def test_score_default_without_model():
    """With no trained model, score is the neutral 0.5 prior."""
    trainer = AITrainer()
    # Force the no-model path regardless of any seeded artifact
    trainer._model = None
    trainer._gbm = None
    assert trainer.score(_features()) == 0.5


def test_score_does_not_accumulate_drift_features():
    """score() must NOT pollute the drift detector's prediction buffer."""
    trainer = AITrainer()
    before_count = trainer._predict_count
    before_feats = {k: list(v) for k, v in trainer._recent_features.items()}
    for _ in range(10):
        trainer.score(_features())
    assert trainer._predict_count == before_count
    assert trainer._recent_features == before_feats
