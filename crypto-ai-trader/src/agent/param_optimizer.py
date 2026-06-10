"""
F5.1 / F2.4 Walk-forward parameter optimisation.

Uses Optuna TPE sampler when available (pip install optuna) for efficient
hyperparameter search over a larger space. Falls back to exhaustive grid
search when Optuna is not installed.

Optuna advantages over grid:
- TPE (Tree-structured Parzen Estimator) focuses trials on promising regions
- Handles continuous ranges (not just discrete grid points)
- Pruning: stop bad trials early
- Typically 3–5× fewer trials needed to find the same optimum
"""
from __future__ import annotations

import itertools
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..core.config import settings

logger = logging.getLogger(__name__)

try:
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    _OPTUNA_AVAILABLE = True
except ImportError:
    optuna = None  # type: ignore
    _OPTUNA_AVAILABLE = False

# ── Default parameter search space ───────────────────────────────────────────

DEFAULT_GRID: Dict[str, List[Any]] = {
    # RSI thresholds
    "rsi_oversold":       [25, 30, 35],
    "rsi_overbought":     [65, 70, 75],
    # ATR SL multiplier (exit_manager regime defaults act as baseline)
    "atr_sl_mult":        [1.5, 2.0, 2.5],
    # Signal confidence gate
    "min_confidence":     [0.50, 0.55, 0.60, 0.65, 0.70],
}

# Optuna search ranges (continuous — richer than the discrete grid)
OPTUNA_RANGES: Dict[str, tuple] = {
    "rsi_oversold":   (20.0, 40.0),
    "rsi_overbought": (60.0, 80.0),
    "atr_sl_mult":    (1.0,  3.5),
    "min_confidence": (0.45, 0.75),
}

_BEST_PARAMS_FILE = "best_params.json"


# ── Objective function ────────────────────────────────────────────────────────

def _sharpe(returns: np.ndarray, annual_factor: float = 252.0) -> float:
    """Annualised Sharpe (returns treated as daily fractions)."""
    if len(returns) < 5:
        return -999.0
    std = float(np.std(returns, ddof=1))
    if std == 0:
        return 0.0
    return float(np.mean(returns) / std * np.sqrt(annual_factor))


def _simulate_returns(
    ohlcv: List[Dict[str, float]],
    rsi_oversold: float,
    rsi_overbought: float,
    atr_sl_mult: float,
    min_confidence: float,
    max_hold: int = 20,
) -> np.ndarray:
    """
    Lightweight price-driven simulation; returns per-trade P&L fractions.

    Each bar dict should have: close, rsi, atr_pct, signal_confidence
    (``label`` is accepted but optional / unused — entries are derived from
    RSI + confidence, not look-ahead labels, so this stays leak-free).

    Trade lifecycle
    ---------------
    * Enter long when flat and ``rsi <= rsi_oversold`` and
      ``signal_confidence >= min_confidence``.
    * Exit on the first of:
        - stop-loss   : unrealised P&L <= -(atr_pct × atr_sl_mult)
        - take-profit : ``rsi >= rsi_overbought`` (momentum exhausted)
        - time-stop   : held for ``max_hold`` bars
    * Any position still open on the last bar is marked-to-market and closed.

    The goal is *relative* ranking of param combos, not tick-accurate P&L —
    every grid dimension (oversold, overbought, atr_sl_mult, min_confidence)
    now measurably affects the outcome.
    """
    returns: List[float] = []
    in_trade = False
    entry_price = 0.0
    sl_pct = 0.0
    bars_held = 0

    for bar in ohlcv:
        close = float(bar.get("close", 1.0))
        rsi   = float(bar.get("rsi", 50.0))
        atr   = float(bar.get("atr_pct", 0.01))
        conf  = float(bar.get("signal_confidence", 1.0))

        if in_trade:
            bars_held += 1
            pnl = (close - entry_price) / entry_price if entry_price else 0.0
            if pnl <= -sl_pct:                       # stop-loss
                returns.append(-sl_pct)
                in_trade = False
            elif rsi >= rsi_overbought:              # take-profit
                returns.append(pnl)
                in_trade = False
            elif bars_held >= max_hold:              # time-stop
                returns.append(pnl)
                in_trade = False
        else:
            if rsi <= rsi_oversold and conf >= min_confidence:
                entry_price = close
                sl_pct = max(atr * atr_sl_mult, 1e-4)
                bars_held = 0
                in_trade = True

    # Mark-to-market any still-open position on the final bar
    if in_trade and ohlcv:
        last_close = float(ohlcv[-1].get("close", entry_price))
        returns.append((last_close - entry_price) / entry_price if entry_price else 0.0)

    return np.array(returns) if returns else np.zeros(1)


# ── Walk-forward split ────────────────────────────────────────────────────────

def walk_forward_splits(
    data: List[Dict[str, float]],
    train_frac: float = 0.70,   # retained for API compatibility
    n_splits: int = 3,
    min_chunk: int = 5,
) -> List[Tuple[List, List]]:
    """
    Expanding-window walk-forward split.

    Divides `data` into ``n_splits + 1`` equal contiguous chunks; for split *i*
    the model trains on chunks ``[0..i)`` and is evaluated out-of-sample on
    chunk *i*. Chunks smaller than ``min_chunk`` bars are dropped so the final
    fold is never a degenerate 1-bar window.
    """
    n = len(data)
    chunk = n // (n_splits + 1)
    if chunk < min_chunk:
        return []
    splits = []
    for i in range(1, n_splits + 1):
        train = data[: chunk * i]
        test  = data[chunk * i: chunk * (i + 1)]
        if len(train) >= min_chunk and len(test) >= min_chunk:
            splits.append((train, test))
    return splits


# ── Grid search ───────────────────────────────────────────────────────────────

def grid_search(
    data: List[Dict[str, float]],
    grid: Optional[Dict[str, List[Any]]] = None,
    n_splits: int = 3,
) -> Dict[str, Any]:
    """
    Exhaustive grid search on walk-forward windows.

    Returns
    -------
    {
      "best_params": {...},
      "best_sharpe": float,
      "n_combos":    int,
      "optimized_at": ISO timestamp,
    }
    """
    grid = grid or DEFAULT_GRID
    keys   = list(grid.keys())
    values = list(grid.values())

    splits = walk_forward_splits(data, n_splits=n_splits)
    if not splits:
        logger.warning("ParamOptimizer: not enough data for walk-forward splits")
        return {"best_params": {k: v[0] for k, v in grid.items()}, "best_sharpe": 0.0,
                "n_combos": 0, "optimized_at": datetime.utcnow().isoformat()}

    best_sharpe = -999.0
    best_combo: Tuple = tuple(v[0] for v in values)

    combos = list(itertools.product(*values))
    for combo in combos:
        params = dict(zip(keys, combo))
        oos_sharpes = []
        for train, test in splits:
            _ = train  # train slice could be used for signal generation; kept for extensibility
            rets = _simulate_returns(
                test,
                rsi_oversold   = params.get("rsi_oversold",   30),
                rsi_overbought = params.get("rsi_overbought",  70),
                atr_sl_mult    = params.get("atr_sl_mult",    2.0),
                min_confidence = params.get("min_confidence", 0.55),
            )
            oos_sharpes.append(_sharpe(rets))
        avg_sharpe = float(np.mean(oos_sharpes))
        if avg_sharpe > best_sharpe:
            best_sharpe = avg_sharpe
            best_combo  = combo

    best_params = dict(zip(keys, best_combo))
    return {
        "best_params":    best_params,
        "best_sharpe":    round(best_sharpe, 4),
        "n_combos":       len(combos),
        "optimized_at":   datetime.utcnow().isoformat(),
    }


# ── Optuna search ────────────────────────────────────────────────────────────

def optuna_search(
    data: List[Dict[str, float]],
    ranges: Optional[Dict[str, tuple]] = None,
    n_trials: int = 80,
    n_splits: int = 3,
) -> Dict[str, Any]:
    """
    Bayesian hyperparameter search via Optuna TPE sampler.

    Falls back to grid_search if Optuna is not installed.
    Roughly 3–5× more efficient than exhaustive grid over the same space.

    Parameters
    ----------
    data : list of bar dicts with close, rsi, atr_pct, signal_confidence
    ranges : {param_name: (low, high)} — defaults to OPTUNA_RANGES
    n_trials : number of Optuna trials (80 = fast but thorough)
    n_splits : walk-forward folds
    """
    if not _OPTUNA_AVAILABLE:
        logger.info("ParamOptimizer: Optuna not installed — using grid search")
        return grid_search(data, n_splits=n_splits)

    ranges = ranges or OPTUNA_RANGES
    splits = walk_forward_splits(data, n_splits=n_splits)
    if not splits:
        logger.warning("ParamOptimizer: not enough data for Optuna splits")
        return {"best_params": {k: (lo + hi) / 2 for k, (lo, hi) in ranges.items()},
                "best_sharpe": 0.0, "n_combos": 0,
                "optimized_at": datetime.utcnow().isoformat()}

    def objective(trial: "optuna.Trial") -> float:
        params = {
            k: trial.suggest_float(k, lo, hi)
            for k, (lo, hi) in ranges.items()
        }
        oos_sharpes = []
        for _, test in splits:
            rets = _simulate_returns(
                test,
                rsi_oversold   = params["rsi_oversold"],
                rsi_overbought = params["rsi_overbought"],
                atr_sl_mult    = params["atr_sl_mult"],
                min_confidence = params["min_confidence"],
            )
            oos_sharpes.append(_sharpe(rets))
        return float(np.mean(oos_sharpes))

    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=42),
    )
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

    best = study.best_params
    return {
        "best_params":    best,
        "best_sharpe":    round(study.best_value, 4),
        "n_combos":       n_trials,
        "optimized_at":   datetime.utcnow().isoformat(),
        "method":         "optuna_tpe",
    }


# ── Persistence ───────────────────────────────────────────────────────────────

def save_best_params(result: Dict[str, Any], models_dir: Optional[Path] = None) -> Path:
    """Persist optimisation result to <models_dir>/best_params.json."""
    dest = (models_dir or settings.models_dir) / _BEST_PARAMS_FILE
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w") as fh:
        json.dump(result, fh, indent=2)
    logger.info("ParamOptimizer: saved best params → %s", dest)
    return dest


def load_best_params(models_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Load previously optimised params; returns None if file absent."""
    src = (models_dir or settings.models_dir) / _BEST_PARAMS_FILE
    if not src.exists():
        return None
    try:
        with open(src) as fh:
            data = json.load(fh)
        logger.info("ParamOptimizer: loaded best params from %s", src)
        return data
    except Exception as exc:
        logger.warning("ParamOptimizer: could not load %s — %s", src, exc)
        return None


# ── High-level runner ─────────────────────────────────────────────────────────

class ParamOptimizer:
    """
    Thin stateful wrapper used by AITrainer / hourly_trainer.
    Call `run(data)` to optimise; call `best_params` to retrieve.
    """

    def __init__(
        self,
        grid:       Optional[Dict[str, List[Any]]] = None,
        n_splits:   int = 3,
        models_dir: Optional[Path] = None,
    ):
        self._grid       = grid or DEFAULT_GRID
        self._n_splits   = n_splits
        self._models_dir = models_dir or settings.models_dir
        self._result:    Optional[Dict[str, Any]] = load_best_params(self._models_dir)

    def run(self, data: List[Dict[str, float]]) -> Dict[str, Any]:
        """
        Run optimisation with champion/challenger gating.

        The *challenger* (new run) must improve on the *champion* (current saved
        result) by at least ``_MIN_IMPROVEMENT`` Sharpe points before the new
        params replace the old ones.  The existing champion is always returned
        when the challenger cannot beat it; the new result is still accessible
        via ``_last_challenger`` for diagnostics.
        """
        if _OPTUNA_AVAILABLE:
            logger.info("ParamOptimizer: starting Optuna search (%d bars)", len(data))
            challenger = optuna_search(data, n_splits=self._n_splits)
        else:
            logger.info("ParamOptimizer: starting grid search (%d bars)", len(data))
            challenger = grid_search(data, grid=self._grid, n_splits=self._n_splits)
        self._last_challenger = challenger

        champion_sharpe = (self._result or {}).get("best_sharpe", -999.0)
        challenger_sharpe = challenger.get("best_sharpe", -999.0)

        if challenger_sharpe > champion_sharpe + self._MIN_IMPROVEMENT:
            self._result = challenger
            save_best_params(self._result, self._models_dir)
            logger.info(
                "ParamOptimizer: challenger promoted → champion "
                "(Sharpe %.3f → %.3f) params=%s",
                champion_sharpe, challenger_sharpe, challenger["best_params"],
            )
        else:
            logger.info(
                "ParamOptimizer: challenger (Sharpe %.3f) did not beat champion "
                "(Sharpe %.3f) — keeping current params",
                challenger_sharpe, champion_sharpe,
            )
        return self._result or challenger

    # Minimum Sharpe improvement required to promote challenger → champion.
    # Small positive value avoids churn on noise while still allowing updates.
    _MIN_IMPROVEMENT: float = 0.05

    @property
    def best_params(self) -> Optional[Dict[str, Any]]:
        """Returns best_params sub-dict, or None if not yet optimised."""
        if self._result and "best_params" in self._result:
            return self._result["best_params"]
        return None

    def summary(self) -> dict:
        if not self._result:
            return {"status": "not_run"}
        challenger = getattr(self, "_last_challenger", None)
        return {
            "best_sharpe":        self._result.get("best_sharpe"),
            "n_combos":           self._result.get("n_combos"),
            "optimized_at":       self._result.get("optimized_at"),
            "best_params":        self._result.get("best_params"),
            "last_challenger_sharpe": challenger.get("best_sharpe") if challenger else None,
        }
