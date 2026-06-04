"""Quantitative features from "Machine Learning for Trading".

Implements three self-contained feature blocks:
  * kalman_trend       - constant-velocity Kalman filter trend/velocity (Ch.4)
  * garch_volatility   - GARCH(1,1) forward volatility forecast (Ch.9)
  * worldquant_alphas  - subset of the WorldQuant 101 formulaic alphas (Ch.24)

Pure numpy throughout, except the `arch` package which is imported lazily
inside garch_volatility. All public functions return dictionaries and are
defensive: they degrade gracefully rather than raising.
"""

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


def kalman_trend(closes: np.ndarray) -> dict:
    """1D Kalman filter on closing prices to extract a denoised trend + velocity.

    Implements a constant-velocity Kalman filter manually with numpy:
      state = [price, velocity]; transition F = [[1,1],[0,1]]; measurement H=[1,0].
      process_var ~ 1e-3 * mean(price), measurement_var ~ var(price diffs).

    Returns a dict with the last filtered price, velocity estimate, a trend
    label and the percent deviation of the raw last close from the filtered
    estimate. Requires >= 20 closes; otherwise returns a FLAT fallback.
    """
    closes = np.asarray(closes, dtype=float).ravel()

    if closes.size < 20:
        last = float(closes[-1]) if closes.size else 0.0
        return {"trend": "FLAT", "kalman_price": last, "velocity": 0.0, "deviation_pct": 0.0}

    # Noise tuning derived from the data scale.
    process_var = 1e-3 * float(np.mean(closes))
    diffs = np.diff(closes)
    measurement_var = float(np.var(diffs))
    if measurement_var <= 0.0:
        measurement_var = 1e-6

    # State-space matrices for a constant-velocity model.
    F = np.array([[1.0, 1.0], [0.0, 1.0]])
    H = np.array([[1.0, 0.0]])
    Q = process_var * np.array([[1.0, 0.0], [0.0, 1.0]])
    R = np.array([[measurement_var]])

    # Initial state and covariance.
    x = np.array([[closes[0]], [0.0]])
    P = np.eye(2) * 1.0

    for z in closes[1:]:
        # Predict.
        x = F @ x
        P = F @ P @ F.T + Q
        # Update.
        y = np.array([[z]]) - H @ x
        S = H @ P @ H.T + R
        K = P @ H.T @ np.linalg.inv(S)
        x = x + K @ y
        P = (np.eye(2) - K @ H) @ P

    filtered_price = float(x[0, 0])
    velocity = float(x[1, 0])

    # Trend label from velocity relative to a small price-scaled threshold.
    threshold = 1e-4 * float(np.mean(closes))
    if velocity > threshold:
        trend = "BULLISH"
    elif velocity < -threshold:
        trend = "BEARISH"
    else:
        trend = "FLAT"

    raw_last = float(closes[-1])
    deviation_pct = (raw_last - filtered_price) / filtered_price * 100.0 if filtered_price else 0.0

    return {
        "kalman_price": filtered_price,
        "velocity": velocity,
        "trend": trend,
        "deviation_pct": float(deviation_pct),
    }


def _ewma_vol(returns: np.ndarray, lam: float = 0.94) -> Optional[float]:
    """RiskMetrics-style EWMA volatility (percent units). Returns None if empty."""
    returns = np.asarray(returns, dtype=float).ravel()
    if returns.size == 0:
        return None
    var = float(returns[0] ** 2)
    for r in returns[1:]:
        var = lam * var + (1.0 - lam) * float(r) ** 2
    return float(np.sqrt(max(var, 0.0)))


def garch_volatility(returns: np.ndarray, horizon: int = 5) -> dict:
    """Forecast forward volatility with GARCH(1,1) via the `arch` package.

    `returns` is an array of pct returns (e.g. close.pct_change*100). Needs
    >= 50 points for the GARCH path. On any failure or insufficient data, falls
    back to a simple EWMA (lambda=0.94) vol estimate. Always returns a dict.
    """
    returns = np.asarray(returns, dtype=float).ravel()
    returns = returns[np.isfinite(returns)]

    def _ewma_fallback() -> dict:
        cur = _ewma_vol(returns) or 0.0
        # Compare a short-window EWMA against the longer mean of |returns| as a
        # crude regime hint when GARCH is unavailable.
        recent = returns[-10:] if returns.size >= 10 else returns
        recent_vol = _ewma_vol(recent) or cur
        mean_abs = float(np.mean(np.abs(returns))) if returns.size else 0.0
        if mean_abs <= 0.0:
            ratio = 1.0
        else:
            ratio = recent_vol / mean_abs
        if ratio > 1.1:
            hint = "RISING_VOL"
        elif ratio < 0.9:
            hint = "FALLING_VOL"
        else:
            hint = "STABLE"
        return {
            "forecast_vol_pct": float(recent_vol),
            "current_vol_pct": float(cur),
            "vol_ratio": float(ratio),
            "regime_hint": hint,
        }

    if returns.size < 50:
        return _ewma_fallback()

    try:
        from arch import arch_model

        model = arch_model(returns, vol="GARCH", p=1, q=1, mean="Zero", rescale=False)
        res = model.fit(disp="off")

        # Conditional vol of the last in-sample observation.
        current_vol = float(res.conditional_volatility[-1])

        fc = res.forecast(horizon=horizon, reindex=False)
        # Mean forecast variance across the horizon, then sqrt -> vol.
        var_row = np.asarray(fc.variance.values)[-1]
        forecast_vol = float(np.sqrt(max(float(np.mean(var_row)), 0.0)))

        vol_ratio = forecast_vol / current_vol if current_vol > 0 else 1.0
        if vol_ratio > 1.05:
            hint = "RISING_VOL"
        elif vol_ratio < 0.95:
            hint = "FALLING_VOL"
        else:
            hint = "STABLE"

        return {
            "forecast_vol_pct": forecast_vol,
            "current_vol_pct": current_vol,
            "vol_ratio": float(vol_ratio),
            "regime_hint": hint,
        }
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("GARCH fit failed (%s); falling back to EWMA", exc)
        return _ewma_fallback()


def _ts_rank(arr: np.ndarray, window: int) -> float:
    """Fractional rank (0..1) of the last value within the trailing `window`."""
    arr = np.asarray(arr, dtype=float).ravel()
    if arr.size < window or window < 1:
        return float("nan")
    w = arr[-window:]
    last = w[-1]
    # Rank = fraction of window values <= last value.
    return float(np.sum(w <= last) / window)


def _rolling_corr(a: np.ndarray, b: np.ndarray, window: int) -> float:
    """Pearson correlation of the last `window` values of a and b."""
    a = np.asarray(a, dtype=float).ravel()
    b = np.asarray(b, dtype=float).ravel()
    n = min(a.size, b.size)
    if n < window or window < 2:
        return float("nan")
    aw = a[-window:]
    bw = b[-window:]
    sa = np.std(aw)
    sb = np.std(bw)
    if sa <= 0 or sb <= 0:
        return 0.0
    return float(np.corrcoef(aw, bw)[0, 1])


def _zscore(arr: np.ndarray, window: int) -> float:
    """Z-score of the last value over the trailing `window`."""
    arr = np.asarray(arr, dtype=float).ravel()
    if arr.size < window or window < 2:
        return float("nan")
    w = arr[-window:]
    mu = float(np.mean(w))
    sd = float(np.std(w))
    if sd <= 0:
        return 0.0
    return float((w[-1] - mu) / sd)


def worldquant_alphas(opens, highs, lows, closes, volumes) -> dict:
    """Compute a curated subset of WorldQuant 101 formulaic alphas (vectorised).

    All inputs are 1D numpy arrays of equal length (>= 30). Returns a dict of
    named alpha values on the most recent bar, rounded to 5 dp. Returns an empty
    dict on insufficient length or any error.
    """
    try:
        o = np.asarray(opens, dtype=float).ravel()
        h = np.asarray(highs, dtype=float).ravel()
        l = np.asarray(lows, dtype=float).ravel()
        c = np.asarray(closes, dtype=float).ravel()
        v = np.asarray(volumes, dtype=float).ravel()

        n = min(o.size, h.size, l.size, c.size, v.size)
        if n < 30:
            return {}
        o, h, l, c, v = o[-n:], h[-n:], l[-n:], c[-n:], v[-n:]

        # Returns series (simple pct change).
        rets = np.zeros_like(c)
        rets[1:] = (c[1:] - c[:-1]) / np.where(c[:-1] == 0, np.nan, c[:-1])

        # alpha001-like: sign-of-returns momentum proxy over recent window.
        win = 10
        recent_rets = rets[-win:]
        recent_rets = recent_rets[np.isfinite(recent_rets)]
        alpha001_like = float(np.mean(np.sign(recent_rets))) if recent_rets.size else 0.0

        # Cross-sectional rank substitute over short window via ts-rank series.
        def _rank_series(arr, window):
            out = np.full(arr.size, np.nan)
            for i in range(window - 1, arr.size):
                w = arr[i - window + 1:i + 1]
                out[i] = np.sum(w <= w[-1]) / window
            return out

        rank_open = _rank_series(o, 10)
        rank_vol = _rank_series(v, 10)

        # alpha003-like: -corr(rank(open), rank(volume), 10).
        alpha003_like = -_rolling_corr(rank_open, rank_vol, 10)

        # alpha004-like: -ts_rank(low, 9).
        alpha004_like = -_ts_rank(l, 9)

        # alpha006-like: -corr(open, volume, 10).
        alpha006_like = -_rolling_corr(o, v, 10)

        # alpha012-like: sign(delta(volume,1)) * -delta(close,1).
        dvol = v[-1] - v[-2]
        dclose = c[-1] - c[-2]
        alpha012_like = float(np.sign(dvol) * (-dclose))

        # alpha101: (close - open) / (high - low + 1e-3).
        alpha101 = float((c[-1] - o[-1]) / (h[-1] - l[-1] + 1e-3))

        # Momentum features.
        mom_5 = float((c[-1] / c[-6] - 1.0) * 100.0) if c[-6] != 0 else 0.0
        mom_10 = float((c[-1] / c[-11] - 1.0) * 100.0) if c[-11] != 0 else 0.0

        # Volume z-score over last 20.
        vol_zscore = _zscore(v, 20)

        # Intrabar range and close location within range.
        hl_range_pct = float((h[-1] - l[-1]) / c[-1] * 100.0) if c[-1] != 0 else 0.0
        close_to_high = float((c[-1] - l[-1]) / (h[-1] - l[-1] + 1e-9))

        def _clean(x):
            x = float(x)
            return 0.0 if not np.isfinite(x) else round(x, 5)

        return {
            "alpha001_like": _clean(alpha001_like),
            "alpha003_like": _clean(alpha003_like),
            "alpha004_like": _clean(alpha004_like),
            "alpha006_like": _clean(alpha006_like),
            "alpha012_like": _clean(alpha012_like),
            "alpha101": _clean(alpha101),
            "mom_5": _clean(mom_5),
            "mom_10": _clean(mom_10),
            "vol_zscore": _clean(vol_zscore),
            "hl_range_pct": _clean(hl_range_pct),
            "close_to_high": _clean(close_to_high),
        }
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("worldquant_alphas failed: %s", exc)
        return {}
