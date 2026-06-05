"""
F3.3 VaR/CVaR + Monte Carlo tail-risk engine.

Pure-function design — all methods are stateless so tests don't need mocks.
Requires scipy (already in requirements.txt).
"""
from __future__ import annotations

import logging
from typing import Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)


def var_cvar(
    returns: Sequence[float],
    confidence: float = 0.95,
) -> Tuple[float, float]:
    """
    Historical VaR and CVaR at the given confidence level.

    Parameters
    ----------
    returns    : daily return series (e.g. [0.02, -0.01, ...])
    confidence : 0.95 → 95% VaR

    Returns
    -------
    (var, cvar) — both expressed as *positive* loss percentages.
    E.g. (0.03, 0.045) means "95% VaR = 3%, CVaR = 4.5%"
    """
    if len(returns) < 5:
        return 0.0, 0.0

    arr = np.array(returns, dtype=float)
    var = float(-np.percentile(arr, (1 - confidence) * 100))
    tail = arr[arr <= -var]
    cvar = float(-tail.mean()) if len(tail) else var
    return max(var, 0.0), max(cvar, 0.0)


def monte_carlo_maxdd(
    returns: Sequence[float],
    n_paths: int = 1_000,
    horizon: int = 30,
    seed: int | None = 42,
) -> dict:
    """
    Simulate `n_paths` equity paths of length `horizon` days by bootstrap-
    sampling from the historical `returns`, then return tail-risk statistics.

    Returns
    -------
    {
      "mean_maxdd":   float,  # average max-drawdown across paths
      "p95_maxdd":    float,  # 95th-percentile max-drawdown (worst-case)
      "p99_maxdd":    float,
      "prob_ruin":    float,  # fraction of paths where equity fell > 20 %
      "n_paths":      int,
      "horizon":      int,
    }
    """
    if len(returns) < 5:
        return {
            "mean_maxdd": 0.0, "p95_maxdd": 0.0, "p99_maxdd": 0.0,
            "prob_ruin": 0.0, "n_paths": n_paths, "horizon": horizon,
        }

    rng = np.random.default_rng(seed)
    arr = np.array(returns, dtype=float)

    # Bootstrap sample: shape (n_paths, horizon)
    idx = rng.integers(0, len(arr), size=(n_paths, horizon))
    sampled = arr[idx]

    # Cumulative equity starting at 1.0
    equity = np.cumprod(1.0 + sampled, axis=1)

    # Max-drawdown per path: max(1 - eq/cummax)
    cummax = np.maximum.accumulate(equity, axis=1)
    # Prepend 1.0 so drawdown is relative to start
    cummax = np.where(cummax < 1.0, 1.0, cummax)
    dd = 1.0 - equity / cummax
    max_dd = dd.max(axis=1)

    return {
        "mean_maxdd": float(np.mean(max_dd)),
        "p95_maxdd":  float(np.percentile(max_dd, 95)),
        "p99_maxdd":  float(np.percentile(max_dd, 99)),
        "prob_ruin":  float(np.mean(max_dd > 0.20)),
        "n_paths":    n_paths,
        "horizon":    horizon,
    }


def summarize(
    returns: Sequence[float],
    confidence: float = 0.95,
    mc_paths: int = 1_000,
    mc_horizon: int = 30,
) -> dict:
    """Convenience wrapper: returns a flat dict suitable for dashboard injection."""
    var, cvar = var_cvar(returns, confidence)
    mc = monte_carlo_maxdd(returns, n_paths=mc_paths, horizon=mc_horizon)
    return {
        "var_pct":       round(var, 4),
        "cvar_pct":      round(cvar, 4),
        "confidence":    confidence,
        **{k: round(v, 4) if isinstance(v, float) else v for k, v in mc.items()},
    }
