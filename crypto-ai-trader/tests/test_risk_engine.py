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


# ── F2.4 Adaptive meta-parameters ────────────────────────────────────────────

def test_adaptive_adjust_no_op_below_min_obs():
    """Returns 1.0 and doesn't change limits when fewer than 10 observations."""
    re = RiskEngine({"max_drawdown_pct": 0.10, "max_var_pct": 0.05})
    re.update(10_000.0, 0, {})   # only 1 return observation after 2 updates
    re.update(10_100.0, 0, {})
    mult = re.adaptive_adjust()
    assert mult == 1.0
    assert re._max_drawdown_pct == pytest.approx(0.10)
    assert re._max_var_pct      == pytest.approx(0.05)


def test_adaptive_adjust_tightens_on_high_vol():
    """High daily vol drives the multiplier to < 1.0, tightening all limits."""
    import numpy as np
    re = RiskEngine({"max_drawdown_pct": 0.10, "max_var_pct": 0.05,
                     "max_daily_loss_pct": 0.05})
    # Inject a deliberately-volatile return series via _daily_returns
    rng = np.random.default_rng(0)
    # Large daily swings → annualised vol >> base_var_pct (0.05)
    re._daily_returns = list(rng.normal(0, 0.08, 30))   # ~8% daily std
    mult = re.adaptive_adjust()
    assert mult < 1.0, "high-vol regime should tighten limits (mult < 1)"
    assert re._max_drawdown_pct   < 0.10
    assert re._max_var_pct        < 0.05
    assert re._max_daily_loss_pct < 0.05


def test_adaptive_adjust_loosens_on_calm_vol():
    """Very calm vol drives multiplier to > 1.0, loosening all limits slightly."""
    import numpy as np
    re = RiskEngine({"max_drawdown_pct": 0.10, "max_var_pct": 0.05,
                     "max_daily_loss_pct": 0.05})
    # Tiny daily moves → annualised vol << base_var_pct
    re._daily_returns = list(np.random.default_rng(1).normal(0, 0.001, 20))
    mult = re.adaptive_adjust()
    assert mult > 1.0, "calm regime should loosen limits slightly (mult > 1)"
    assert re._max_drawdown_pct   > 0.10
    assert re._max_var_pct        > 0.05


def test_adaptive_adjust_anchors_to_base():
    """Repeated calls never drift the limits below the original base × min_mult."""
    import numpy as np
    re = RiskEngine({"max_drawdown_pct": 0.10, "max_var_pct": 0.05})
    rng = np.random.default_rng(2)
    re._daily_returns = list(rng.normal(0, 0.10, 30))   # extreme vol
    for _ in range(5):
        re.adaptive_adjust()
    # Must never go below base × 0.50 (the hardest tightening step)
    assert re._max_drawdown_pct >= 0.10 * 0.50
    assert re._max_var_pct      >= 0.05 * 0.50


def test_adaptive_mult_in_summary():
    """summary() must include the adaptive_mult key."""
    re = RiskEngine()
    re.update(10_000.0, 0, {})
    s = re.summary()
    assert "adaptive_mult" in s


import pytest
