"""Correlation guard + correlation matrix (risk_engine + AITrader)."""
from src.agent.risk_engine import RiskEngine
from src.agent.ai_trader import AITrader


class _FakeExchange:
    name = "demo"
    is_demo = True
    quote_currency = "USDT"


# A deterministic return series and a correlated / independent counterpart
_BASE = [0.01, -0.02, 0.03, -0.01, 0.02, 0.0, 0.015, -0.005]
_CORR = [x * 1.01 for x in _BASE]              # ~perfectly correlated
_INDEP = [0.02, 0.01, -0.03, 0.025, -0.02, 0.005, -0.01, 0.03]


def _prices_from_returns(rets, start=100.0):
    """Rebuild a close-price series so _returns_for() reproduces the returns."""
    closes = [start]
    for r in rets:
        closes.append(closes[-1] * (1 + r))
    return closes


# ── RiskEngine.check_correlation ─────────────────────────────────────────────

def test_pearson_identical_is_one():
    re = RiskEngine({})
    assert round(re._pearson(_BASE, _BASE), 3) == 1.0


def test_guard_blocks_highly_correlated():
    re = RiskEngine({"max_correlation": 0.8, "correlation_guard_enabled": True})
    allowed, reason, avg = re.check_correlation(_BASE, {"ETH/USDT": _CORR})
    assert allowed is False
    assert avg is not None and avg > 0.8
    assert "Correlation" in reason


def test_guard_allows_independent():
    re = RiskEngine({"max_correlation": 0.8, "correlation_guard_enabled": True})
    allowed, _, avg = re.check_correlation(_BASE, {"ETH/USDT": _INDEP})
    assert allowed is True
    assert avg is not None and avg <= 0.8


def test_guard_disabled_always_allows():
    re = RiskEngine({"correlation_guard_enabled": False})
    allowed, _, _ = re.check_correlation(_BASE, {"ETH/USDT": _CORR})
    assert allowed is True


def test_guard_allows_when_no_held_positions():
    re = RiskEngine({"correlation_guard_enabled": True})
    assert re.check_correlation(_BASE, {})[0] is True


# ── AITrader correlation wiring ──────────────────────────────────────────────

def test_trader_correlation_guard_blocks():
    trader = AITrader(_FakeExchange())
    trader._price_history = {
        "BTC/USDT": _prices_from_returns(_BASE),
        "ETH/USDT": _prices_from_returns(_CORR),
    }
    trader._open_trades = {"ETH/USDT": {"price": 1.0}}
    ok, reason = trader._check_correlation_guard("BTC/USDT")
    assert ok is False and "Correlation" in reason


def test_trader_correlation_guard_allows_independent():
    trader = AITrader(_FakeExchange())
    trader._price_history = {
        "BTC/USDT": _prices_from_returns(_BASE),
        "XRP/USDT": _prices_from_returns(_INDEP),
    }
    trader._open_trades = {"XRP/USDT": {"price": 1.0}}
    ok, _ = trader._check_correlation_guard("BTC/USDT")
    assert ok is True


def test_correlation_matrix_shape_and_diagonal():
    trader = AITrader(_FakeExchange())
    trader._price_history = {
        "BTC/USDT": _prices_from_returns(_BASE),
        "ETH/USDT": _prices_from_returns(_CORR),
        "XRP/USDT": _prices_from_returns(_INDEP),
    }
    out = trader.correlation_matrix()
    syms, m = out["symbols"], out["matrix"]
    assert len(syms) == 3
    assert len(m) == 3 and all(len(row) == 3 for row in m)
    for i in range(3):
        assert m[i][i] == 1.0           # self-correlation on the diagonal
    # BTC vs ETH (correlated) should read high
    i, j = syms.index("BTC/USDT"), syms.index("ETH/USDT")
    assert m[i][j] is not None and m[i][j] > 0.8
