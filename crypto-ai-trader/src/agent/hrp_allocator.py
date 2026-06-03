"""Hierarchical Risk Parity (HRP) portfolio allocation.

Implements Marcos López de Prado's HRP algorithm ("Machine Learning for
Trading", Ch. 13). HRP allocates capital across correlated assets so that
clusters of correlated assets do not get double-weighted. The algorithm has
three stages: (1) hierarchical clustering of the correlation-distance matrix,
(2) quasi-diagonalisation of the linkage tree, and (3) recursive bisection
allocating inverse-variance weights down the tree.
"""

import logging
from typing import Dict, List

import numpy as np
from scipy.cluster.hierarchy import linkage
from scipy.spatial.distance import squareform

logger = logging.getLogger(__name__)


def _corr_distance(corr: np.ndarray) -> np.ndarray:
    """Convert a correlation matrix to the standard HRP distance metric.

    distance = sqrt(0.5 * (1 - corr)), bounded in [0, 1].
    """
    dist = np.sqrt(np.clip(0.5 * (1.0 - corr), 0.0, 1.0))
    np.fill_diagonal(dist, 0.0)
    return 0.5 * (dist + dist.T)


def _get_quasi_diag(link) -> List[int]:
    """Return the leaf order from a scipy linkage matrix.

    Recursively unpacks merged clusters until only original leaves remain,
    producing an ordering that places similar assets adjacent to each other.
    """
    link = link.astype(int)
    num_items = link[-1, 3]
    sort_ix = [link[-1, 0], link[-1, 1]]

    while max(sort_ix) >= num_items:
        new_order: List[int] = []
        for item in sort_ix:
            if item < num_items:
                new_order.append(item)
            else:
                row = item - num_items
                new_order.append(link[row, 0])
                new_order.append(link[row, 1])
        sort_ix = new_order

    return [int(i) for i in sort_ix]


def _get_cluster_var(cov: np.ndarray, items: List[int]) -> float:
    """Inverse-variance portfolio variance for a sub-cluster."""
    sub = cov[np.ix_(items, items)]
    ivp = 1.0 / np.diag(sub)
    ivp /= ivp.sum()
    return float(ivp @ sub @ ivp)


def _recursive_bisection(cov: np.ndarray, sort_ix: List[int]) -> np.ndarray:
    """Allocate weights via recursive bisection (López de Prado)."""
    n = cov.shape[0]
    weights = np.ones(n)
    clusters = [list(sort_ix)]

    while clusters:
        new_clusters: List[List[int]] = []
        for cluster in clusters:
            if len(cluster) <= 1:
                continue
            mid = len(cluster) // 2
            left = cluster[:mid]
            right = cluster[mid:]
            var_left = _get_cluster_var(cov, left)
            var_right = _get_cluster_var(cov, right)
            alpha = 1.0 - var_left / (var_left + var_right)
            for i in left:
                weights[i] *= alpha
            for i in right:
                weights[i] *= 1.0 - alpha
            new_clusters.append(left)
            new_clusters.append(right)
        clusters = new_clusters

    return weights


def hrp_weights(returns: np.ndarray, symbols: List[str]) -> Dict[str, float]:
    """Compute HRP weights from a (T x N) matrix of asset returns.

    returns: 2D array, rows=time, cols=assets (aligned with `symbols`).
    Returns {symbol: weight} summing to 1.0, rounded to 4 dp. On any
    degenerate input, invalid covariance, or error, falls back to equal
    weighting. Never raises.
    """
    n = len(symbols)
    equal = {s: round(1.0 / n, 4) for s in symbols} if n else {}

    try:
        returns = np.asarray(returns, dtype=float)
        if returns.ndim != 2 or returns.shape[1] < 2 or returns.shape[0] < 20:
            return equal
        if returns.shape[1] != n:
            return equal
        if not np.all(np.isfinite(returns)):
            return equal

        cov = np.cov(returns, rowvar=False)
        corr = np.corrcoef(returns, rowvar=False)
        if not np.all(np.isfinite(cov)) or not np.all(np.isfinite(corr)):
            return equal
        if np.any(np.diag(cov) <= 0):
            return equal

        dist = _corr_distance(corr)
        if not np.all(np.isfinite(dist)):
            return equal

        link = linkage(squareform(dist, checks=False), method="single")
        sort_ix = _get_quasi_diag(link)
        if sorted(sort_ix) != list(range(n)):
            return equal

        raw = _recursive_bisection(cov, sort_ix)
        total = raw.sum()
        if not np.isfinite(total) or total <= 0:
            return equal

        raw /= total
        return {symbols[i]: round(float(raw[i]), 4) for i in range(n)}
    except Exception as exc:  # noqa: BLE001
        logger.warning("HRP weighting failed, using equal weights: %s", exc)
        return equal


def allocate_capital(
    total_capital: float,
    returns_by_symbol: Dict[str, List[float]],
    max_weight: float = 0.40,
) -> Dict[str, dict]:
    """Allocate capital across symbols using HRP with a per-asset cap.

    Takes per-symbol return series, aligns them to the shortest length
    (truncating from the front), computes HRP weights, applies `max_weight`
    cap, renormalises so weights sum to 1.0, and splits `total_capital`
    accordingly. Symbols with fewer than 20 aligned points fall back to
    equal weighting overall.

    Returns {symbol: {"weight": float, "capital": float}}.
    """
    symbols = list(returns_by_symbol.keys())
    n = len(symbols)
    if n == 0:
        return {}

    def _equal() -> Dict[str, dict]:
        w = round(1.0 / n, 4)
        return {s: {"weight": w, "capital": round(total_capital * w, 4)} for s in symbols}

    try:
        lengths = [len(returns_by_symbol[s]) for s in symbols]
        min_len = min(lengths)
        if min_len < 20:
            return _equal()

        aligned = np.column_stack(
            [np.asarray(returns_by_symbol[s], dtype=float)[-min_len:] for s in symbols]
        )

        weights = hrp_weights(aligned, symbols)
        w = np.array([weights[s] for s in symbols], dtype=float)

        w = np.minimum(w, max_weight)
        total = w.sum()
        if not np.isfinite(total) or total <= 0:
            return _equal()
        w /= total

        return {
            symbols[i]: {
                "weight": round(float(w[i]), 4),
                "capital": round(float(total_capital * w[i]), 4),
            }
            for i in range(n)
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("allocate_capital failed, using equal weights: %s", exc)
        return _equal()
