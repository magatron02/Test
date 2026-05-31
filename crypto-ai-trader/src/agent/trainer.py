import logging
import pickle
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from .strategy_manager import TradingSignal
from ..core.config import settings
from ..core.database import SessionLocal, TrainingRecord

logger = logging.getLogger(__name__)

FEATURE_KEYS = [
    "rsi", "macd_hist", "bb_position", "atr_pct",
    "volume_ratio", "price_vs_vwap", "change_24h",
    "ema_9_vs_21",  # computed
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
        }
        self._trades_since_train = 0
        self._load_model()

    def _load_model(self):
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
        })

        logger.info(f"Model trained on {len(records)} samples, accuracy={accuracy:.3f}")
        return True

    def predict(self, features: Dict) -> Optional[TradingSignal]:
        if self._model is None:
            return None
        try:
            feat_vec = np.array([self._extract_features(features)])
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
