"""Shared pytest fixtures and import-path setup.

The `src.agent` package uses relative imports that only resolve when the
repo root is on sys.path and modules are imported as `src.agent.<mod>`.
We add the repo root here so every test module can do
`from src.agent.market_analyzer import analyze`.
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.exchanges.base import OHLCV  # noqa: E402

SEED = 1234


@pytest.fixture
def synthetic_candles():
    """~120 OHLCV bars with a mild deterministic uptrend (seeded random walk)."""
    rng = np.random.default_rng(SEED)
    n = 120
    base = 100.0
    drift = 0.05          # mild upward drift per bar
    closes = []
    price = base
    for _ in range(n):
        price = price * (1.0 + drift / 100.0) + rng.normal(0.0, 0.4)
        price = max(price, 1.0)
        closes.append(price)

    candles = []
    t0 = datetime(2024, 1, 1)
    prev_close = base
    for i, close in enumerate(closes):
        open_ = prev_close
        high = max(open_, close) + abs(rng.normal(0.0, 0.2))
        low = min(open_, close) - abs(rng.normal(0.0, 0.2))
        vol = float(abs(rng.normal(1000.0, 200.0)))
        candles.append(
            OHLCV(
                timestamp=t0 + timedelta(minutes=5 * i),
                open=float(open_),
                high=float(high),
                low=float(low),
                close=float(close),
                volume=vol,
            )
        )
        prev_close = close
    return candles


@pytest.fixture
def synthetic_returns():
    """(T x N) array of correlated returns for HRP tests.

    Columns 0,1,2 share a common factor (strongly correlated cluster);
    column 3 is independent. Deterministic via fixed seed.
    """
    rng = np.random.default_rng(SEED)
    T = 200
    common = rng.normal(0.0, 0.01, size=T)
    a = common + rng.normal(0.0, 0.002, size=T)
    b = common + rng.normal(0.0, 0.002, size=T)
    c = common + rng.normal(0.0, 0.002, size=T)
    d = rng.normal(0.0, 0.01, size=T)       # independent asset
    return np.column_stack([a, b, c, d])
