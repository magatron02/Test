"""Tests for src/agent/arbitrage.py — TriangularArbScanner + FundingRateMonitor."""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from src.agent.arbitrage import (
    ArbitrageEngine,
    FundingRateInfo,
    FundingRateMonitor,
    TriangularArbScanner,
    TriangularOpportunity,
    TriLeg,
)
from src.exchanges.base import Order, OrderbookTop


# ── Fixtures ──────────────────────────────────────────────────────────────────

_PRICES = {
    "BTC/USDT": (104999.0, 105001.0),
    "ETH/USDT": (3799.8,   3800.2),
    "ETH/BTC":  (0.036188, 0.036192),
    "BNB/USDT": (679.9,    680.1),
    "BNB/BTC":  (0.006475, 0.006477),
    "SOL/USDT": (174.8,    175.2),
    "SOL/BTC":  (0.001665, 0.001667),
    "XRP/USDT": (2.2990,   2.3010),
    "XRP/BTC":  (0.0000219, 0.0000220),
    "BNB/ETH":  (0.17892,  0.17895),
    "SOL/ETH":  (0.04605,  0.04607),
}


@pytest.fixture
def mock_exchange():
    ex = MagicMock()
    ex.is_demo = True

    async def _ob(sym):
        if sym not in _PRICES:
            return None
        bid, ask = _PRICES[sym]
        return OrderbookTop(sym, bid, ask, round((ask - bid) / bid * 100, 6))

    ex.get_orderbook_top = _ob
    ex.get_funding_rate = AsyncMock(return_value={
        "fundingRate":     0.0001,
        "fundingDatetime": "1749132000000",  # epoch-ms string
    })
    ex.create_order = AsyncMock(return_value=Order(
        id="T1", symbol="X/Y", side="buy", type="market",
        price=100.0, amount=1.0, cost=100.0, status="closed",
    ))
    return ex


# ── TriangularArbScanner: calculation ─────────────────────────────────────────

def test_calc_returns_opportunity(mock_exchange):
    scanner = TriangularArbScanner(mock_exchange, fee_pct=0.001,
                                   min_net_profit_pct=-100.0, max_amount_usdt=100.0)
    legs = [
        TriLeg("BTC/USDT", "BUY",  105001.0),
        TriLeg("ETH/BTC",  "BUY",  0.036192),
        TriLeg("ETH/USDT", "SELL", 3799.8),
    ]
    opp = scanner._calc("USDT→BTC→ETH→USDT", legs)
    assert opp is not None
    assert opp.cycle == "USDT→BTC→ETH→USDT"
    assert isinstance(opp.net_profit_pct, float)
    assert isinstance(opp.gross_profit_pct, float)
    assert opp.gross_profit_pct > opp.net_profit_pct   # fees drag down net


def test_calc_zero_price_returns_none(mock_exchange):
    scanner = TriangularArbScanner(mock_exchange)
    legs = [
        TriLeg("BTC/USDT", "BUY",  0.0),   # zero price → division error
        TriLeg("ETH/BTC",  "BUY",  0.036),
        TriLeg("ETH/USDT", "SELL", 3800.0),
    ]
    assert scanner._calc("test", legs) is None


def test_calc_fee_drag(mock_exchange):
    """3 × 0.1% fee should reduce net profit by ~0.3%."""
    scanner = TriangularArbScanner(mock_exchange, fee_pct=0.001,
                                   min_net_profit_pct=-100.0, max_amount_usdt=100.0)
    # Perfect triangle: prices that give exactly 0% gross profit
    # buy at 1, sell at 1 — net should be approx -(3×fee)
    legs = [
        TriLeg("A/USDT", "BUY",  1.0),
        TriLeg("B/A",    "BUY",  1.0),
        TriLeg("B/USDT", "SELL", 1.0),
    ]
    opp = scanner._calc("USDT→A→B→USDT", legs)
    assert opp is not None
    expected_fee_drag = (1 - (1 - 0.001) ** 3) * 100
    assert abs(opp.net_profit_pct + expected_fee_drag) < 0.001


# ── TriangularArbScanner: scan ────────────────────────────────────────────────

@pytest.mark.anyio
async def test_scan_returns_list(mock_exchange):
    scanner = TriangularArbScanner(mock_exchange, min_net_profit_pct=-100.0)
    opps = await scanner.scan()
    assert isinstance(opps, list)
    assert scanner.stats["scans"] == 1


@pytest.mark.anyio
async def test_scan_sorted_descending(mock_exchange):
    scanner = TriangularArbScanner(mock_exchange, min_net_profit_pct=-100.0)
    opps = await scanner.scan()
    for i in range(len(opps) - 1):
        assert opps[i].net_profit_pct >= opps[i + 1].net_profit_pct


@pytest.mark.anyio
async def test_scan_threshold_filters(mock_exchange):
    """Very high threshold should return no opportunities."""
    scanner = TriangularArbScanner(mock_exchange, min_net_profit_pct=99.0)
    opps = await scanner.scan()
    assert opps == []


@pytest.mark.anyio
async def test_scan_increments_found(mock_exchange):
    scanner = TriangularArbScanner(mock_exchange, min_net_profit_pct=-100.0)
    opps = await scanner.scan()
    if opps:
        assert scanner.stats["found"] > 0


# ── TriangularArbScanner: execute ────────────────────────────────────────────

@pytest.mark.anyio
async def test_execute_dry_run_no_orders(mock_exchange):
    scanner = TriangularArbScanner(mock_exchange, max_amount_usdt=100.0)
    opp = TriangularOpportunity(
        cycle="USDT→BTC→ETH→USDT",
        legs=[
            TriLeg("BTC/USDT", "BUY",  105000.0),
            TriLeg("ETH/BTC",  "BUY",  0.036),
            TriLeg("ETH/USDT", "SELL", 3800.0),
        ],
        gross_profit_pct=0.30, net_profit_pct=0.20, amount_usdt=100.0,
    )
    result = await scanner.execute(opp, available_usdt=500.0, dry_run=True)
    assert result is not None
    assert result["dry_run"] is True
    mock_exchange.create_order.assert_not_called()


@pytest.mark.anyio
async def test_execute_live_three_orders(mock_exchange):
    scanner = TriangularArbScanner(mock_exchange, max_amount_usdt=100.0)
    opp = TriangularOpportunity(
        cycle="USDT→BTC→ETH→USDT",
        legs=[
            TriLeg("BTC/USDT", "BUY",  105000.0),
            TriLeg("ETH/BTC",  "BUY",  0.036),
            TriLeg("ETH/USDT", "SELL", 3800.0),
        ],
        gross_profit_pct=0.30, net_profit_pct=0.20, amount_usdt=100.0,
    )
    await scanner.execute(opp, available_usdt=500.0, dry_run=False)
    assert mock_exchange.create_order.call_count == 3


@pytest.mark.anyio
async def test_execute_no_cash_returns_none(mock_exchange):
    scanner = TriangularArbScanner(mock_exchange, max_amount_usdt=100.0)
    opp = TriangularOpportunity(
        cycle="test",
        legs=[TriLeg("A/USDT", "BUY", 1.0)],
        gross_profit_pct=0.5, net_profit_pct=0.2, amount_usdt=100.0,
    )
    result = await scanner.execute(opp, available_usdt=0.0, dry_run=False)
    assert result is None


# ── FundingRateMonitor ────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_funding_scan_returns_per_symbol(mock_exchange):
    monitor = FundingRateMonitor(mock_exchange)
    results = await monitor.scan(["BTC/USDT", "ETH/USDT"])
    assert len(results) == 2
    assert all(isinstance(r, FundingRateInfo) for r in results)
    assert monitor.stats["scans"] == 1


@pytest.mark.anyio
async def test_funding_annualized_formula(mock_exchange):
    mock_exchange.get_funding_rate = AsyncMock(return_value={"fundingRate": 0.0001})
    monitor = FundingRateMonitor(mock_exchange)
    results = await monitor.scan(["BTC/USDT"])
    expected = round(0.0001 * 3 * 365 * 100, 2)
    assert abs(results[0].annualized_pct - expected) < 0.01


@pytest.mark.anyio
async def test_funding_direction_positive(mock_exchange):
    mock_exchange.get_funding_rate = AsyncMock(return_value={"fundingRate": 0.0002})
    monitor = FundingRateMonitor(mock_exchange)
    r = (await monitor.scan(["BTC/USDT"]))[0]
    assert r.direction == "LONG_SPOT_SHORT_PERP"


@pytest.mark.anyio
async def test_funding_direction_negative(mock_exchange):
    mock_exchange.get_funding_rate = AsyncMock(return_value={"fundingRate": -0.0002})
    monitor = FundingRateMonitor(mock_exchange)
    r = (await monitor.scan(["BTC/USDT"]))[0]
    assert r.direction == "SHORT_SPOT_LONG_PERP"


@pytest.mark.anyio
async def test_funding_viability_flag(mock_exchange):
    mock_exchange.get_funding_rate = AsyncMock(return_value={"fundingRate": 0.001})  # 36.5%/yr
    monitor = FundingRateMonitor(mock_exchange, min_annualized_pct=15.0)
    r = (await monitor.scan(["BTC/USDT"]))[0]
    assert r.arb_viable is True


@pytest.mark.anyio
async def test_funding_not_viable_low_rate(mock_exchange):
    mock_exchange.get_funding_rate = AsyncMock(return_value={"fundingRate": 0.00005})  # 5.5%/yr
    monitor = FundingRateMonitor(mock_exchange, min_annualized_pct=15.0)
    r = (await monitor.scan(["BTC/USDT"]))[0]
    assert r.arb_viable is False


@pytest.mark.anyio
async def test_funding_sorted_descending(mock_exchange):
    rates = {"BTC/USDT": 0.001, "ETH/USDT": 0.0005}

    async def _get_rate(sym):
        return {"fundingRate": rates[sym]}

    mock_exchange.get_funding_rate = _get_rate
    monitor = FundingRateMonitor(mock_exchange)
    results = await monitor.scan(["BTC/USDT", "ETH/USDT"])
    assert results[0].annualized_pct >= results[1].annualized_pct


# ── ArbitrageEngine ───────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_engine_run_cycle_structure(mock_exchange):
    engine = ArbitrageEngine(mock_exchange,
                             {"min_profit_pct": -100.0}, dry_run=True)
    result = await engine.run_cycle(["BTC/USDT", "ETH/USDT"],
                                    available_usdt=1000.0)
    assert "tri_opportunities" in result
    assert "funding_rates" in result
    assert "executed" in result
    assert isinstance(result["tri_opportunities"], list)
    assert isinstance(result["funding_rates"], list)


@pytest.mark.anyio
async def test_engine_no_exec_below_min_cash(mock_exchange):
    engine = ArbitrageEngine(mock_exchange,
                             {"min_profit_pct": -100.0}, dry_run=False)
    result = await engine.run_cycle(["BTC/USDT"], available_usdt=5.0)
    assert result["executed"] == []


@pytest.mark.anyio
async def test_engine_full_stats(mock_exchange):
    engine = ArbitrageEngine(mock_exchange, dry_run=True)
    await engine.run_cycle(["BTC/USDT"], available_usdt=500.0)
    stats = engine.full_stats()
    assert "triangular" in stats
    assert "funding" in stats
    assert stats["triangular"]["scans"] == 1
    assert stats["funding"]["scans"] == 1
