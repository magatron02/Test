"""Risk analytics: Sharpe, Sortino, VaR, Calmar, Profit Factor, streaks."""
from __future__ import annotations
import math
from typing import List, Dict, Any


def compute_metrics(
    trades: List[Dict[str, Any]],
    equity_curve: List[float],
    initial_capital: float = 1000.0,
    risk_free_annual: float = 0.04,
    periods_per_year: int = 365,
) -> Dict[str, Any]:
    """
    Compute comprehensive risk analytics from a list of closed trades and
    an equity curve (list of equity values sampled per bar/trade).

    trades: list of dicts with keys: pnl_pct (float), win (bool)
    equity_curve: list of portfolio values over time
    """
    if not trades:
        return _empty()

    pnl_pcts = [t.get("pnl_pct", 0.0) for t in trades]
    wins = [bool(t.get("win", False)) for t in trades]
    n = len(pnl_pcts)

    total_return = (equity_curve[-1] / initial_capital - 1) * 100 if equity_curve else 0.0

    # ── Sharpe (annualised, trade-level returns) ─────────────────────────────
    sharpe = _sharpe(pnl_pcts, risk_free_annual, periods_per_year)

    # ── Sortino (downside deviation only) ────────────────────────────────────
    sortino = _sortino(pnl_pcts, risk_free_annual, periods_per_year)

    # ── VaR 95 % (historical) ────────────────────────────────────────────────
    var_95 = _var(pnl_pcts, 0.05)

    # ── Max Drawdown from equity curve ───────────────────────────────────────
    max_dd = _max_drawdown(equity_curve) * 100

    # ── Calmar Ratio (annualised return / max drawdown) ──────────────────────
    calmar = _calmar(total_return, max_dd, n, periods_per_year)

    # ── Profit Factor ────────────────────────────────────────────────────────
    gross_profit = sum(p for p in pnl_pcts if p > 0) or 0.0
    gross_loss   = abs(sum(p for p in pnl_pcts if p < 0)) or 0.0
    profit_factor = (gross_profit / gross_loss) if gross_loss else float("inf")
    if profit_factor == float("inf"):
        profit_factor = 99.0

    # ── Streaks ──────────────────────────────────────────────────────────────
    max_win_streak, max_loss_streak, cur_win, cur_loss = 0, 0, 0, 0
    for w in wins:
        if w:
            cur_win += 1; cur_loss = 0
        else:
            cur_loss += 1; cur_win = 0
        max_win_streak  = max(max_win_streak,  cur_win)
        max_loss_streak = max(max_loss_streak, cur_loss)

    win_rate = sum(wins) / n * 100

    # ── Avg win / avg loss ───────────────────────────────────────────────────
    winning = [p for p in pnl_pcts if p > 0]
    losing  = [p for p in pnl_pcts if p < 0]
    avg_win  = sum(winning) / len(winning) if winning else 0.0
    avg_loss = sum(losing)  / len(losing)  if losing  else 0.0
    expectancy = (win_rate / 100 * avg_win) + ((1 - win_rate / 100) * avg_loss)

    return {
        "total_trades":     n,
        "win_rate":         round(win_rate, 1),
        "total_return_pct": round(total_return, 2),
        "sharpe":           round(sharpe,  3),
        "sortino":          round(sortino, 3),
        "calmar":           round(calmar,  3),
        "var_95_pct":       round(var_95,  2),
        "max_drawdown_pct": round(max_dd,  2),
        "profit_factor":    round(profit_factor, 2),
        "max_win_streak":   max_win_streak,
        "max_loss_streak":  max_loss_streak,
        "avg_win_pct":      round(avg_win,  2),
        "avg_loss_pct":     round(avg_loss, 2),
        "expectancy_pct":   round(expectancy, 3),
        "gross_profit_pct": round(gross_profit, 2),
        "gross_loss_pct":   round(gross_loss, 2),
    }


# ── helpers ──────────────────────────────────────────────────────────────────

def _empty() -> Dict[str, Any]:
    return {k: 0 for k in [
        "total_trades", "win_rate", "total_return_pct", "sharpe", "sortino",
        "calmar", "var_95_pct", "max_drawdown_pct", "profit_factor",
        "max_win_streak", "max_loss_streak", "avg_win_pct", "avg_loss_pct",
        "expectancy_pct", "gross_profit_pct", "gross_loss_pct",
    ]}


def _mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _std(xs: List[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def _sharpe(pnl_pcts: List[float], rf_annual: float, periods: int) -> float:
    if len(pnl_pcts) < 2:
        return 0.0
    rf_per_trade = rf_annual / periods
    excess = [p / 100 - rf_per_trade for p in pnl_pcts]
    sd = _std(excess)
    if sd == 0:
        return 0.0
    return (_mean(excess) / sd) * math.sqrt(periods)


def _sortino(pnl_pcts: List[float], rf_annual: float, periods: int) -> float:
    if len(pnl_pcts) < 2:
        return 0.0
    rf_per_trade = rf_annual / periods
    returns = [p / 100 for p in pnl_pcts]
    mean_r = _mean(returns)
    downside = [min(r - rf_per_trade, 0) ** 2 for r in returns]
    dd_std = math.sqrt(sum(downside) / len(downside)) if downside else 0
    if dd_std == 0:
        return 0.0
    return ((mean_r - rf_per_trade) / dd_std) * math.sqrt(periods)


def _var(pnl_pcts: List[float], alpha: float = 0.05) -> float:
    """Historical VaR at alpha significance (returned as negative pct)."""
    if not pnl_pcts:
        return 0.0
    sorted_r = sorted(pnl_pcts)
    idx = max(0, int(math.floor(alpha * len(sorted_r))) - 1)
    return sorted_r[idx]


def _max_drawdown(equity: List[float]) -> float:
    if len(equity) < 2:
        return 0.0
    peak = equity[0]
    max_dd = 0.0
    for v in equity:
        if v > peak:
            peak = v
        dd = (peak - v) / peak if peak else 0
        max_dd = max(max_dd, dd)
    return max_dd


def _calmar(total_return_pct: float, max_dd_pct: float, n_trades: int, periods: int) -> float:
    """Annualised return / max drawdown."""
    if max_dd_pct == 0 or n_trades == 0:
        return 0.0
    annual_factor = periods / n_trades
    annual_return = total_return_pct * annual_factor
    return annual_return / max_dd_pct
