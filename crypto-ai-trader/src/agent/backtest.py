"""Backtesting engine using regime-simulated historical data."""
import math
import random
from datetime import datetime, timedelta
from typing import List

import numpy as np


REGIMES = {
    "BULL":     {"drift": +0.0040, "vol": 0.0055, "dur": (30, 80)},
    "BEAR":     {"drift": -0.0040, "vol": 0.0055, "dur": (30, 80)},
    "RANGE":    {"drift":  0.0000, "vol": 0.0030, "dur": (20, 60)},
    "VOLATILE": {"drift":  0.0002, "vol": 0.0160, "dur": (8,  20)},
}

TRANSITIONS = {
    "BULL":     [("RANGE", 0.50), ("BEAR", 0.30), ("VOLATILE", 0.20)],
    "BEAR":     [("RANGE", 0.50), ("BULL", 0.30), ("VOLATILE", 0.20)],
    "RANGE":    [("BULL", 0.35), ("BEAR", 0.35), ("VOLATILE", 0.30)],
    "VOLATILE": [("RANGE", 0.50), ("BULL", 0.25), ("BEAR", 0.25)],
}


def _simulate_ohlcv(days: int, base_price: float, tf_minutes: int = 60) -> List[dict]:
    n_candles = days * 24 * 60 // tf_minutes
    candles = []
    p = base_price
    regime = "RANGE"
    remaining = random.randint(20, 50)
    start = datetime.utcnow() - timedelta(days=days)

    for i in range(n_candles):
        if remaining <= 0:
            names, weights = zip(*TRANSITIONS[regime])
            regime = random.choices(names, weights=weights)[0]
            remaining = random.randint(*REGIMES[regime]["dur"])
        cfg = REGIMES[regime]
        c = p * math.exp(random.gauss(cfg["drift"], cfg["vol"]))
        spread = cfg["vol"] * random.uniform(0.3, 0.7)
        h = max(p, c) * (1 + spread * 0.5)
        l = min(p, c) * (1 - spread * 0.5)
        candles.append({
            "ts": start + timedelta(minutes=i * tf_minutes),
            "open": p, "high": h, "low": l, "close": c,
            "volume": random.uniform(200, 3000),
            "regime": regime,
        })
        p = c
        remaining -= 1
    return candles


def _ema(series: np.ndarray, period: int) -> np.ndarray:
    k = 2 / (period + 1)
    out = np.empty_like(series, dtype=float)
    out[0] = series[0]
    for i in range(1, len(series)):
        out[i] = series[i] * k + out[i - 1] * (1 - k)
    return out


def _rsi(closes: np.ndarray, period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    d = np.diff(closes[-(period + 1):])
    avg_gain = np.where(d > 0, d, 0.0).mean()
    avg_loss = np.where(d < 0, -d, 0.0).mean()
    return 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)


def _signal(window: List[dict]) -> tuple:
    """Trend-following signal: EMA alignment + momentum confirmation."""
    if len(window) < 30:
        return "HOLD", 0.0
    closes = np.array([c["close"] for c in window])
    ema9  = _ema(closes, 9)
    ema21 = _ema(closes, 21)
    ema50 = _ema(closes, min(50, len(closes) - 1))

    # Trend: EMAs aligned
    bull = ema9[-1] > ema21[-1] > ema50[-1]
    bear = ema9[-1] < ema21[-1] < ema50[-1]

    # Momentum: recent EMA9 direction
    ema9_rising  = ema9[-1] > ema9[-3]
    ema9_falling = ema9[-1] < ema9[-3]

    # Price vs EMA21 (entry timing — don't chase too far above/below)
    price = closes[-1]
    dist = abs(price - ema21[-1]) / ema21[-1] if ema21[-1] > 0 else 0

    if bull and ema9_rising and dist < 0.06:
        return "BUY",  min(0.5 + (ema9[-1] - ema21[-1]) / ema21[-1] * 5, 0.85)
    if bear and ema9_falling and dist < 0.06:
        return "SELL", min(0.5 + (ema21[-1] - ema9[-1]) / ema21[-1] * 5, 0.85)
    return "HOLD", 0.0


def run_backtest(symbol: str, days: int = 30,
                 tp_pct: float = 0.04, sl_pct: float = 0.02,
                 initial_capital: float = 10000.0) -> dict:
    from ..exchanges.demo_client import _SEED_PRICES
    base_price = _SEED_PRICES.get(symbol, 100.0)
    candles = _simulate_ohlcv(days, base_price)

    capital = initial_capital
    equity  = [capital]
    trades  = []
    open_trade = None

    for i in range(30, len(candles)):
        c = candles[i]
        price = c["close"]

        if open_trade:
            side  = open_trade["side"]
            entry = open_trade["entry"]
            tp = entry * (1 + tp_pct) if side == "BUY" else entry * (1 - tp_pct)
            sl = entry * (1 - sl_pct) if side == "BUY" else entry * (1 + sl_pct)
            hit_tp = c["high"] >= tp if side == "BUY" else c["low"] <= tp
            hit_sl = c["low"]  <= sl if side == "BUY" else c["high"] >= sl
            if hit_tp or hit_sl:
                pnl_pct = tp_pct if hit_tp else -sl_pct
                capital += open_trade["cost"] * pnl_pct
                trades.append({
                    "open_at":  open_trade["at"].isoformat(),
                    "close_at": c["ts"].isoformat(),
                    "side": side,
                    "pnl_pct": round(pnl_pct * 100, 2),
                    "win": hit_tp,
                    "regime": c["regime"],
                })
                open_trade = None

        equity.append(round(capital, 2))

        if not open_trade:
            action, _ = _signal(candles[max(0, i - 60):i])
            if action != "HOLD":
                open_trade = {"side": action, "entry": price,
                               "cost": capital * 0.10, "at": c["ts"]}

    if not trades:
        return {"symbol": symbol, "days": days, "total_trades": 0,
                "win_rate": 0, "total_return_pct": 0, "sharpe": 0,
                "max_drawdown_pct": 0, "equity_curve": [], "trades": []}

    eq = np.array(equity, dtype=float)
    rets = np.diff(eq) / np.where(eq[:-1] != 0, eq[:-1], 1)
    sharpe = float((rets.mean() / rets.std()) * math.sqrt(8760 / (days * 24))) if rets.std() > 0 else 0.0

    run_max  = np.maximum.accumulate(eq)
    max_dd   = float(((eq - run_max) / np.where(run_max != 0, run_max, 1)).min() * 100)
    wins     = sum(1 for t in trades if t["win"])
    tot_ret  = (capital - initial_capital) / initial_capital * 100

    step = max(1, len(equity) // 200)
    curve = [{"i": i, "v": equity[i]} for i in range(0, len(equity), step)]

    return {
        "symbol":            symbol,
        "days":              days,
        "total_trades":      len(trades),
        "win_rate":          round(wins / len(trades) * 100, 1),
        "total_return_pct":  round(tot_ret, 2),
        "sharpe":            round(sharpe, 2),
        "max_drawdown_pct":  round(max_dd, 2),
        "initial_capital":   initial_capital,
        "final_capital":     round(capital, 2),
        "equity_curve":      curve,
        "trades":            trades[-20:],
    }
