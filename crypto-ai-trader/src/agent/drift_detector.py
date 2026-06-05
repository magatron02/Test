"""
F3.4 Model-drift detection via Population Stability Index (PSI).

PSI = Σ (actual_pct - expected_pct) × ln(actual_pct / expected_pct)
  < 0.10 → stable
  0.10 – 0.20 → minor drift (monitor)
  > 0.20 → significant drift (retrain)

Pure-function core; DriftDetector class wraps state (baseline).
"""
from __future__ import annotations

import logging
import math
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)

_DRIFT_THRESHOLD = 0.20   # PSI above this triggers retrain
_WARN_THRESHOLD  = 0.10   # PSI above this logs a warning
_MIN_EPSILON     = 1e-6   # avoids log(0)


def psi(
    expected: Sequence[float],
    actual: Sequence[float],
    buckets: int = 10,
) -> float:
    """
    PSI between two 1-D distributions.

    Parameters
    ----------
    expected : baseline / training distribution values
    actual   : current / production distribution values
    buckets  : number of equal-width histogram bins

    Returns
    -------
    PSI score (float ≥ 0).  Higher = more drift.
    """
    if len(expected) < 5 or len(actual) < 5:
        return 0.0

    exp_arr = np.array(expected, dtype=float)
    act_arr = np.array(actual, dtype=float)

    # Use training-set percentiles as bin edges so both arrays share bins
    edges = np.percentile(exp_arr, np.linspace(0, 100, buckets + 1))
    # Force unique edges to avoid zero-width bins
    edges = np.unique(edges)
    if len(edges) < 2:
        return 0.0

    exp_counts, _ = np.histogram(exp_arr, bins=edges)
    act_counts, _ = np.histogram(act_arr, bins=edges)

    exp_pct = exp_counts / (exp_counts.sum() + _MIN_EPSILON)
    act_pct = act_counts / (act_counts.sum() + _MIN_EPSILON)

    # Clip to avoid log(0)
    exp_pct = np.clip(exp_pct, _MIN_EPSILON, None)
    act_pct = np.clip(act_pct, _MIN_EPSILON, None)

    psi_val = float(np.sum((act_pct - exp_pct) * np.log(act_pct / exp_pct)))
    return max(0.0, psi_val)


def detect_feature_drift(
    baseline_stats: Dict[str, List[float]],
    current_stats:  Dict[str, List[float]],
    threshold: float = _DRIFT_THRESHOLD,
    buckets: int = 10,
) -> Tuple[bool, Dict[str, float]]:
    """
    Compare feature distributions via PSI.

    Parameters
    ----------
    baseline_stats : {feature_name: [values...]} from training time
    current_stats  : {feature_name: [values...]} from recent predictions
    threshold      : PSI above this triggers drift flag

    Returns
    -------
    (drift_detected: bool, per_feature_psi: dict)
    """
    scores: Dict[str, float] = {}
    for feat, base_vals in baseline_stats.items():
        curr_vals = current_stats.get(feat, [])
        if len(curr_vals) >= 5:
            scores[feat] = psi(base_vals, curr_vals, buckets=buckets)
        else:
            scores[feat] = 0.0

    drift = any(v > threshold for v in scores.values())
    return drift, scores


class DriftDetector:
    """
    Stateful wrapper: record baseline stats after training,
    then call check() before each prediction batch.
    """

    def __init__(self, threshold: float = _DRIFT_THRESHOLD, buckets: int = 10):
        self._threshold = threshold
        self._buckets   = buckets
        self._baseline:  Optional[Dict[str, List[float]]] = None
        self._last_psi:  Dict[str, float] = {}
        self._drift_count = 0

    # ── Baseline management ───────────────────────────────────────────────

    def record_baseline(self, feature_values: Dict[str, List[float]]):
        """Call once after training completes."""
        self._baseline = {k: list(v) for k, v in feature_values.items()}
        self._last_psi = {}
        logger.info("Drift detector: baseline recorded (%d features)", len(self._baseline))

    def has_baseline(self) -> bool:
        return self._baseline is not None

    # ── Drift check ───────────────────────────────────────────────────────

    def check(
        self, current_values: Dict[str, List[float]]
    ) -> Tuple[bool, Dict[str, float]]:
        """
        Returns (drift_detected, per_feature_psi).
        Logs warning / critical as appropriate.
        """
        if not self._baseline:
            return False, {}

        drift, scores = detect_feature_drift(
            self._baseline, current_values,
            threshold=self._threshold,
            buckets=self._buckets,
        )
        self._last_psi = scores

        if drift:
            self._drift_count += 1
            drifted = [f for f, v in scores.items() if v > self._threshold]
            logger.warning(
                "Model drift detected (PSI threshold=%.2f): features=%s, psi=%s",
                self._threshold, drifted,
                {f: round(v, 3) for f, v in scores.items() if v > _WARN_THRESHOLD},
            )
        elif any(v > _WARN_THRESHOLD for v in scores.values()):
            logger.info(
                "Minor feature drift (PSI 0.10-0.20): %s",
                {f: round(v, 3) for f, v in scores.items() if v > _WARN_THRESHOLD},
            )
        return drift, scores

    # ── Reporting ─────────────────────────────────────────────────────────

    @property
    def last_psi(self) -> Dict[str, float]:
        return dict(self._last_psi)

    @property
    def drift_count(self) -> int:
        return self._drift_count

    def summary(self) -> dict:
        max_psi = max(self._last_psi.values(), default=0.0)
        return {
            "drift_count":    self._drift_count,
            "max_psi":        round(max_psi, 4),
            "threshold":      self._threshold,
            "has_baseline":   self.has_baseline(),
            "per_feature":    {k: round(v, 4) for k, v in self._last_psi.items()},
        }
