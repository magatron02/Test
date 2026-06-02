import logging
import joblib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from .strategy_manager import TradingSignal
from ..core.config import settings
from ..core.database import SessionLocal, TrainingRecord, ModelVersion

logger = logging.getLogger(__name__)


FEATURE_KEYS = [
    "rsi", "macd_hist", "bb_position", "atr_pct",
    "volume_ratio", "price_vs_vwap", "change_24h",
    "ema_9_vs_21",
]

# Minimum improvement ratio: new val_accuracy must be >= best * (1 - TOLERANCE)
# before we replace the active model.
KEEP_BEST_TOLERANCE = 0.03   # allow up to 3% regression (more data → worth it)
VAL_SPLIT = 0.25             # newest 25% of samples used for validation


class AITrainer:
    def __init__(self):
        self._model = None
        self._model_path = settings.models_dir / "signal_model.pkl"
        self._stats = {
            "total_records": 0,
            "labelled_records": 0,
            "last_trained": None,
            "accuracy": None,
            "val_accuracy": None,
            "training_trades": 0,
            "model_version": 0,
            "best_val_accuracy": None,
        }
        self._trades_since_train = 0
        self._pending_train = False   # set True when retrain threshold hit; consumed by run_cycle
        self._load_model()
        self._load_stats_from_db()

    # ── startup ──────────────────────────────────────────────────
    def _load_model(self):
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
                self._model = joblib.load(self._model_path)
                logger.info("Loaded existing ML model")
            except Exception as e:
                logger.warning(f"Could not load model: {e}")

    def _load_stats_from_db(self):
        """Restore model version stats from DB so a restart doesn't reset metrics."""
        db = SessionLocal()
        try:
            latest = (
                db.query(ModelVersion)
                .filter(ModelVersion.kept == True)
                .order_by(ModelVersion.version.desc())
                .first()
            )
            if latest:
                self._stats["model_version"] = latest.version
                self._stats["accuracy"] = latest.cv_accuracy
                self._stats["val_accuracy"] = latest.val_accuracy
                self._stats["training_trades"] = latest.training_samples or 0
                self._stats["last_trained"] = latest.saved_at.isoformat() if latest.saved_at else None
                # best val accuracy across all kept versions
                best = (
                    db.query(ModelVersion)
                    .filter(ModelVersion.kept == True)
                    .order_by(ModelVersion.val_accuracy.desc())
                    .first()
                )
                self._stats["best_val_accuracy"] = best.val_accuracy if best else None
                logger.info(
                    f"Restored model stats: v{latest.version}, "
                    f"cv={latest.cv_accuracy}, val={latest.val_accuracy}"
                )
        except Exception as e:
            logger.warning(f"Could not restore model stats from DB: {e}")
        finally:
            db.close()

    def _save_model(self):
        joblib.dump(self._model, self._model_path)

    # ── recording ────────────────────────────────────────────────
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
                # Direction-aware label:
                #   BUY trade profitable  → 1 (BUY was correct)
                #   BUY trade loss        → 0 (should have avoided / SELL)
                #   SELL trade profitable → 0 (SELL/short was correct)
                #   SELL trade loss       → 1 (BUY would have been better)
                if record.action == "BUY":
                    record.label = 1 if pnl_pct > 0 else 0
                else:
                    record.label = 0 if pnl_pct > 0 else 1
                db.commit()
                self._stats["labelled_records"] += 1
                self._trades_since_train += 1

                retrain_interval = settings.get("ai", "ml", "retrain_interval", default=50)
                if self._trades_since_train >= retrain_interval:
                    # Do NOT call self.train() here — it blocks the async event loop.
                    # Signal run_cycle() to schedule training off-thread instead.
                    self._pending_train = True
        finally:
            db.close()

    # ── feature extraction ───────────────────────────────────────
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

    # ── training ─────────────────────────────────────────────────
    def train(self) -> bool:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import cross_val_score
        from sklearn.metrics import accuracy_score

        min_samples = settings.get("ai", "ml", "min_training_samples", default=30)
        db = SessionLocal()
        try:
            # Load ALL labelled records, ordered by time (oldest first)
            records = (
                db.query(TrainingRecord)
                .filter(TrainingRecord.label.isnot(None))
                .order_by(TrainingRecord.recorded_at.asc())
                .all()
            )
        finally:
            db.close()

        if len(records) < min_samples:
            logger.info(f"Not enough training data: {len(records)}/{min_samples}")
            return False

        X_all, y_all = [], []
        for r in records:
            if r.features and r.label is not None:
                X_all.append(self._extract_features(r.features))
                y_all.append(r.label)

        if len(X_all) < min_samples:
            return False

        X_all = np.array(X_all)
        y_all = np.array(y_all)

        # Time-based train/val split — keep newest samples for validation
        split_idx = max(min_samples, int(len(X_all) * (1 - VAL_SPLIT)))
        X_train, y_train = X_all[:split_idx], y_all[:split_idx]
        X_val,   y_val   = X_all[split_idx:], y_all[split_idx:]

        # Cross-val on train split only
        cv_folds = min(5, max(2, len(X_train) // 10))
        model = RandomForestClassifier(n_estimators=100, max_depth=6, random_state=42, n_jobs=-1)
        cv_scores = cross_val_score(model, X_train, y_train, cv=cv_folds, scoring="accuracy")
        cv_accuracy = float(cv_scores.mean())

        # Fit on full train split
        model.fit(X_train, y_train)

        # Validation accuracy (honest hold-out)
        val_accuracy = float(accuracy_score(y_val, model.predict(X_val))) if len(X_val) >= 10 else cv_accuracy

        # Feature importances
        feature_importances = dict(zip(FEATURE_KEYS, model.feature_importances_.tolist()))

        # Keep-best: only replace active model if val_accuracy is not significantly worse
        best_val = self._stats.get("best_val_accuracy") or 0.0
        kept = val_accuracy >= best_val * (1 - KEEP_BEST_TOLERANCE)

        next_version = self._stats["model_version"] + 1
        notes = None
        if not kept:
            notes = f"Rejected: val={val_accuracy:.3f} < best={best_val:.3f}×{1-KEEP_BEST_TOLERANCE:.2f}"
            logger.info(f"Model v{next_version} rejected (val={val_accuracy:.3f} < threshold {best_val*(1-KEEP_BEST_TOLERANCE):.3f})")
        else:
            self._model = model
            self._save_model()
            if val_accuracy > best_val:
                self._stats["best_val_accuracy"] = val_accuracy
            logger.info(
                f"Model v{next_version} saved — cv={cv_accuracy:.3f} val={val_accuracy:.3f} "
                f"train={len(X_train)} val_n={len(X_val)}"
            )

        self._trades_since_train = 0
        self._stats.update({
            "last_trained": datetime.utcnow().isoformat(),
            "accuracy": round(cv_accuracy, 3),
            "val_accuracy": round(val_accuracy, 3),
            "training_trades": len(X_all),
            "model_version": next_version,
            "feature_importances": feature_importances,
        })

        # Persist version record
        self._save_version_record(
            version=next_version,
            cv_accuracy=cv_accuracy,
            val_accuracy=val_accuracy,
            training_samples=len(X_train),
            val_samples=len(X_val),
            feature_importances=feature_importances,
            kept=kept,
            notes=notes,
        )

        return kept

    def _save_version_record(
        self,
        version: int,
        cv_accuracy: float,
        val_accuracy: float,
        training_samples: int,
        val_samples: int,
        feature_importances: dict,
        kept: bool,
        notes: Optional[str],
    ):
        db = SessionLocal()
        try:
            # Deactivate previous active versions
            if kept:
                db.query(ModelVersion).filter(ModelVersion.is_active == True).update({"is_active": False})
            record = ModelVersion(
                version=version,
                cv_accuracy=round(cv_accuracy, 4),
                val_accuracy=round(val_accuracy, 4),
                training_samples=training_samples,
                val_samples=val_samples,
                feature_importances=feature_importances,
                is_active=kept,
                kept=kept,
                notes=notes,
            )
            db.add(record)
            db.commit()
        except Exception as e:
            logger.warning(f"Could not save model version record: {e}")
        finally:
            db.close()

    # ── prediction ───────────────────────────────────────────────
    def predict(self, features: Dict) -> Optional[TradingSignal]:
        if self._model is None:
            return None
        try:
            feat_vec = np.array([self._extract_features(features)])
            pred = self._model.predict(feat_vec)[0]
            proba = self._model.predict_proba(feat_vec)[0]
            confidence = float(max(proba))
            action = "BUY" if pred == 1 else "SELL"
            v = self._stats.get("model_version", 0)
            return TradingSignal(
                action=action,
                confidence=confidence,
                strategy="ml",
                reasoning=(
                    f"ML v{v}: {confidence:.0%} confidence "
                    f"(trained on {self._stats['training_trades']} samples, "
                    f"val_acc={self._stats.get('val_accuracy') or '—'})"
                ),
                stop_loss_pct=0.03,
                take_profit_pct=0.06,
            )
        except Exception as e:
            logger.warning(f"ML prediction failed: {e}")
            return None

    # ── stats ────────────────────────────────────────────────────
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
        self._stats["model_ready"] = self._model is not None
        return dict(self._stats)

    def model_history(self, limit: int = 30) -> List[dict]:
        """Return recent model version history for the dashboard."""
        db = SessionLocal()
        try:
            rows = (
                db.query(ModelVersion)
                .order_by(ModelVersion.version.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "version": r.version,
                    "cv_accuracy": r.cv_accuracy,
                    "val_accuracy": r.val_accuracy,
                    "training_samples": r.training_samples,
                    "val_samples": r.val_samples,
                    "feature_importances": r.feature_importances,
                    "is_active": r.is_active,
                    "kept": r.kept,
                    "notes": r.notes,
                    "saved_at": r.saved_at.isoformat() if r.saved_at else None,
                }
                for r in rows
            ]
        finally:
            db.close()
