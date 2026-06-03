"""Tests for src/agent/position_sizer.py PositionSizer."""
from src.agent.market_analyzer import MarketAnalysis
from src.agent.position_sizer import PositionSizer


def _analysis(atr_pct=2.0, vol_ratio=1.0):
    a = MarketAnalysis(symbol="BTC/USDT", price=100.0, change_24h=0.0)
    a.atr_pct = atr_pct
    a.garch_vol_ratio = vol_ratio
    return a


def test_cold_start_positive_fraction():
    ps = PositionSizer()
    # No history -> Bayesian prior gives a positive Kelly fraction
    frac = ps._kelly_fraction_for("BTC/USDT")
    assert frac > 0.0


def test_kelly_increases_after_wins_vs_losses():
    winner = PositionSizer()
    loser = PositionSizer()
    for _ in range(8):
        winner.update_outcome("BTC/USDT", pnl_pct=4.0)
        loser.update_outcome("BTC/USDT", pnl_pct=-3.0)

    win_kelly = winner._kelly_fraction_for("BTC/USDT")
    loss_kelly = loser._kelly_fraction_for("BTC/USDT")

    assert win_kelly > loss_kelly
    # Winning streak should also beat the cold-start prior
    cold = PositionSizer()._kelly_fraction_for("BTC/USDT")
    assert win_kelly > cold


def test_compute_respects_portfolio_and_cash_caps():
    ps = PositionSizer()
    # warm it up to a high win rate so Kelly is large and caps bind
    for _ in range(20):
        ps.update_outcome("BTC/USDT", pnl_pct=10.0)

    portfolio = 10_000.0
    max_pct = 0.10
    available_cash = 500.0  # deliberately small to exercise the cash guard

    size = ps.compute(
        symbol="BTC/USDT",
        portfolio_value=portfolio,
        analysis=_analysis(),
        available_cash=available_cash,
        regime="BULL_TREND",
        regime_multiplier=1.0,
        max_position_pct=max_pct,
    )

    assert size <= portfolio * max_pct + 1e-6
    assert size <= available_cash * 0.95 + 1e-6
    assert size >= 0.0


def test_compute_portfolio_cap_when_cash_abundant():
    ps = PositionSizer()
    for _ in range(20):
        ps.update_outcome("BTC/USDT", pnl_pct=10.0)
    portfolio = 10_000.0
    max_pct = 0.10
    size = ps.compute(
        symbol="BTC/USDT",
        portfolio_value=portfolio,
        analysis=_analysis(),
        available_cash=1_000_000.0,  # cash not a constraint
        regime="BULL_TREND",
        regime_multiplier=1.0,
        max_position_pct=max_pct,
    )
    assert size <= portfolio * max_pct + 1e-6


def test_is_tradeable_respects_min_trade_usdt():
    ps = PositionSizer({"min_trade_usdt": 10.0})
    assert ps.is_tradeable(15.0) is True
    assert ps.is_tradeable(5.0) is False
    assert ps.is_tradeable(10.0) is True
