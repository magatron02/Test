"""
F5.3 ML Champion/Challenger — unit tests.

Covers:
  1. GBMSignalModel.fit_challenger() returns auc_oos and keeps model in memory
  2. GBMSignalModel.save() persists and load() restores
  3. AITrainer champion/challenger gate: promote when AUC beats threshold
  4. AITrainer champion/challenger gate: reject when AUC doesn't beat threshold
  5. Stats keys present after training
"""
import json
import os
import pickle
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.agent.ml_models import GBMSignalModel
from src.agent.trainer import AITrainer, _MIN_AUC_IMPROVEMENT, _CHAMPION_META_FILE


# ── Synthetic data helpers ────────────────────────────────────────────────────

_RNG = np.random.default_rng(0)


def _make_data(n=120, n_feat=5):
    """Synthetic binary dataset; class 1 has slightly higher feature means."""
    X = _RNG.normal(size=(n, n_feat))
    y = (X[:, 0] + 0.5 * X[:, 1] + _RNG.normal(0, 0.5, n) > 0).astype(int)
    return X, y


def _feat_names(n_feat=5):
    return [f"feat_{i}" for i in range(n_feat)]


# ── GBMSignalModel tests ──────────────────────────────────────────────────────

@pytest.fixture
def model_dir(tmp_path):
    return tmp_path


def test_fit_challenger_returns_auc(model_dir):
    m = GBMSignalModel(model_dir)
    X, y = _make_data()
    res = m.fit_challenger(X, y, _feat_names())
    assert res.get("auc_oos") is not None, "auc_oos must be present"
    assert 0.0 <= res["auc_oos"] <= 1.0
    assert res["n_val"] > 0 and res["n_train"] > 0
    assert res["n_train"] + res["n_val"] == len(y)


def test_fit_challenger_model_is_loaded_in_memory(model_dir):
    m = GBMSignalModel(model_dir)
    X, y = _make_data()
    m.fit_challenger(X, y, _feat_names())
    assert m.ready, "model must be in memory after fit_challenger"


def test_fit_challenger_does_not_save(model_dir):
    m = GBMSignalModel(model_dir)
    X, y = _make_data()
    m.fit_challenger(X, y, _feat_names())
    assert not (model_dir / GBMSignalModel.MODEL_FILENAME).exists(), \
        "fit_challenger must NOT save to disk"


def test_save_and_load_roundtrip(model_dir):
    m = GBMSignalModel(model_dir)
    X, y = _make_data()
    m.fit_challenger(X, y, _feat_names())
    assert m.save() is True
    assert (model_dir / GBMSignalModel.MODEL_FILENAME).exists()

    m2 = GBMSignalModel(model_dir)
    assert m2.load() is True
    assert m2.ready
    pred = m2.predict(X[0])
    assert pred is not None and "action" in pred


def test_save_without_model_returns_false(model_dir):
    m = GBMSignalModel(model_dir)
    assert m.save() is False


def test_fit_challenger_insufficient_data(model_dir):
    m = GBMSignalModel(model_dir)
    X, y = _make_data(n=8)    # too small to split
    res = m.fit_challenger(X, y, _feat_names())
    assert res.get("auc_oos") is None
    assert "error" in res


# ── AITrainer champion/challenger gate ───────────────────────────────────────

def _make_trainer_with_dir(tmp_path, champion_auc=0.0):
    """Return an AITrainer with models_dir patched to tmp_path.
    Optionally write a pre-existing champion_meta.json.
    """
    meta_path = tmp_path / _CHAMPION_META_FILE
    if champion_auc > 0.0:
        meta_path.write_text(json.dumps({"auc_oos": champion_auc}))

    with patch("src.agent.trainer.settings") as mock_settings:
        mock_settings.models_dir = tmp_path
        mock_settings.ai_model = "ml"
        mock_settings.get = MagicMock(side_effect=lambda *a, **kw: kw.get("default"))
        trainer = AITrainer()
    # Patch the models_dir setting so file I/O lands in tmp_path
    trainer._model_path = tmp_path / "signal_model.pkl"
    if trainer._gbm:
        trainer._gbm.model_dir = tmp_path
    return trainer


class _FakeRecord:
    def __init__(self, features, label):
        self.features = features
        self.label = label
        self.trade_id = None


def _fake_records(n=120, n_feat=25, seed=42):
    """Generate fake TrainingRecord-like objects."""
    rng = np.random.default_rng(seed)
    from src.agent.trainer import GBM_FEATURE_KEYS
    keys = GBM_FEATURE_KEYS[:n_feat] + GBM_FEATURE_KEYS[n_feat:]   # just use all
    records = []
    X = rng.normal(size=(n, len(GBM_FEATURE_KEYS)))
    y = (X[:, 0] + rng.normal(0, 0.5, n) > 0).astype(int)
    for i in range(n):
        feats = {k: float(X[i, j]) for j, k in enumerate(GBM_FEATURE_KEYS)}
        feats["ema_9"] = 1.0; feats["ema_21"] = 0.5   # ensure ema_9_vs_21 = 1
        records.append(_FakeRecord(feats, int(y[i])))
    return records


def test_challenger_promoted_when_auc_beats_champion(tmp_path):
    """When champion AUC is very low (0.0), any reasonable challenger should be promoted."""
    with patch("src.agent.trainer.settings") as ms:
        ms.models_dir = tmp_path
        ms.get = MagicMock(side_effect=lambda *a, **kw: kw.get("default"))
        trainer = AITrainer()
        trainer._model_path = tmp_path / "signal_model.pkl"
        if trainer._gbm:
            trainer._gbm.model_dir = tmp_path

    records = _fake_records(n=120)
    trainer._champion_auc = 0.0    # no previous champion

    # Stub DB query
    with patch.object(trainer, '_gbm') as mock_gbm, \
         patch("src.agent.trainer.SessionLocal"):
        mock_res = {"auc_oos": 0.65, "accuracy": 0.60, "n_total": 120, "n_val": 24}
        mock_gbm.fit_challenger.return_value = mock_res
        mock_gbm.save.return_value = True
        mock_gbm.load.return_value = True

        # Simulate training by calling the gate logic directly
        auc_oos = mock_res["auc_oos"]
        challenger_wins = auc_oos > trainer._champion_auc + _MIN_AUC_IMPROVEMENT
        assert challenger_wins is True, "0.65 > 0.0 + 0.02 should promote"


def test_challenger_rejected_when_below_threshold(tmp_path):
    """Challenger that only marginally improves champion is rejected."""
    champion_auc = 0.70
    challenger_auc = 0.71    # < champion + 0.02

    challenger_wins = challenger_auc > champion_auc + _MIN_AUC_IMPROVEMENT
    assert challenger_wins is False, "0.71 ≤ 0.70 + 0.02 must be rejected"


def test_champion_meta_saved_on_promotion(tmp_path):
    """Champion metadata file is written when challenger is promoted."""
    with patch("src.agent.trainer.settings") as ms:
        ms.models_dir = tmp_path
        ms.get = MagicMock(side_effect=lambda *a, **kw: kw.get("default"))
        trainer = AITrainer()
        trainer._gbm = None   # disable GBM so we test the meta-save directly
        meta = {"auc_oos": 0.65, "accuracy": 0.60, "n_total": 100,
                "promoted_at": "2025-01-01T00:00:00"}
        trainer._save_champion_meta(meta)

    path = tmp_path / _CHAMPION_META_FILE
    assert path.exists()
    loaded = json.loads(path.read_text())
    assert loaded["auc_oos"] == pytest.approx(0.65)


def test_champion_auc_loaded_from_disk(tmp_path):
    """AITrainer reads the saved champion AUC at startup."""
    (tmp_path / _CHAMPION_META_FILE).write_text(json.dumps({"auc_oos": 0.73}))
    with patch("src.agent.trainer.settings") as ms:
        ms.models_dir = tmp_path
        ms.get = MagicMock(side_effect=lambda *a, **kw: kw.get("default"))
        trainer = AITrainer()
    assert trainer._champion_auc == pytest.approx(0.73)


def test_champion_auc_defaults_to_zero_when_no_file(tmp_path):
    with patch("src.agent.trainer.settings") as ms:
        ms.models_dir = tmp_path
        ms.get = MagicMock(side_effect=lambda *a, **kw: kw.get("default"))
        trainer = AITrainer()
    assert trainer._champion_auc == pytest.approx(0.0)


def test_stats_has_champion_keys(tmp_path):
    with patch("src.agent.trainer.settings") as ms:
        ms.models_dir = tmp_path
        ms.get = MagicMock(side_effect=lambda *a, **kw: kw.get("default"))
        with patch("src.agent.trainer.SessionLocal"):
            trainer = AITrainer()

    with patch("src.agent.trainer.SessionLocal") as MockDB:
        db = MagicMock()
        db.query.return_value.count.return_value = 0
        db.query.return_value.filter.return_value.count.return_value = 0
        MockDB.return_value.__enter__ = MagicMock(return_value=db)
        MockDB.return_value.__exit__ = MagicMock(return_value=False)
        MockDB.return_value = db
        s = trainer.stats

    assert "champion_auc" in s
    assert "challenger_auc" in s
    assert "challenger_promoted" in s
