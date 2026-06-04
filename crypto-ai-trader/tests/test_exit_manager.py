"""Tests for ExitManager (F2.2 Adaptive Dynamic SL/TP)."""
import pytest
from src.agent.exit_manager import ExitManager


@pytest.fixture
def em():
    return ExitManager()


# ── compute_exits ─────────────────────────────────────────────────────────────

def test_bull_trend_wider_than_ranging(em):
    bull = em.compute_exits(50000, 1.5, "BULL_TREND")
    rang = em.compute_exits(50000, 1.5, "RANGING")
    # BULL_TREND uses k_sl=2.0 vs RANGING k_sl=1.5 → wider SL
    assert bull["sl_pct"] > rang["sl_pct"]


def test_bull_trend_better_rr_than_volatile(em):
    bull = em.compute_exits(50000, 1.5, "BULL_TREND")
    vol  = em.compute_exits(50000, 1.5, "VOLATILE")
    # BULL R:R = 3.0, VOLATILE = 1.5 → TP/SL ratio higher in bull
    bull_rr = bull["tp_pct"] / bull["sl_pct"]
    vol_rr  = vol["tp_pct"]  / vol["sl_pct"]
    assert bull_rr > vol_rr


def test_crash_tightest_sl(em):
    crash = em.compute_exits(50000, 1.5, "CRASH")
    bull  = em.compute_exits(50000, 1.5, "BULL_TREND")
    assert crash["sl_pct"] < bull["sl_pct"]


def test_minimum_sl_enforced(em):
    # Very low ATR should not produce SL tighter than _MIN_SL_PCT=0.005
    exits = em.compute_exits(100.0, 0.01, "RANGING")
    assert exits["sl_pct"] >= 0.005


def test_minimum_tp_enforced(em):
    exits = em.compute_exits(100.0, 0.01, "CRASH")
    assert exits["tp_pct"] >= 0.01


def test_unknown_regime_uses_defaults(em):
    exits = em.compute_exits(50000, 1.5, "UNKNOWN_REGIME")
    assert exits["sl_pct"] > 0
    assert exits["tp_pct"] > exits["sl_pct"]


# ── attach_exits ──────────────────────────────────────────────────────────────

def test_attach_overwrites_fixed_levels(em):
    trade = {
        "symbol": "BTC/USDT",
        "stop_loss_price":   48500.0,  # old fixed 3%
        "take_profit_price": 53000.0,  # old fixed 6%
    }
    em.attach_exits(trade, 50000.0, 1.5, "RANGING")
    # Should now reflect ATR-based levels, not the original fixed ones
    assert trade["stop_loss_price"]   != 48500.0
    assert trade["take_profit_price"] != 53000.0
    assert "atr_sl_price" in trade
    assert "atr_tp_price" in trade


def test_attach_sl_below_entry(em):
    trade = {"symbol": "ETH/USDT", "stop_loss_price": 0, "take_profit_price": 0}
    em.attach_exits(trade, 3000.0, 2.0, "VOLATILE")
    assert trade["atr_sl_price"] < 3000.0
    assert trade["atr_tp_price"] > 3000.0


# ── check_exit ────────────────────────────────────────────────────────────────

def test_sl_triggers_below_price(em):
    trade = {
        "price":          50000.0,
        "atr_sl_price":   48500.0,
        "atr_tp_price":   53000.0,
        "high_water":     50000.0,
        "atr_trailing_sl": None,
    }
    reason = em.check_exit(trade, 48000.0, 1.5, "RANGING")
    assert reason is not None
    assert "SL" in reason


def test_tp_triggers_above_price(em):
    trade = {
        "price":          50000.0,
        "atr_sl_price":   48500.0,
        "atr_tp_price":   53000.0,
        "high_water":     53100.0,
        "atr_trailing_sl": None,
    }
    reason = em.check_exit(trade, 53100.0, 1.5, "RANGING")
    assert reason is not None
    assert "TP" in reason


def test_no_exit_in_middle(em):
    trade = {
        "price":          50000.0,
        "atr_sl_price":   48500.0,
        "atr_tp_price":   53000.0,
        "high_water":     50000.0,
        "atr_trailing_sl": None,
    }
    reason = em.check_exit(trade, 51000.0, 1.5, "RANGING")
    assert reason is None


def test_trailing_stop_activates_and_triggers(em):
    # BULL_TREND: trail activates at profit >= 1.0 × atr_pct/100
    # atr_pct=2.0 → activate at 2% profit. entry=50000 → activates at >=51000
    trade = {
        "price":           50000.0,
        "atr_sl_price":    49000.0,
        "atr_tp_price":    54000.0,
        "high_water":      50000.0,
        "atr_trailing_sl": None,
    }
    # Price rises 3% → trail should be set
    em.check_exit(trade, 51500.0, 2.0, "BULL_TREND")
    assert trade["atr_trailing_sl"] is not None

    # Now price drops back through trail
    reason = em.check_exit(trade, trade["atr_trailing_sl"] - 1.0, 2.0, "BULL_TREND")
    assert reason is not None
    assert "trail" in reason
