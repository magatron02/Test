"""
FINTA bridge — compute any FinTA indicator from Aiterra's OHLCV list format.

Usage
-----
from .finta_bridge import finta_compute, AVAILABLE

# Single indicator
hull_ma = finta_compute("HMA", ohlcv, period=20)

# Indicators already covered natively (don't duplicate)
# RSI, MACD, EMA, BB, ATR, VWAP, Stoch, Ichimoku, Williams %R, CCI
# → use market_analyzer / indicators_extra instead.

# Useful extras via FINTA:
#   HMA   — Hull Moving Average (responsive, smooth)
#   DEMA  — Double EMA (reduces lag)
#   TEMA  — Triple EMA (even less lag)
#   KELT  — Keltner Channel (ATR-based band)
#   DO    — Donchian Channel (breakout detection)
#   CMF   — Chaikin Money Flow (volume pressure)
#   OBV   — On-Balance Volume
#   AO    — Awesome Oscillator
#   DPO   — Detrended Price Oscillator
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

try:
    from finta import TA as _TA
    AVAILABLE = True
except ImportError:
    _TA = None  # type: ignore
    AVAILABLE = False
    logger.debug("finta not installed — pip install finta to enable extra indicators")


def finta_compute(
    indicator: str,
    ohlcv: List[dict],
    **kwargs: Any,
) -> List[Optional[float]]:
    """
    Compute a FinTA indicator over a list of OHLCV dicts.

    Parameters
    ----------
    indicator : str
        FinTA method name, e.g. "HMA", "DEMA", "CMF".
    ohlcv : list of dict
        Each dict must have keys: open, high, low, close, volume.
    **kwargs
        Passed verbatim to the FinTA method (e.g. period=20).

    Returns
    -------
    list of float | None
        Same length as `ohlcv`. Leading values may be None (warm-up period).
    """
    if not AVAILABLE:
        raise ImportError("finta is not installed. Run: pip install finta")

    import pandas as pd

    df = pd.DataFrame([
        {
            "open":   float(c.get("open",   c.get("o", 0))),
            "high":   float(c.get("high",   c.get("h", 0))),
            "low":    float(c.get("low",    c.get("l", 0))),
            "close":  float(c.get("close",  c.get("c", 0))),
            "volume": float(c.get("volume", c.get("v", 0))),
        }
        for c in ohlcv
    ])

    fn = getattr(_TA, indicator.upper(), None)
    if fn is None:
        raise ValueError(f"finta has no indicator '{indicator}'. Check TA.<name>.")

    result = fn(df, **kwargs)

    if isinstance(result, pd.DataFrame):
        series = result.iloc[:, 0]
    else:
        series = result

    out: List[Optional[float]] = []
    for v in series:
        if v is None or (isinstance(v, float) and np.isnan(v)):
            out.append(None)
        else:
            out.append(float(v))
    return out


def finta_last(indicator: str, ohlcv: List[dict], **kwargs: Any) -> Optional[float]:
    """Return only the last (most recent) value of a FinTA indicator."""
    values = finta_compute(indicator, ohlcv, **kwargs)
    for v in reversed(values):
        if v is not None:
            return v
    return None


def indicator_summary(ohlcv: List[dict]) -> Dict[str, Optional[float]]:
    """
    Return a dict of useful FINTA indicators not covered natively.
    Returns None for each if finta is unavailable or data too short.
    """
    if not AVAILABLE or len(ohlcv) < 20:
        return {k: None for k in ("hma_20", "dema_21", "cmf_20", "obv", "ao", "donchian_upper", "donchian_lower")}

    out: Dict[str, Optional[float]] = {}
    try:
        out["hma_20"]         = finta_last("HMA",  ohlcv, period=20)
        out["dema_21"]        = finta_last("DEMA", ohlcv, period=21)
        out["cmf_20"]         = finta_last("CMF",  ohlcv, period=20)
        out["obv"]            = finta_last("OBV",  ohlcv)
        out["ao"]             = finta_last("AO",   ohlcv)
        try:
            do = finta_compute("DO", ohlcv, period=20)
            import pandas as pd
            import finta
            df = pd.DataFrame([{"open": float(c.get("open",0)), "high": float(c.get("high",0)),
                                 "low": float(c.get("low",0)), "close": float(c.get("close",0)),
                                 "volume": float(c.get("volume",0))} for c in ohlcv])
            do_df = _TA.DO(df, period=20)
            out["donchian_upper"] = float(do_df["UPPER"].iloc[-1]) if not do_df.empty else None
            out["donchian_lower"] = float(do_df["LOWER"].iloc[-1]) if not do_df.empty else None
        except Exception:
            out["donchian_upper"] = None
            out["donchian_lower"] = None
    except Exception as exc:
        logger.warning("finta_bridge.indicator_summary: %s", exc)
        return {k: None for k in out}

    return out
