"""run_cycle() Phase A — concurrent, resilient symbol analysis."""
import asyncio

import pytest

from src.agent.ai_trader import AITrader
from src.agent.market_analyzer import MarketAnalysis
from src.agent.strategy_manager import TradingSignal
from src.core.config import settings


class _FakeExchange:
    name = "demo"
    is_demo = True
    quote_currency = "USDT"


class _Regime:
    regime = "RANGING"
    confidence = 0.5
    adx = 20.0


@pytest.mark.asyncio
async def test_run_cycle_analyzes_symbols_concurrently_and_survives_failures(monkeypatch):
    trader = AITrader(_FakeExchange())

    orig_symbols = settings.get("trading", "symbols")
    settings.set(["A/USDT", "B/USDT", "C/USDT"], "trading", "symbols")
    try:
        live = 0
        peak = 0
        analyzed = []

        async def fake_analyze(sym):
            nonlocal live, peak
            live += 1
            peak = max(peak, live)
            await asyncio.sleep(0.02)      # force overlap if run concurrently
            live -= 1
            if sym == "B/USDT":
                raise RuntimeError("simulated analysis failure")
            analyzed.append(sym)
            trader._regimes[sym] = _Regime()
            return MarketAnalysis(symbol=sym, price=100.0, change_24h=1.0)

        async def anoop(*a, **k):
            return None

        async def fake_portfolio(*a, **k):
            return {"total_value": 1000, "available_usdt": 1000,
                    "cash_usdt": 1000, "open_positions": 0}

        async def fake_signal(*a, **k):
            return TradingSignal("HOLD", 0.5, "rule", "x", 0.03, 0.06)

        captured = []

        async def fake_broadcast(event, data):
            captured.append((event, data))

        async def fake_dash():
            return {}

        monkeypatch.setattr(trader, "analyze_symbol", fake_analyze)
        monkeypatch.setattr(trader, "_check_exit_conditions", anoop)
        monkeypatch.setattr(trader, "_get_portfolio_summary", fake_portfolio)
        monkeypatch.setattr(trader, "_update_risk_engine", anoop)
        monkeypatch.setattr(trader, "_get_final_signal", fake_signal)
        monkeypatch.setattr(trader, "_broadcast", fake_broadcast)
        monkeypatch.setattr(trader, "get_dashboard_state", fake_dash)
        monkeypatch.setattr(trader, "_update_hrp_weights", lambda: None)

        await trader.run_cycle()

        # Ran in parallel, not one-at-a-time
        assert peak >= 2
        # The failing symbol didn't abort the cycle; the others completed
        assert set(analyzed) == {"A/USDT", "C/USDT"}
        updates = [d for e, d in captured if e == "analysis_update"]
        assert {u["symbol"] for u in updates} == {"A/USDT", "C/USDT"}
        assert all("narrative" in u for u in updates)
    finally:
        settings.set(orig_symbols, "trading", "symbols")
