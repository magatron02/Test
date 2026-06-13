"""Granger causality tests — identify features that statistically predict returns.

Inspired by VincentGurgul/crypto-price-forecasting-public (Ch.4 Granger causality).

For each feature in GBM_FEATURE_KEYS we test the null hypothesis:
  "past values of this feature do NOT help predict future price returns"
  beyond what past returns alone explain (F-test, statsmodels).

Features that reject H0 (p < alpha) are statistically useful predictors.
"""
import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

_MAX_SAMPLES = 800
_DEFAULT_ALPHA = 0.05
_DEFAULT_MAX_LAG = 3


def run_granger_tests(
    records: list,
    feature_keys: list,
    max_lag: int = _DEFAULT_MAX_LAG,
    alpha: float = _DEFAULT_ALPHA,
) -> list:
    """Test each feature for Granger-causal relationship with price returns.

    ``records`` — list of dicts with feature values + ``outcome`` (signed pnl%).
    Returns list of result dicts sorted ascending by p-value.
    """
    try:
        from statsmodels.tsa.stattools import grangercausalitytests
    except ImportError:
        logger.warning("granger_analyzer: statsmodels not installed — pip install statsmodels")
        return []

    if len(records) < max_lag + 10:
        return []

    outcomes = np.array([float(r.get("outcome", 0.0) or 0.0) for r in records])
    outcomes = np.clip(outcomes, -20.0, 20.0)

    results = []
    for key in feature_keys:
        series = np.array([float(r.get(key, 0.0) or 0.0) for r in records])

        if np.std(series) < 1e-9:
            results.append(_null_result(key, max_lag))
            continue

        try:
            data = np.column_stack([outcomes, series])
            gc = grangercausalitytests(data, maxlag=max_lag, verbose=False)

            best_p, best_lag = 1.0, max_lag
            for lag, tests in gc.items():
                p = tests[0][0][1]  # ssr F-test p-value
                if p < best_p:
                    best_p, best_lag = p, lag

            # Pearson correlation for direction label
            corr = float(np.corrcoef(series[max_lag:], outcomes[max_lag:])[0, 1])
            direction = "bullish" if corr > 0.05 else "bearish" if corr < -0.05 else "neutral"

            results.append({
                "feature": key,
                "p_value": round(float(best_p), 4),
                "significant": bool(best_p < alpha),
                "lag": best_lag,
                "direction": direction,
                "correlation": round(corr, 3),
            })
        except Exception as exc:
            logger.debug("Granger test failed for %s: %s", key, exc)
            results.append(_null_result(key, max_lag))

    results.sort(key=lambda d: d["p_value"])
    return results


def _null_result(feature: str, max_lag: int) -> dict:
    return {
        "feature": feature, "p_value": 1.0, "significant": False,
        "lag": max_lag, "direction": "neutral", "correlation": 0.0,
    }


def load_records_for_symbol(symbol: Optional[str] = None, limit: int = _MAX_SAMPLES) -> list:
    """Load labelled training records from DB, returned in chronological order."""
    try:
        from ..core.database import SessionLocal, TrainingRecord
        db = SessionLocal()
        try:
            q = db.query(TrainingRecord).filter(TrainingRecord.label.isnot(None))
            if symbol:
                q = q.filter(TrainingRecord.symbol == symbol)
            rows = q.order_by(TrainingRecord.recorded_at.desc()).limit(limit).all()
            result = []
            for r in reversed(rows):
                if r.features:
                    d = dict(r.features)
                    d["outcome"] = float(r.outcome or 0.0)
                    result.append(d)
            return result
        finally:
            db.close()
    except Exception as exc:
        logger.warning("granger_analyzer: DB load failed — %s", exc)
        return []
