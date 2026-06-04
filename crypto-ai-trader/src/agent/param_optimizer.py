"""
F5.1 Walk-forward parameter optimisation.

Grid-searches over key strategy parameters on rolling walk-forward windows,
stores the best params as JSON, and exposes a loader for AITrader / AITrainer.

No Optuna required — pure scipy / numpy grid search.
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

# ── Default parameter search space ───────────────────────────────────────────

DEFAULT_GRID: Dict[str, List[Any]] = {
    # RSI thresholds
    "rsi_oversold":       [25, 30, 35],
    "rsi_overbought":     [65, 70, 75],
    # ATR SL multiplier (exit_manager regime defaults act as baseline)
    "atr_sl_mult":        [1.5, 2.0, 2.5],
    # Signal confidence gate
    "min_confidence":     [0.50, 0.55, 0.60],
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
) -> np.ndarray:
    """
    Simplified simulation on a bar sequence; returns daily P&L fractions.

    Each bar dict must have: close, rsi, atr_pct, signal_confidence, label
    where label ∈ {1=BUY, -1=SELL, 0=HOLD}.

    This is intentionally lightweight — the goal is relative ranking of
    param combos, not tick-level accuracy.
    """
    equity = 1.0
    returns = []
    in_trade = False
    entry_price = 0.0
    sl_pct = 0.0

    for bar in ohlcv:
        close = float(bar.get("close", 1.0))
        rsi   = float(bar.get("rsi", 50.0))
        atr   = float(bar.get("atr_pct", 0.01))
        conf  = float(bar.get("signal_confidence", 0.0))
        label = int(bar.get("label", 0))

        if in_trade:
            pnl = (close - entry_price) / entry_price
            # Stop-loss check
            if pnl <= -sl_pct:
                returns.append(-sl_pct)
                equity *= 1 - sl_pct
                in_trade = False
                continue
            # Take-profit / exit signal
            if label == -1:
                returns.append(pnl)
                equity *= 1 + pnl
                in_trade = False
        else:
            buy_signal = (
                label == 1
                and conf >= min_confidence
                and rsi <= rsi_oversold
            )
            if buy_signal:
                entry_price = close
                sl_pct = atr * atr_sl_mult
                in_trade = True

    return np.array(returns) if returns else np.zeros(1)


# ── Walk-forward split ────────────────────────────────────────────────────────

def walk_forward_splits(
    data: List[Dict[str, float]],
    train_frac: float = 0.70,
    n_splits: int = 3,
) -> List[Tuple[List, List]]:
    """
    Returns n_splits (train, test) slices over `data` using expanding train window.
    """
    n = len(data)
    splits = []
    step = n // (n_splits + 1)
    for i in range(1, n_splits + 1):
        train_end = step * (i + 1) if i < n_splits else int(n * train_frac) + step * i
        train_end = min(train_end, n - 1)
        test_end  = min(train_end + step, n)
        if test_end > train_end:
            splits.append((data[:train_end], data[train_end:test_end]))
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
        """Run optimisation and persist result. Returns the result dict."""
        logger.info("ParamOptimizer: starting grid search (%d bars)", len(data))
        self._result = grid_search(data, grid=self._grid, n_splits=self._n_splits)
        save_best_params(self._result, self._models_dir)
        logger.info(
            "ParamOptimizer: best Sharpe=%.3f params=%s",
            self._result["best_sharpe"], self._result["best_params"],
        )
        return self._result

    @property
    def best_params(self) -> Optional[Dict[str, Any]]:
        """Returns best_params sub-dict, or None if not yet optimised."""
        if self._result and "best_params" in self._result:
            return self._result["best_params"]
        return None

    def summary(self) -> dict:
        if not self._result:
            return {"status": "not_run"}
        return {
            "best_sharpe":  self._result.get("best_sharpe"),
            "n_combos":     self._result.get("n_combos"),
            "optimized_at": self._result.get("optimized_at"),
            "best_params":  self._result.get("best_params"),
        }
