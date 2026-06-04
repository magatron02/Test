"""
v1.4.0 Release gate — crash scenario test.

"simulate -30% in one day → circuit breaker + VaR work correctly"

Tests that the risk-management stack stays standing across three failure modes:
  1. Standard −30% equity-crash → drawdown circuit
  2. Sustained negative-return streak → VaR circuit (F3.3)
  3. Monte Carlo ruin probability breach → Monte-Carlo circuit (F3.3)
"""
import numpy as np
import pytest

from src.agent.risk_engine import RiskEngine


# ── helpers ───────────────────────────────────────────────────────────────────

def _engine(cfg: dict = None) -> RiskEngine:
    base = {"max_drawdown_pct": 0.10, "max_daily_loss_pct": 0.05,
            "max_var_pct": 0.04, "max_prob_ruin": 0.35}
    base.update(cfg or {})
    return RiskEngine(config=base)


def _feed(engine: RiskEngine, equity_series: list, regime: str = "RANGING"):
    """Drive the engine through a sequence of daily equity values."""
    for eq in equity_series:
        daily_pnl = eq - equity_series[0]
        engine.update(eq, daily_pnl, {}, regime)


# ── 1. Standard −30% crash trips drawdown circuit ────────────────────────────

def test_crash_30pct_trips_drawdown_circuit():
    eng = _engine()
    eng.update(1_000, 0, {})          # baseline
    eng.update(700, -300, {}, "CRASH")   # −30%
    assert eng.state.circuit_open
    assert "drawdown" in eng.state.circuit_reason.lower()


def test_crash_below_threshold_does_not_trip():
    # Raise both drawdown AND daily-loss limits so only the drawdown gate matters
    eng = _engine({"max_drawdown_pct": 0.50, "max_daily_loss_pct": 0.99})
    eng.update(1_000, 0, {})
    eng.update(700, -300, {}, "CRASH")   # −30% < 50% drawdown limit
    assert not eng.state.circuit_open


def test_crash_summary_has_tail_risk_keys():
    eng = _engine()
    eng.update(1_000, 0, {})
    eng.update(700, -300, {}, "CRASH")
    s = eng.summary()
    assert "tail_risk" in s
    assert "circuit_open" in s
    assert "limits" in s
    assert s["limits"]["max_drawdown_pct"] == pytest.approx(0.10)


# ── 2. Daily-loss circuit ─────────────────────────────────────────────────────

def test_daily_loss_limit_trips_circuit():
    eng = _engine()
    eng.update(1_000, -60, {})   # −6% daily loss, limit is 5%
    assert eng.state.circuit_open
    assert "daily" in eng.state.circuit_reason.lower()


def test_circuit_resets_on_recovery():
    eng = _engine()
    eng.update(1_000, -60, {})    # trips
    assert eng.state.circuit_open
    eng.update(1_100, 0, {})      # new high-water, no loss
    assert not eng.state.circuit_open


# ── 3. VaR circuit (F3.3) — requires history ─────────────────────────────────

def test_var_circuit_trips_on_extreme_returns():
    """
    Feed 25 days of −3% returns; 95% VaR should exceed a tight 2% limit.
    The VaR circuit gate needs ≥ 20 observations.
    Pass daily_pnl=0 so the daily-loss gate stays quiet while we isolate VaR.
    """
    eng = _engine({"max_var_pct": 0.02, "max_drawdown_pct": 0.99,
                   "max_daily_loss_pct": 0.99})
    equity = 1_000.0
    for _ in range(25):
        equity *= 0.97   # −3% per day
        eng.update(equity, 0, {})   # daily_pnl=0 to isolate VaR gate
    assert eng.state.circuit_open
    assert "VaR" in eng.state.circuit_reason or "var" in eng.state.circuit_reason.lower()


def test_var_circuit_not_triggered_with_positive_returns():
    """Healthy equity curve must not trigger the VaR gate."""
    eng = _engine({"max_var_pct": 0.05})
    equity = 1_000.0
    for _ in range(30):
        equity *= 1.002   # +0.2% per day
        eng.update(equity, equity - 1_000, {})
    assert not eng.state.circuit_open


def test_var_circuit_needs_min_20_observations():
    """VaR gate must be skipped when there are fewer than 20 data-points."""
    eng = _engine({"max_var_pct": 0.001,   # impossibly tight limit
                   "max_drawdown_pct": 0.99,
                   "max_daily_loss_pct": 0.99})
    # Feed only 10 observations — VaR gate should not fire
    equity = 1_000.0
    for _ in range(10):
        equity *= 0.97
        eng.update(equity, equity - 1_000, {})
    assert not eng.state.circuit_open   # too few obs → gate skipped


# ── 4. Monte Carlo ruin circuit (F3.3) ───────────────────────────────────────

def test_prob_ruin_circuit_triggers():
    """
    A −5% daily crash sequence should drive prob_ruin well above the 10% limit
    once 20+ observations are in.  daily_pnl=0 isolates the ruin gate.
    """
    eng = _engine({"max_prob_ruin": 0.10,
                   "max_var_pct":   0.99,        # disable VaR gate
                   "max_drawdown_pct": 0.99,
                   "max_daily_loss_pct": 0.99})
    equity = 1_000.0
    for _ in range(30):
        equity *= 0.95   # −5% per day
        eng.update(equity, 0, {})   # daily_pnl=0 to isolate ruin gate
    assert eng.state.circuit_open
    assert "ruin" in eng.state.circuit_reason.lower() or "Monte Carlo" in eng.state.circuit_reason


# ── 5. Integration: full −30% crash scenario (gate test) ─────────────────────

def test_full_crash_gate():
    """
    End-to-end simulation of a −30% single-day shock:
      - History: 25 days of small gains
      - Shock:   one −30% day
    Verifies that at least one circuit fires and the summary is consistent.
    """
    eng = _engine()
    equity = 10_000.0
    rng = np.random.default_rng(0)
    for _ in range(25):
        equity *= 1 + rng.normal(0.001, 0.005)   # gentle uptrend
        eng.update(equity, equity - 10_000, {})

    # Crash day
    equity *= 0.70   # −30%
    eng.update(equity, equity - 10_000, {}, "CRASH")

    assert eng.state.circuit_open, "At least one circuit must fire after −30% shock"
    s = eng.summary()
    assert s["drawdown_pct"] >= 0.29   # approximately −30%
    assert s["tail_risk"].get("var_pct", 0.0) >= 0.0
