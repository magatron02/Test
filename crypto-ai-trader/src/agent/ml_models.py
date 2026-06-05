"""LightGBM gradient-boosting signal classifier with SHAP explanations.

Inspired by "Machine Learning for Trading" Ch.12. Provides a drop-in
gradient-boosted alternative/augmentation to the RandomForest signal model,
adding SHAP-based local and global feature-importance explanations.

lightgbm and shap are imported lazily inside methods so importing this module
never fails when the optional dependencies are absent; methods degrade
gracefully and log a warning instead.
"""

import logging
import pickle
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


class GBMSignalModel:
    """LightGBM binary signal classifier (1=win, 0=loss) with SHAP explainability."""

    MODEL_FILENAME = "gbm_signal_model.pkl"
    _SHAP_SAMPLE_LIMIT = 500

    def __init__(self, model_dir: Path):
        self.model_dir = Path(model_dir)
        self.model = None
        self.feature_names: list[str] = []
        self._explainer = None
        self._shap_global: Optional[np.ndarray] = None

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @property
    def _model_path(self) -> Path:
        return self.model_dir / self.MODEL_FILENAME

    @staticmethod
    def _positive_class_shap(shap_values) -> np.ndarray:
        """Normalise TreeExplainer output across shap/lightgbm versions.

        TreeExplainer may return:
          - a list [class0, class1] -> use index 1 (positive class)
          - a 3D ndarray (n, features, classes) -> take [..., 1]
          - a 2D ndarray (n, features) -> use as-is
        """
        if isinstance(shap_values, list):
            return np.asarray(shap_values[1])
        arr = np.asarray(shap_values)
        if arr.ndim == 3:
            return arr[..., 1]
        return arr

    def _build_explainer(self) -> None:
        """Build a SHAP TreeExplainer for the current model (best-effort)."""
        self._explainer = None
        if self.model is None:
            return
        try:
            import shap
        except Exception as exc:  # pragma: no cover - optional dependency
            logger.warning("shap unavailable; explanations disabled: %s", exc)
            return
        try:
            self._explainer = shap.TreeExplainer(self.model)
        except Exception as exc:
            logger.warning("Failed to build SHAP TreeExplainer: %s", exc)
            self._explainer = None

    # ------------------------------------------------------------------ #
    # Training
    # ------------------------------------------------------------------ #
    def fit(self, X: np.ndarray, y: np.ndarray, feature_names: list[str]) -> dict:
        """Train on full dataset and save immediately (legacy / fallback path)."""
        res = self.fit_challenger(X, y, feature_names)
        if res.get("auc_oos") is not None:
            self.save()
        return res

    def fit_challenger(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: list[str],
        val_fraction: float = 0.20,
    ) -> dict:
        """Train on the first (1-val_fraction) of data, evaluate OOS AUC on the
        last val_fraction, then refit on the full dataset so the model in memory
        is always trained on everything.  Does NOT save — the caller decides
        whether to promote this challenger to champion.

        Returns a dict with ``auc_oos``, ``accuracy`` (CV on train slice),
        ``n_train``, ``n_val``, ``n_total``.
        """
        try:
            import lightgbm as lgb
            from sklearn.metrics import roc_auc_score
            from sklearn.model_selection import TimeSeriesSplit, cross_val_score

            X = np.asarray(X, dtype=float)
            y = np.asarray(y).astype(int)
            n = int(X.shape[0])

            n_val   = max(int(n * val_fraction), 5)
            n_train = n - n_val
            if n_train < 10:
                return {"auc_oos": None, "error": "insufficient data for champion/challenger split"}

            X_tr, X_val = X[:n_train], X[n_train:]
            y_tr, y_val = y[:n_train], y[n_train:]

            self.feature_names = list(feature_names)

            challenger = lgb.LGBMClassifier(
                n_estimators=200, learning_rate=0.05, num_leaves=31,
                max_depth=6, subsample=0.8, colsample_bytree=0.8,
                random_state=42, n_jobs=-1, verbose=-1,
            )
            challenger.fit(X_tr, y_tr)

            # OOS AUC on the held-out time slice
            if len(np.unique(y_val)) < 2:
                auc_oos = 0.5   # can't discriminate with single class
            else:
                proba_val = challenger.predict_proba(X_val)[:, 1]
                auc_oos = float(roc_auc_score(y_val, proba_val))

            # CV accuracy on the training slice
            accuracy = None
            n_splits = max(2, min(5, n_train // 10 + 1))
            try:
                tscv = TimeSeriesSplit(n_splits=n_splits)
                scores = cross_val_score(challenger, X_tr, y_tr, cv=tscv, scoring="accuracy")
                accuracy = float(np.mean(scores))
            except Exception as exc:
                logger.debug("CV during fit_challenger failed: %s", exc)

            # Refit on the FULL dataset so if promoted the champion saw everything
            challenger.fit(X, y)
            self.model = challenger
            self._build_explainer()

            # Cache global SHAP importance on a sample of the full set
            self._shap_global = None
            if self._explainer is not None:
                try:
                    n_s = min(n, self._SHAP_SAMPLE_LIMIT)
                    rng = np.random.default_rng(42)
                    idx = rng.choice(n, n_s, replace=False)
                    sv = self._positive_class_shap(self._explainer.shap_values(X[idx]))
                    self._shap_global = np.mean(np.abs(sv), axis=0)
                except Exception as exc:
                    logger.debug("SHAP caching failed: %s", exc)

            return {
                "auc_oos":  round(auc_oos, 4),
                "accuracy": round(accuracy, 3) if accuracy is not None else None,
                "n_train":  n_train,
                "n_val":    n_val,
                "n_total":  n,
                "cv_folds": n_splits,
                "feature_names": self.feature_names,
            }
        except Exception as exc:
            logger.warning("GBMSignalModel.fit_challenger failed: %s", exc)
            return {"auc_oos": None, "error": str(exc)}

    def save(self) -> bool:
        """Explicitly persist the currently-loaded model to disk (champion promotion)."""
        if self.model is None:
            return False
        try:
            self.model_dir.mkdir(parents=True, exist_ok=True)
            with open(self._model_path, "wb") as fh:
                pickle.dump(
                    {
                        "model": self.model,
                        "feature_names": self.feature_names,
                        "shap_global": self._shap_global,
                    },
                    fh,
                )
            return True
        except Exception as exc:
            logger.warning("GBMSignalModel.save failed: %s", exc)
            return False

    # ------------------------------------------------------------------ #
    # Inference
    # ------------------------------------------------------------------ #
    def predict(self, x: np.ndarray) -> Optional[dict]:
        if self.model is None:
            return None
        try:
            row = np.asarray(x, dtype=float).reshape(1, -1)
            proba = self.model.predict_proba(row)[0]
            proba_win = float(proba[1])
            confidence = float(np.max(proba))
            action = "BUY" if proba_win >= 0.5 else "SELL"
            return {
                "action": action,
                "confidence": confidence,
                "proba_win": proba_win,
            }
        except Exception as exc:
            logger.warning("GBMSignalModel.predict failed: %s", exc)
            return None

    def explain(self, x: np.ndarray) -> list[dict]:
        if self._explainer is None:
            return []
        try:
            row = np.asarray(x, dtype=float).reshape(1, -1)
            sv = self._positive_class_shap(self._explainer.shap_values(row))
            sv = np.asarray(sv).reshape(-1)
            values = row.reshape(-1)
            n = min(len(self.feature_names), len(sv), len(values))
            contributions = [
                {
                    "feature": self.feature_names[i],
                    "shap": float(sv[i]),
                    "value": float(values[i]),
                }
                for i in range(n)
            ]
            contributions.sort(key=lambda d: abs(d["shap"]), reverse=True)
            return contributions
        except Exception as exc:
            logger.warning("GBMSignalModel.explain failed: %s", exc)
            return []

    def global_importance(self) -> list[dict]:
        if self.model is None:
            return []
        try:
            if self._shap_global is not None:
                importance = np.asarray(self._shap_global, dtype=float)
            else:
                raw = np.asarray(
                    self.model.feature_importances_, dtype=float
                )
                total = raw.sum()
                importance = raw / total if total > 0 else raw
            n = min(len(self.feature_names), len(importance))
            items = [
                {"feature": self.feature_names[i], "importance": float(importance[i])}
                for i in range(n)
            ]
            items.sort(key=lambda d: d["importance"], reverse=True)
            return items
        except Exception as exc:
            logger.warning("GBMSignalModel.global_importance failed: %s", exc)
            return []

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #
    def load(self) -> bool:
        if not self._model_path.exists():
            return False
        try:
            with open(self._model_path, "rb") as fh:
                payload = pickle.load(fh)
            self.model = payload.get("model")
            self.feature_names = list(payload.get("feature_names", []))
            self._shap_global = payload.get("shap_global")
            if self.model is None:
                return False
            self._build_explainer()
            return True
        except Exception as exc:
            logger.warning("GBMSignalModel.load failed: %s", exc)
            return False

    @property
    def ready(self) -> bool:
        return self.model is not None
