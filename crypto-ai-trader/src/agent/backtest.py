"""
Enhanced Backtest Engine — Market Regime + Chart Patterns + Kelly Sizing + Risk Engine.

Three backtest modes:
  basic      — original EMA-crossover baseline (v1 benchmark)
  hybrid     — StrategyManager.hybrid_signal with regime-aware confidence thresholds
  autotrade  — full AI stack: regime + chart patterns + Kelly position sizing + circuit breaker

Results include:
  - Overall metrics (return, Sharpe, win rate, max drawdown)
  - Per-regime breakdown (performance in each of the 5 regimes)
  - Per-pattern breakdown (best and worst chart patterns)
  - Side-by-side comparison (basic vs autotrade)
  - Full equity curve
  - Last 50 annotated trades
"""
import logging
import math
import random
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

BINANCE_KLINES = "https://api.binance.com/api/v3/klines"

# Regime → preferred single strategy (the policy the RL bandit converges to).
# Ichimoku & SMC work well in trending markets; mean-reversion for ranging.
_REGIME_STRATEGY = {
    "BULL_TREND": "ichimoku",      # Ichimoku excels in trending markets
    "BEAR_TREND": "smc",           # SMC detects bearish structure + liquidity sweeps
    "RANGING":    "mean_reversion",
    "VOLATILE":   "mean_reversion",
    "CRASH":      "smc",           # SMC BOS/ChoCH useful for crash structure reads
}

# ── Regime simulation parameters (used when Binance is unreachable) ───────────
_SIM_REGIMES = {
    "BULL":     {"drift": +0.0040, "vol": 0.0055, "dur": (30, 80)},
    "BEAR":     {"drift": -0.0040, "vol": 0.0055, "dur": (30, 80)},
    "RANGE":    {"drift":  0.0000, "vol": 0.0030, "dur": (20, 60)},
    "VOLATILE": {"drift":  0.0002, "vol": 0.0160, "dur": (8,  20)},
}
_SIM_TRANSITIONS = {
    "BULL":     [("RANGE", 0.50), ("BEAR", 0.30), ("VOLATILE", 0.20)],
    "BEAR":     [("RANGE", 0.50), ("BULL", 0.30), ("VOLATILE", 0.20)],
    "RANGE":    [("BULL", 0.35), ("BEAR", 0.35), ("VOLATILE", 0.30)],
    "VOLATILE": [("RANGE", 0.50), ("BULL", 0.25), ("BEAR", 0.25)],
}


# ── Data fetching ─────────────────────────────────────────────────────────────

def _simulate_ohlcv(days: int, base_price: float, tf_minutes: int = 60) -> List[dict]:
    n = days * 24 * 60 // tf_minutes
    candles, p = [], base_price
    regime, remaining = "RANGE", random.randint(20, 50)
    start = datetime.utcnow() - timedelta(days=days)
    for i in range(n):
        if remaining <= 0:
            names, weights = zip(*_SIM_TRANSITIONS[regime])
            regime = random.choices(names, weights=weights)[0]
            remaining = random.randint(*_SIM_REGIMES[regime]["dur"])
        cfg = _SIM_REGIMES[regime]
        c = p * math.exp(random.gauss(cfg["drift"], cfg["vol"]))
        spread = cfg["vol"] * random.uniform(0.3, 0.7)
        candles.append({
            "ts":     start + timedelta(minutes=i * tf_minutes),
            "open":   p,
            "high":   max(p, c) * (1 + spread * 0.5),
            "low":    min(p, c) * (1 - spread * 0.5),
            "close":  c,
            "volume": random.uniform(200, 3000),
            "sim_regime": regime,
        })
        p = c
        remaining -= 1
    return candles


async def _fetch_real_ohlcv(symbol: str, days: int, tf_minutes: int = 60) -> List[dict]:
    import aiohttp
    needed = days * 24 * 60 // tf_minutes
    binance_sym = symbol.replace("/", "")
    interval_map = {60: "1h", 15: "15m", 240: "4h", 1440: "1d"}
    interval = interval_map.get(tf_minutes, "1h")
    out: List[dict] = []
    end_time: Optional[int] = None

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        while len(out) < needed:
            limit = min(1000, needed - len(out))
            params = {"symbol": binance_sym, "interval": interval, "limit": limit}
            if end_time is not None:
                params["endTime"] = end_time
            async with session.get(BINANCE_KLINES, params=params) as resp:
                resp.raise_for_status()
                raw = await resp.json()
            if not raw:
                break
            chunk = [{
                "ts":     datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc).replace(tzinfo=None),
                "open":   float(row[1]),
                "high":   float(row[2]),
                "low":    float(row[3]),
                "close":  float(row[4]),
                "volume": float(row[5]),
                "sim_regime": "LIVE",
            } for row in raw]
            out = chunk + out
            end_time = raw[0][0] - 1
            if len(raw) < limit:
                break

    if not out:
        raise ValueError("Binance returned no candles")
    return out


# ── Convert dict candles → OHLCV objects ─────────────────────────────────────

def _to_ohlcv(candles: List[dict]):
    from ..exchanges.base import OHLCV
    return [
        OHLCV(
            timestamp=c["ts"],
            open=c["open"], high=c["high"], low=c["low"],
            close=c["close"], volume=c["volume"],
        )
        for c in candles
    ]


# ── Rolling Kelly tracker ─────────────────────────────────────────────────────

class _KellyTracker:
    """Rolling Kelly sizer with Bayesian warm-start (matches PositionSizer logic)."""

    PRIOR_N = 5
    PRIOR_P = 0.55
    PRIOR_B = 1.5

    def __init__(self, fraction: float = 0.25):
        self.fraction  = fraction
        self.wins      = 0
        self.losses    = 0
        self.gain_sum  = 0.0
        self.loss_sum  = 0.0

    def update(self, pnl_pct: float):
        if pnl_pct > 0:
            self.wins     += 1
            self.gain_sum += pnl_pct
        else:
            self.losses   += 1
            self.loss_sum += abs(pnl_pct)

    @property
    def fraction_for_trade(self) -> float:
        P, B = self.PRIOR_P, self.PRIOR_B
        bw = self.wins   + self.PRIOR_N * P
        bl = self.losses + self.PRIOR_N * (1 - P)
        bt = bw + bl
        p  = bw / bt
        q  = 1.0 - p
        aw = ((self.gain_sum + self.PRIOR_N * P * B) / bw) if bw > 0 else B
        al = ((self.loss_sum + self.PRIOR_N * (1 - P)) / bl) if bl > 0 else 1.0
        b  = aw / al if al > 0 else B
        kelly = (p * b - q) / b
        # Minimum 2% floor so system keeps trading and collecting data
        # (live system's RiskEngine provides the true safety circuit breaker)
        return max(0.02, min(kelly * self.fraction, 0.15))


# ── Basic signal (v1 baseline — EMA crossover) ────────────────────────────────

def _ema(series: np.ndarray, period: int) -> np.ndarray:
    k = 2 / (period + 1)
    out = np.empty_like(series, dtype=float)
    out[0] = series[0]
    for i in range(1, len(series)):
        out[i] = series[i] * k + out[i - 1] * (1 - k)
    return out


def _basic_signal(window: List[dict]) -> Tuple[str, float]:
    if len(window) < 30:
        return "HOLD", 0.0
    closes = np.array([c["close"] for c in window])
    ema9  = _ema(closes, 9)
    ema21 = _ema(closes, 21)
    ema50 = _ema(closes, min(50, len(closes) - 1))
    bull  = ema9[-1] > ema21[-1] > ema50[-1]
    bear  = ema9[-1] < ema21[-1] < ema50[-1]
    price = closes[-1]
    dist  = abs(price - ema21[-1]) / ema21[-1] if ema21[-1] > 0 else 0
    if bull and ema9[-1] > ema9[-3] and dist < 0.06:
        return "BUY",  min(0.5 + (ema9[-1] - ema21[-1]) / ema21[-1] * 5, 0.85)
    if bear and ema9[-1] < ema9[-3] and dist < 0.06:
        return "SELL", min(0.5 + (ema21[-1] - ema9[-1]) / ema21[-1] * 5, 0.85)
    return "HOLD", 0.0


# ── Hybrid / Autotrade signal ─────────────────────────────────────────────────

def _ai_signal(
    symbol: str,
    ohlcv_window,
    use_patterns: bool = True,
    use_regime: bool = True,
) -> Tuple[str, float, str, str, str]:
    """
    Returns (action, confidence, strategy, regime_name, patterns_summary).
    Wraps the production StrategyManager + MarketRegime + ChartPatterns.
    """
    from .market_analyzer import analyze
    from .market_regime import detect_regime
    from .strategy_manager import StrategyManager, TradingSignal

    if len(ohlcv_window) < 30:
        return "HOLD", 0.0, "none", "RANGING", ""

    price = ohlcv_window[-1].close
    change_24h = (price - ohlcv_window[-24].close) / ohlcv_window[-24].close * 100 \
        if len(ohlcv_window) >= 24 else 0.0

    analysis = analyze(symbol, ohlcv_window, price, change_24h)
    regime   = detect_regime(ohlcv_window, analysis) if use_regime else None
    regime_name = regime.regime if regime else "RANGING"

    sm = StrategyManager()
    # Pick the strategy that fits the regime (the policy the RL bandit converges
    # to). Blending all strategies lets trend & mean-reversion cancel to HOLD.
    if use_regime and regime:
        strat = _REGIME_STRATEGY.get(regime.regime, "trend")
        signal = sm.signal_for_strategy(strat, analysis)
        # Fallback: if primary strategy has no conviction, try trend-following
        if signal.action == "HOLD" and signal.confidence < 0.20 and strat not in ("trend", "mean_reversion"):
            signal = sm.signal_for_strategy("trend", analysis)
    else:
        signal = sm.get_signal(analysis)

    # Regime-aware confidence threshold
    min_conf = 0.55
    if use_regime and regime:
        if regime.regime == "CRASH":
            min_conf = 0.85
        elif regime.regime == "VOLATILE":
            min_conf = 0.70
        elif regime.regime == "BEAR_TREND":
            min_conf = 0.60

    if signal.action != "HOLD" and signal.confidence < min_conf:
        return "HOLD", signal.confidence, signal.strategy, regime_name, \
               getattr(analysis, "pattern_summary", "")

    # In bear trend / crash, suppress new BUYs
    if use_regime and regime and regime.regime in ("CRASH", "BEAR_TREND") \
            and signal.action == "BUY":
        return "HOLD", signal.confidence, signal.strategy, regime_name, \
               getattr(analysis, "pattern_summary", "")

    return (signal.action, signal.confidence, signal.strategy, regime_name,
            getattr(analysis, "pattern_summary", ""))


# ── Core simulation loop ──────────────────────────────────────────────────────

def _run_loop(
    symbol: str,
    candles: List[dict],
    tp_pct: float,
    sl_pct: float,
    initial_capital: float,
    mode: str = "basic",       # basic | hybrid | autotrade
    window_size: int = 80,
) -> Tuple[dict, list, list, list]:
    """
    Core simulation loop shared by all modes.
    Returns (metrics_dict, curve_list, trades_list, equity_raw).
    """
    capital = initial_capital
    equity  = [capital]
    trades: List[dict] = []
    open_trade = None
    kelly = _KellyTracker()

    # Regime + pattern stats
    regime_stats: Dict[str, dict] = defaultdict(
        lambda: {"trades": 0, "wins": 0, "pnl_sum": 0.0}
    )
    pattern_stats: Dict[str, dict] = defaultdict(
        lambda: {"trades": 0, "wins": 0, "pnl_sum": 0.0}
    )

    # Circuit breaker (autotrade mode only)
    high_water = initial_capital
    circuit_open = False

    ohlcv_cache = _to_ohlcv(candles)

    for i in range(window_size, len(candles)):
        c = candles[i]
        price = c["close"]

        # --- Update circuit breaker ---
        if capital > high_water:
            high_water = capital
        drawdown = (high_water - capital) / high_water if high_water > 0 else 0
        if mode == "autotrade":
            circuit_open = drawdown >= 0.10

        # --- Check open trade exit ---
        if open_trade:
            side  = open_trade["side"]
            entry = open_trade["entry"]
            tp = entry * (1 + tp_pct) if side == "BUY" else entry * (1 - tp_pct)
            sl = entry * (1 - sl_pct) if side == "BUY" else entry * (1 + sl_pct)
            hit_tp = c["high"] >= tp if side == "BUY" else c["low"]  <= tp
            hit_sl = c["low"]  <= sl if side == "BUY" else c["high"] >= sl

            if hit_tp or hit_sl:
                raw_pnl_pct = tp_pct if hit_tp else -sl_pct
                capital += open_trade["cost"] * raw_pnl_pct
                kelly.update(raw_pnl_pct * 100)

                r = open_trade.get("regime", "RANGING")
                regime_stats[r]["trades"] += 1
                regime_stats[r]["pnl_sum"] += raw_pnl_pct * 100
                if hit_tp:
                    regime_stats[r]["wins"] += 1

                for pat in open_trade.get("patterns", []):
                    pattern_stats[pat]["trades"] += 1
                    pattern_stats[pat]["pnl_sum"] += raw_pnl_pct * 100
                    if hit_tp:
                        pattern_stats[pat]["wins"] += 1

                trades.append({
                    "open_at":    open_trade["at"].isoformat(),
                    "close_at":   c["ts"].isoformat(),
                    "side":       side,
                    "entry":      round(entry, 4),
                    "exit":       round(tp if hit_tp else sl, 4),
                    "pnl_pct":    round(raw_pnl_pct * 100, 2),
                    "win":        hit_tp,
                    "regime":     open_trade.get("regime", "RANGING"),
                    "patterns":   open_trade.get("patterns", []),
                    "strategy":   open_trade.get("strategy", ""),
                    "size_pct":   round(open_trade["cost"] / capital * 100, 1),
                })
                open_trade = None

        equity.append(round(capital, 2))

        if open_trade or circuit_open:
            continue

        # --- Get signal ---
        if mode == "basic":
            action, conf = _basic_signal(candles[max(0, i - window_size):i])
            regime_name = candles[i].get("sim_regime", "RANGING")
            patterns_s  = ""
            strategy    = "ema_crossover"
        else:
            ohlcv_win = ohlcv_cache[max(0, i - window_size):i]
            action, conf, strategy, regime_name, patterns_s = _ai_signal(
                symbol, ohlcv_win,
                use_patterns=(mode == "autotrade"),
                use_regime=(mode in ("hybrid", "autotrade")),
            )

        if action not in ("BUY", "SELL"):
            continue

        # --- Position sizing ---
        if mode == "autotrade":
            # Kelly + ATR-based sizing
            frac = kelly.fraction_for_trade
            # Simple ATR proxy from last 14 candles
            if i >= 14:
                recent = candles[i - 14:i]
                trs = [max(r["high"] - r["low"],
                           abs(r["high"] - candles[j]["close"]),
                           abs(r["low"]  - candles[j]["close"]))
                       for j, r in enumerate(recent[1:], i - 13)]
                atr_pct = np.mean(trs) / price * 100 if price > 0 else 2.0
                target_atr = 2.0
                atr_adj = min(target_atr / atr_pct, 1.5) if atr_pct > 0 else 1.0
                atr_adj = max(atr_adj, 0.25)
                frac *= atr_adj
            frac = min(frac, 0.10)
            cost = max(capital * frac, 0.0)
        else:
            cost = capital * 0.10   # fixed 10% baseline

        if cost < 1.0:
            continue

        open_trade = {
            "side":     action,
            "entry":    price,
            "cost":     cost,
            "at":       c["ts"],
            "regime":   regime_name,
            "patterns": [s for s in patterns_s.split() if s] if patterns_s else [],
            "strategy": strategy,
        }

    # --- Close any open position at end ---
    if open_trade:
        price = candles[-1]["close"]
        entry = open_trade["entry"]
        raw_pnl_pct = (price - entry) / entry if open_trade["side"] == "BUY" else (entry - price) / entry
        capital += open_trade["cost"] * raw_pnl_pct
        trades.append({
            "open_at":  open_trade["at"].isoformat(),
            "close_at": candles[-1]["ts"].isoformat(),
            "side":     open_trade["side"],
            "entry":    round(entry, 4),
            "exit":     round(price, 4),
            "pnl_pct":  round(raw_pnl_pct * 100, 2),
            "win":      raw_pnl_pct > 0,
            "regime":   open_trade.get("regime", "RANGING"),
            "patterns": open_trade.get("patterns", []),
            "strategy": open_trade.get("strategy", ""),
            "size_pct": round(open_trade["cost"] / max(capital, 1) * 100, 1),
        })
        equity.append(round(capital, 2))

    # --- Metrics ---
    eq   = np.array(equity, dtype=float)
    rets = np.diff(eq) / np.where(eq[:-1] != 0, eq[:-1], 1)
    # 1-hour candles → annualise with sqrt(8760); use 24*365 to be safe
    sharpe = float((rets.mean() / rets.std()) * math.sqrt(24 * 365)) \
        if len(rets) > 1 and rets.std() > 0 else 0.0
    run_max = np.maximum.accumulate(eq)
    max_dd  = float(((eq - run_max) / np.where(run_max != 0, run_max, 1)).min() * 100)
    wins    = sum(1 for t in trades if t["win"])
    tot_ret = (capital - initial_capital) / initial_capital * 100

    # Equity curve (max 300 points)
    step  = max(1, len(equity) // 300)
    curve = [{"i": idx, "v": equity[idx]} for idx in range(0, len(equity), step)]

    # Regime breakdown
    regime_out = {}
    for rname, rs in regime_stats.items():
        n = rs["trades"]
        regime_out[rname] = {
            "trades":   n,
            "win_rate": round(rs["wins"] / n * 100, 1) if n > 0 else 0,
            "avg_pnl":  round(rs["pnl_sum"] / n, 2)   if n > 0 else 0,
        }

    # Pattern breakdown (top 5 by trade count)
    sorted_patterns = sorted(pattern_stats.items(), key=lambda x: -x[1]["trades"])[:5]
    pattern_out = {}
    for pname, ps in sorted_patterns:
        n = ps["trades"]
        pattern_out[pname] = {
            "trades":   n,
            "win_rate": round(ps["wins"] / n * 100, 1) if n > 0 else 0,
            "avg_pnl":  round(ps["pnl_sum"] / n, 2)   if n > 0 else 0,
        }

    metrics = {
        "total_trades":     len(trades),
        "win_rate":         round(wins / len(trades) * 100, 1) if trades else 0,
        "total_return_pct": round(tot_ret, 2),
        "sharpe":           round(sharpe, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "initial_capital":  initial_capital,
        "final_capital":    round(capital, 2),
        "regime_stats":     regime_out,
        "pattern_stats":    pattern_out,
    }
    return metrics, curve, trades, list(equity)


# ── Public API ────────────────────────────────────────────────────────────────

def run_backtest(
    symbol: str,
    days: int = 30,
    tp_pct: float = 0.04,
    sl_pct: float = 0.02,
    initial_capital: float = 10_000.0,
) -> dict:
    """Synchronous simulated backtest (offline fallback). Compares basic vs autotrade."""
    from ..exchanges.demo_client import _SEED_PRICES
    base_price = _SEED_PRICES.get(symbol, 100.0)
    candles = _simulate_ohlcv(days, base_price)
    return _build_result(symbol, candles, days, tp_pct, sl_pct, initial_capital,
                         data_source="simulated")


async def run_backtest_real(
    symbol: str,
    days: int = 30,
    tp_pct: float = 0.04,
    sl_pct: float = 0.02,
    initial_capital: float = 10_000.0,
) -> dict:
    """Backtest on real Binance klines; falls back to simulation if offline."""
    try:
        candles = await _fetch_real_ohlcv(symbol, days)
        return _build_result(symbol, candles, days, tp_pct, sl_pct, initial_capital,
                             data_source="binance")
    except Exception as e:
        logger.warning("Real backtest unavailable for %s (%s); using simulation", symbol, e)
        return run_backtest(symbol, days, tp_pct, sl_pct, initial_capital)


def _build_result(
    symbol: str,
    candles: List[dict],
    days: int,
    tp_pct: float,
    sl_pct: float,
    initial_capital: float,
    data_source: str,
) -> dict:
    """Run all 3 modes and merge into one result."""
    from .risk_analytics import compute_metrics

    basic_m,  basic_curve,  basic_trades,  basic_eq  = _run_loop(symbol, candles, tp_pct, sl_pct, initial_capital, "basic")
    hybrid_m, hybrid_curve, hybrid_trades, hybrid_eq = _run_loop(symbol, candles, tp_pct, sl_pct, initial_capital, "hybrid")
    ai_m,     ai_curve,     ai_trades,     ai_eq     = _run_loop(symbol, candles, tp_pct, sl_pct, initial_capital, "autotrade")

    basic_analytics  = compute_metrics(basic_trades,  basic_eq,  initial_capital)
    hybrid_analytics = compute_metrics(hybrid_trades, hybrid_eq, initial_capital)
    ai_analytics     = compute_metrics(ai_trades,     ai_eq,     initial_capital)

    def _mode_block(m, curve, analytics):
        return {
            "total_trades":     m["total_trades"],
            "win_rate":         m["win_rate"],
            "total_return_pct": m["total_return_pct"],
            "sharpe":           analytics["sharpe"],
            "sortino":          analytics["sortino"],
            "calmar":           analytics["calmar"],
            "var_95_pct":       analytics["var_95_pct"],
            "max_drawdown_pct": m["max_drawdown_pct"],
            "profit_factor":    analytics["profit_factor"],
            "max_win_streak":   analytics["max_win_streak"],
            "max_loss_streak":  analytics["max_loss_streak"],
            "avg_win_pct":      analytics["avg_win_pct"],
            "avg_loss_pct":     analytics["avg_loss_pct"],
            "expectancy_pct":   analytics["expectancy_pct"],
            "final_capital":    m["final_capital"],
            "equity_curve":     curve,
        }

    # Primary result = autotrade (full AI stack)
    result = {
        "symbol":       symbol,
        "days":         days,
        "data_source":  data_source,
        "tp_pct":       tp_pct,
        "sl_pct":       sl_pct,

        # Top-level metrics = autotrade
        **{k: ai_m[k] for k in (
            "total_trades", "win_rate", "total_return_pct",
            "sharpe", "max_drawdown_pct", "initial_capital", "final_capital",
        )},
        "analytics":     ai_analytics,

        "equity_curve":  ai_curve,
        "trades":        ai_trades[-50:],
        "regime_stats":  ai_m["regime_stats"],
        "pattern_stats": ai_m["pattern_stats"],

        # Side-by-side comparison (full analytics per mode)
        "comparison": {
            "basic":      _mode_block(basic_m,  basic_curve,  basic_analytics),
            "hybrid":     _mode_block(hybrid_m, hybrid_curve, hybrid_analytics),
            "autotrade":  _mode_block(ai_m,     ai_curve,     ai_analytics),
        },
    }
    return result
