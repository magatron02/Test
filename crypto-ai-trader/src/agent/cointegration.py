"""Cointegration-based pairs-trading signals (statistical arbitrage).

Two crypto assets are often cointegrated: their price spread is mean-reverting.
When the spread deviates far from its mean (high z-score), we expect reversion,
so we short the outperformer and long the underperformer.
"""

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


def hedge_ratio(y: np.ndarray, x: np.ndarray) -> float:
    """OLS hedge ratio (beta) regressing y on x with an intercept."""
    y = np.asarray(y, dtype=float)
    x = np.asarray(x, dtype=float)
    A = np.column_stack([x, np.ones(len(x))])
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    return float(coef[0])


def _half_life(spread: np.ndarray) -> Optional[float]:
    """Ornstein-Uhlenbeck mean-reversion half-life in bars, or None."""
    spread = np.asarray(spread, dtype=float)
    lag = spread[:-1]
    delta = spread[1:] - lag
    A = np.column_stack([lag, np.ones(len(lag))])
    coef, *_ = np.linalg.lstsq(A, delta, rcond=None)
    lam = float(coef[0])
    if lam >= 0:
        return None
    hl = -np.log(2) / lam
    if not np.isfinite(hl) or hl <= 0:
        return None
    return float(hl)


def check_cointegration(price_a: np.ndarray, price_b: np.ndarray) -> dict:
    """Engle-Granger cointegration test on two price series (equal length, >= 50)."""
    try:
        a = np.asarray(price_a, dtype=float)
        b = np.asarray(price_b, dtype=float)
        if len(a) != len(b) or len(a) < 50:
            return {
                "cointegrated": False,
                "p_value": None,
                "t_stat": None,
                "hedge_ratio": None,
                "half_life": None,
            }
        from statsmodels.tsa.stattools import coint

        t_stat, p_value, _ = coint(a, b)
        beta = hedge_ratio(a, b)
        spread = a - beta * b
        hl = _half_life(spread)
        return {
            "cointegrated": bool(p_value < 0.05),
            "p_value": float(p_value),
            "t_stat": float(t_stat),
            "hedge_ratio": float(beta),
            "half_life": hl,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("check_cointegration failed: %s", exc)
        return {
            "cointegrated": False,
            "p_value": None,
            "t_stat": None,
            "hedge_ratio": None,
            "half_life": None,
            "error": str(exc),
        }


def pairs_signal(
    price_a: np.ndarray,
    price_b: np.ndarray,
    entry_z: float = 2.0,
    exit_z: float = 0.5,
) -> dict:
    """Generate a mean-reversion pairs signal from the current spread z-score."""
    try:
        a = np.asarray(price_a, dtype=float)
        b = np.asarray(price_b, dtype=float)
        if len(a) != len(b) or len(a) < 50:
            return {
                "zscore": 0.0,
                "signal": "HOLD",
                "action_a": "HOLD",
                "action_b": "HOLD",
                "hedge_ratio": None,
                "spread": None,
                "confidence": 0.0,
            }
        beta = hedge_ratio(a, b)
        spread = a - beta * b
        std = float(np.std(spread))
        if std == 0 or not np.isfinite(std):
            z = 0.0
        else:
            z = float((spread[-1] - np.mean(spread)) / std)

        if abs(z) <= exit_z:
            signal, action_a, action_b = "CLOSE", "HOLD", "HOLD"
        elif z >= entry_z:
            signal, action_a, action_b = "SHORT_A_LONG_B", "SELL", "BUY"
        elif z <= -entry_z:
            signal, action_a, action_b = "LONG_A_SHORT_B", "BUY", "SELL"
        else:
            signal, action_a, action_b = "HOLD", "HOLD", "HOLD"

        return {
            "zscore": z,
            "signal": signal,
            "action_a": action_a,
            "action_b": action_b,
            "hedge_ratio": float(beta),
            "spread": float(spread[-1]),
            "confidence": float(min(abs(z) / 4.0, 1.0)),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("pairs_signal failed: %s", exc)
        return {
            "zscore": 0.0,
            "signal": "HOLD",
            "action_a": "HOLD",
            "action_b": "HOLD",
            "hedge_ratio": None,
            "spread": None,
            "confidence": 0.0,
            "error": str(exc),
        }


def find_cointegrated_pairs(
    prices_by_symbol: Dict[str, List[float]],
    threshold: float = 0.05,
) -> List[dict]:
    """Scan all symbol pairs, return those cointegrated below the p-value threshold."""
    results: List[dict] = []
    try:
        symbols = list(prices_by_symbol.keys())
        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                sym_a, sym_b = symbols[i], symbols[j]
                try:
                    raw_a = np.asarray(prices_by_symbol[sym_a], dtype=float)
                    raw_b = np.asarray(prices_by_symbol[sym_b], dtype=float)
                    n = min(len(raw_a), len(raw_b))
                    if n < 50:
                        continue
                    a = raw_a[-n:]
                    b = raw_b[-n:]
                    res = check_cointegration(a, b)
                    p = res.get("p_value")
                    if p is None or p >= threshold:
                        continue
                    results.append(
                        {
                            "pair": [sym_a, sym_b],
                            "p_value": float(p),
                            "hedge_ratio": res.get("hedge_ratio"),
                            "half_life": res.get("half_life"),
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("pair %s/%s failed: %s", sym_a, sym_b, exc)
                    continue
        results.sort(key=lambda r: r["p_value"])
        return results
    except Exception as exc:  # noqa: BLE001
        logger.warning("find_cointegrated_pairs failed: %s", exc)
        return results
