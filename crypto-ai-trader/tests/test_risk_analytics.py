"""Tests for src/agent/risk_analytics.py compute_metrics()."""
from src.agent.risk_analytics import compute_metrics


def test_compute_metrics_known_trades():
    # Mostly winning, profitable sequence.
    trades = [
        {"pnl_pct": 3.0, "win": True},
        {"pnl_pct": 2.0, "win": True},
        {"pnl_pct": -1.0, "win": False},
        {"pnl_pct": 4.0, "win": True},
        {"pnl_pct": -2.0, "win": False},
        {"pnl_pct": 5.0, "win": True},
    ]
    equity = [1000.0, 1030.0, 1050.0, 1040.0, 1080.0, 1058.0, 1110.0]
    m = compute_metrics(trades, equity, initial_capital=1000.0)

    assert m["total_trades"] == 6
    # Net positive expectancy -> positive Sharpe.
    assert m["sharpe"] > 0
    # gross profit 14 vs gross loss 3 -> profit factor ~4.67
    assert m["profit_factor"] > 1.0
    assert m["max_win_streak"] >= 2
    assert m["max_loss_streak"] >= 1
    assert 0.0 <= m["win_rate"] <= 100.0
    assert m["total_return_pct"] > 0  # equity ended above start


def test_losing_trades_negative_sharpe():
    trades = [
        {"pnl_pct": -3.0, "win": False},
        {"pnl_pct": -2.0, "win": False},
        {"pnl_pct": 1.0, "win": True},
        {"pnl_pct": -4.0, "win": False},
    ]
    equity = [1000.0, 970.0, 951.0, 960.0, 922.0]
    m = compute_metrics(trades, equity, initial_capital=1000.0)
    assert m["sharpe"] < 0
    assert m["profit_factor"] < 1.0


def test_empty_trades_safe_structure():
    m = compute_metrics([], [], initial_capital=1000.0)
    assert isinstance(m, dict)
    # Empty structure has all keys present and zeroed, no crash.
    for key in ("total_trades", "sharpe", "profit_factor", "max_drawdown_pct"):
        assert key in m
    assert m["total_trades"] == 0
