import logging
import pickle
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from .drift_detector import DriftDetector
from .strategy_manager import TradingSignal
from ..core.config import settings
from ..core.database import SessionLocal, TrainingRecord

logger = logging.getLogger(__name__)

FEATURE_KEYS = [
    "rsi", "macd_hist", "bb_position", "atr_pct",
    "volume_ratio", "price_vs_vwap", "change_24h",
    "ema_9_vs_21",  # computed
]

# Extended, ordered feature set for the gradient-boosting model (ML4T Ch.12).
# Kept stable so persisted models stay compatible across restarts.
GBM_FEATURE_KEYS = [
    "rsi", "macd_hist", "bb_position", "atr_pct", "volume_ratio",
    "price_vs_vwap", "change_24h", "ema_9_vs_21",
    "stoch_rsi_k", "williams_r", "cci", "smc_buy", "smc_sell",
    "ichimoku_bull", "supertrend_buy", "rsi_div_bull", "rsi_div_bear",
    "kalman_velocity", "kalman_dev_pct", "garch_vol_ratio",
    "wq_alpha101", "wq_mom_5", "wq_mom_10", "wq_vol_zscore", "wq_close_to_high",
]


class AITrainer:
    def __init__(self):
        self._model = None
        self._model_path = settings.models_dir / "signal_model.pkl"
        self._stats = {
            "total_records": 0,
            "labelled_records": 0,
            "last_trained": None,
            "accuracy": None,
            "training_trades": 0,
            "model_type": "none",
        }
        self._trades_since_train = 0
        # F3.4 — drift detection
        self._drift_detector = DriftDetector()
        self._recent_features: Dict[str, List[float]] = {}   # feature → recent values
        self._predict_count = 0
        # Gradient-boosting model with SHAP explanations (primary when available)
        self._gbm = None
        try:
            from .ml_models import GBMSignalModel
            self._gbm = GBMSignalModel(settings.models_dir)
            if self._gbm.load():
                self._stats["model_type"] = "lightgbm"
                logger.info("Loaded existing LightGBM signal model")
        except Exception as e:
            logger.debug("GBM model unavailable, using RandomForest: %s", e)
        self._load_model()

    def _load_model(self):
        # First run: seed the active model from the bundled seed (if shipped),
        # so a fresh install has predictions immediately. The active model is
        # never shipped in the package, so user-trained models survive updates.
        if not self._model_path.exists():
            seed = self._model_path.with_name("signal_model.seed.pkl")
            if seed.exists():
                try:
                    import shutil
                    shutil.copy(seed, self._model_path)
                    logger.info("Seeded ML model from bundled seed")
                except Exception as e:
                    logger.warning(f"Could not seed model: {e}")
        if self._model_path.exists():
            try:
                with open(self._model_path, "rb") as f:
                    self._model = pickle.load(f)
                logger.info("Loaded existing ML model")
            except Exception as e:
                logger.warning(f"Could not load model: {e}")

    def _save_model(self):
        with open(self._model_path, "wb") as f:
            pickle.dump(self._model, f)

    def record_trade(self, symbol: str, features: Dict, action: str, trade_id: Optional[int] = None):
        db = SessionLocal()
        try:
            record = TrainingRecord(
                symbol=symbol,
                features=features,
                action=action,
                outcome=None,
                label=None,
                trade_id=trade_id,
            )
            db.add(record)
            db.commit()
            self._stats["total_records"] += 1
        finally:
            db.close()

    def update_outcome(self, trade_id: int, pnl_pct: float):
        db = SessionLocal()
        try:
            record = db.query(TrainingRecord).filter_by(trade_id=trade_id).first()
            if record:
                record.outcome = pnl_pct
                record.label = 1 if pnl_pct > 0 else 0
                db.commit()
                self._stats["labelled_records"] += 1
                self._trades_since_train += 1

                retrain_interval = settings.get("ai", "ml", "retrain_interval", default=50)
                if self._trades_since_train >= retrain_interval:
                    self.train()
        finally:
            db.close()

    def _extract_features(self, features: Dict) -> List[float]:
        ema_9_vs_21 = 1.0 if features.get("ema_9", 0) > features.get("ema_21", 0) else -1.0
        return [
            features.get("rsi", 50) / 100,
            features.get("macd_hist", 0),
            features.get("bb_position", 0.5),
            features.get("atr_pct", 1.0) / 5,
            min(features.get("volume_ratio", 1.0), 5.0) / 5,
            features.get("price_vs_vwap", 0.5),
            features.get("change_24h", 0) / 10,
            ema_9_vs_21,
        ]

    def _extract_gbm_features(self, features: Dict) -> List[float]:
        """Build the extended GBM feature vector in a stable column order.

        Unlike the RandomForest path this keeps raw (unscaled) values — tree
        models are scale-invariant, and SHAP reads cleaner on native units.
        """
        f = dict(features)
        f["ema_9_vs_21"] = 1.0 if f.get("ema_9", 0) > f.get("ema_21", 0) else -1.0
        return [float(f.get(k, 0.0) or 0.0) for k in GBM_FEATURE_KEYS]

    def train(self) -> bool:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import cross_val_score

        min_samples = settings.get("ai", "ml", "min_training_samples", default=30)
        db = SessionLocal()
        try:
            records = db.query(TrainingRecord).filter(
                TrainingRecord.label.isnot(None)
            ).all()
        finally:
            db.close()

        if len(records) < min_samples:
            logger.info(f"Not enough training data: {len(records)}/{min_samples}")
            return False

        X, y = [], []
        for r in records:
            if r.features and r.label is not None:
                X.append(self._extract_features(r.features))
                y.append(r.label)

        if len(X) < min_samples:
            return False

        X_arr = np.array(X)
        y_arr = np.array(y)

        # ── Primary: LightGBM + SHAP (ML4T Ch.12) ───────────────────────────
        if self._gbm is not None:
            try:
                Xg = np.array([
                    self._extract_gbm_features(r.features)
                    for r in records if r.features and r.label is not None
                ])
                yg = y_arr
                res = self._gbm.fit(Xg, yg, GBM_FEATURE_KEYS)
                if res.get("accuracy") is not None:
                    self._trades_since_train = 0
                    self._stats.update({
                        "last_trained":    datetime.utcnow().isoformat(),
                        "accuracy":        round(res["accuracy"], 3),
                        "training_trades": len(records),
                        "model_type":      "lightgbm",
                    })
                    logger.info("LightGBM trained on %d samples, CV acc=%.3f",
                                len(records), res["accuracy"])
                    self._record_drift_baseline(records, use_gbm=True)
                    return True
                logger.warning("GBM fit failed (%s); falling back to RandomForest",
                               res.get("error"))
            except Exception as e:
                logger.warning("GBM training error, using RandomForest: %s", e)

        # ── Fallback: RandomForest ──────────────────────────────────────────
        model = RandomForestClassifier(n_estimators=100, max_depth=6, random_state=42, n_jobs=-1)
        scores = cross_val_score(model, X_arr, y_arr, cv=min(5, len(X) // 10 + 1), scoring="accuracy")
        accuracy = float(scores.mean())

        model.fit(X_arr, y_arr)
        self._model = model
        self._save_model()
        self._trades_since_train = 0

        self._stats.update({
            "last_trained": datetime.utcnow().isoformat(),
            "accuracy": round(accuracy, 3),
            "training_trades": len(records),
            "model_type": "random_forest",
        })

        logger.info(f"Model trained on {len(records)} samples, accuracy={accuracy:.3f}")
        self._record_drift_baseline(records, use_gbm=False)
        return True

    # ── F3.4 Drift helpers ────────────────────────────────────────────────

    def _record_drift_baseline(self, records, *, use_gbm: bool):
        """Snapshot training-time feature distributions for PSI baseline."""
        baseline: Dict[str, List[float]] = {}
        key_list = GBM_FEATURE_KEYS if use_gbm else FEATURE_KEYS
        for r in records:
            if not r.features:
                continue
            vec = (self._extract_gbm_features(r.features) if use_gbm
                   else self._extract_features(r.features))
            for i, k in enumerate(key_list):
                baseline.setdefault(k, []).append(float(vec[i]))
        self._drift_detector.record_baseline(baseline)
        self._recent_features = {}
        self._predict_count = 0

    def _accumulate_predict_features(self, features: Dict, *, use_gbm: bool):
        """Buffer incoming feature values for drift check."""
        key_list = GBM_FEATURE_KEYS if use_gbm else FEATURE_KEYS
        vec = (self._extract_gbm_features(features) if use_gbm
               else self._extract_features(features))
        for i, k in enumerate(key_list):
            self._recent_features.setdefault(k, []).append(float(vec[i]))

    def _maybe_check_drift(self):
        """Check drift every 50 predictions; trigger retrain on significant drift."""
        self._predict_count += 1
        if self._predict_count % 50 != 0:
            return
        if not self._drift_detector.has_baseline():
            return
        drift, _ = self._drift_detector.check(self._recent_features)
        if drift:
            logger.warning("Drift detected — scheduling retrain")
            self.train()

    def score(self, features: Dict) -> float:
        """
        Side-effect-free model confidence in [0, 1] for a single feature row.

        Unlike :meth:`predict` this does NOT accumulate drift statistics or build
        a TradingSignal — it is meant for batch/offline use (e.g. the param
        optimizer scoring many historical candles). Returns 0.5 when no model
        is ready.
        """
        if self._gbm is not None and self._gbm.ready:
            try:
                pred = self._gbm.predict(np.array(self._extract_gbm_features(features)))
                if pred:
                    return float(pred.get("confidence", 0.5))
            except Exception:
                pass
        if self._model is not None:
            try:
                feat_vec = np.array([self._extract_features(features)])
                return float(max(self._model.predict_proba(feat_vec)[0]))
            except Exception:
                pass
        return 0.5

    def predict(self, features: Dict) -> Optional[TradingSignal]:
        # ── Primary: LightGBM with SHAP-backed reasoning ────────────────────
        if self._gbm is not None and self._gbm.ready:
            try:
                x = np.array(self._extract_gbm_features(features))
                pred = self._gbm.predict(x)
                if pred:
                    self._accumulate_predict_features(features, use_gbm=True)
                    self._maybe_check_drift()
                    top = self._gbm.explain(x)[:3]
                    drivers = ", ".join(
                        f"{d['feature']}({d['shap']:+.2f})" for d in top
                    ) if top else "—"
                    return TradingSignal(
                        action=pred["action"],
                        confidence=pred["confidence"],
                        strategy="ml",
                        reasoning=(f"LightGBM {pred['confidence']:.0%} | "
                                   f"top drivers: {drivers}"),
                        stop_loss_pct=0.03,
                        take_profit_pct=0.06,
                    )
            except Exception as e:
                logger.debug("GBM predict failed, trying RandomForest: %s", e)

        # ── Fallback: RandomForest ──────────────────────────────────────────
        if self._model is None:
            return None
        try:
            feat_vec = np.array([self._extract_features(features)])
            self._accumulate_predict_features(features, use_gbm=False)
            self._maybe_check_drift()
            pred = self._model.predict(feat_vec)[0]
            proba = self._model.predict_proba(feat_vec)[0]
            confidence = float(max(proba))
            action = "BUY" if pred == 1 else "SELL"
            return TradingSignal(
                action=action,
                confidence=confidence,
                strategy="ml",
                reasoning=f"ML model: {confidence:.0%} confidence (trained on {self._stats['training_trades']} trades)",
                stop_loss_pct=0.03,
                take_profit_pct=0.06,
            )
        except Exception as e:
            logger.warning(f"ML prediction failed: {e}")
            return None

    def feature_importance(self) -> List[dict]:
        """Return global SHAP feature importance (ML4T Ch.12) for the dashboard."""
        if self._gbm is not None and self._gbm.ready:
            try:
                return self._gbm.global_importance()
            except Exception as e:
                logger.debug("SHAP importance unavailable: %s", e)
        # Fallback: RandomForest feature_importances_
        if self._model is not None and hasattr(self._model, "feature_importances_"):
            imps = self._model.feature_importances_
            return sorted(
                [{"feature": k, "importance": float(v)}
                 for k, v in zip(FEATURE_KEYS, imps)],
                key=lambda d: -d["importance"],
            )
        return []

    @property
    def stats(self) -> dict:
        db = SessionLocal()
        try:
            total = db.query(TrainingRecord).count()
            labelled = db.query(TrainingRecord).filter(TrainingRecord.label.isnot(None)).count()
        finally:
            db.close()
        self._stats["total_records"] = total
        self._stats["labelled_records"] = labelled
        gbm_ready = self._gbm is not None and self._gbm.ready
        self._stats["model_ready"] = gbm_ready or (self._model is not None)
        self._stats["drift"] = self._drift_detector.summary()
        return dict(self._stats)
