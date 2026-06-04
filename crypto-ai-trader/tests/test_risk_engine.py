"""Tests for src/agent/risk_engine.py RiskEngine."""
from src.agent.risk_engine import RiskEngine


def test_circuit_breaker_opens_on_drawdown():
    re = RiskEngine({"max_drawdown_pct": 0.10})
    # Establish a high-water mark, then drop 15% below it.
    re.update(equity=10_000.0, daily_pnl=0.0, open_trades={}, regime="RANGING")
    re.update(equity=8_500.0, daily_pnl=0.0, open_trades={}, regime="RANGING")

    assert re.state.circuit_open is True
    allowed, reason = re.can_trade(new_trade_risk=0.0)
    assert allowed is False
    assert "Circuit breaker" in reason


def test_circuit_breaker_opens_on_daily_loss():
    re = RiskEngine({"max_drawdown_pct": 0.99, "max_daily_loss_pct": 0.05})
    # No drawdown (equity == HWM) but a large daily loss.
    re.update(equity=10_000.0, daily_pnl=-800.0, open_trades={}, regime="RANGING")

    assert re.state.circuit_open is True
    allowed, _ = re.can_trade()
    assert allowed is False


def test_can_trade_blocks_excess_portfolio_heat():
    re = RiskEngine({"max_portfolio_heat": 0.20, "max_drawdown_pct": 0.99})
    re.update(equity=10_000.0, daily_pnl=0.0, open_trades={}, regime="RANGING")

    # Existing open risk = 15% of equity.
    re.register_open_trade("BTC/USDT", 1_500.0)

    # Adding another 1000 (10%) would push heat to 25% > 20% cap.
    allowed, reason = re.can_trade(new_trade_risk=1_000.0)
    assert allowed is False
    assert "heat" in reason.lower()

    # A small extra risk stays under the cap.
    allowed_small, _ = re.can_trade(new_trade_risk=100.0)
    assert allowed_small is True


def test_regime_multiplier_ordering():
    re = RiskEngine()
    bull = re.get_regime_multiplier("BULL_TREND")
    volatile = re.get_regime_multiplier("VOLATILE")
    crash = re.get_regime_multiplier("CRASH")

    assert crash < bull
    assert volatile < bull
    # unknown regime falls back to a sane default
    assert 0.0 < re.get_regime_multiplier("UNKNOWN") <= 1.0
