"""Tests for the incremental analysis cache + market narrative."""
from src.agent.signal_cache import SignalCache
from src.agent.narrative import build_narrative
from src.agent.market_analyzer import MarketAnalysis
from src.agent.strategy_manager import TradingSignal


class _Regime:
    def __init__(self, regime="BULL_TREND", confidence=0.7):
        self.regime = regime
        self.confidence = confidence


def _analysis(price=100.0, **overrides):
    base = dict(
        symbol="BTC/USDT", price=price, change_24h=1.0,
        rsi=58.0, rsi_signal="NEUTRAL", macd_trend="BULLISH",
        ema_trend="BULLISH", bb_signal="NEUTRAL", bb_position=0.55,
        volatility="MEDIUM", price_vs_vwap="ABOVE", volume_signal="NORMAL",
        ichimoku_signal="BULL", supertrend_signal="BUY",
        stoch_rsi_signal="NEUTRAL", rsi_divergence="NONE",
        smc_summary="", overall_signal="BUY",
    )
    base.update(overrides)
    return MarketAnalysis(**base)


def _signal(action="BUY", conf=0.72):
    return TradingSignal(action, conf, "claude", "reasoning", 0.05, 0.10)


# ── SignalCache ──────────────────────────────────────────────────────────────

def test_cache_miss_then_hit():
    c = SignalCache({"enabled": True, "price_threshold_pct": 0.5, "max_age_sec": 1800})
    a, r, s = _analysis(), _Regime(), _signal()
    assert c.get("BTC/USDT", a, r) is None          # nothing cached yet
    c.put("BTC/USDT", a, r, s)
    hit = c.get("BTC/USDT", a, r)
    assert hit is s                                  # same object returned
    assert c.stats["calls_saved"] == 1


def test_cache_busts_on_price_move():
    c = SignalCache({"enabled": True, "price_threshold_pct": 0.5, "max_age_sec": 1800})
    r, s = _Regime(), _signal()
    c.put("BTC/USDT", _analysis(price=100.0), r, s)
    # +1% move exceeds the 0.5% tolerance → miss
    assert c.get("BTC/USDT", _analysis(price=101.0), r) is None
    # within tolerance → hit
    assert c.get("BTC/USDT", _analysis(price=100.2), r) is s


def test_cache_busts_on_signal_change():
    c = SignalCache({"enabled": True, "price_threshold_pct": 0.5, "max_age_sec": 1800})
    r, s = _Regime(), _signal()
    c.put("BTC/USDT", _analysis(macd_trend="BULLISH"), r, s)
    # categorical change → miss even at the same price
    assert c.get("BTC/USDT", _analysis(macd_trend="BEARISH"), r) is None


def test_cache_busts_on_regime_change():
    c = SignalCache({"enabled": True})
    s = _signal()
    c.put("BTC/USDT", _analysis(), _Regime("BULL_TREND"), s)
    assert c.get("BTC/USDT", _analysis(), _Regime("CRASH")) is None


def test_cache_disabled_never_hits():
    c = SignalCache({"enabled": False})
    a, r, s = _analysis(), _Regime(), _signal()
    c.put("BTC/USDT", a, r, s)
    assert c.get("BTC/USDT", a, r) is None


def test_cache_invalidate():
    c = SignalCache({"enabled": True})
    a, r, s = _analysis(), _Regime(), _signal()
    c.put("BTC/USDT", a, r, s)
    c.invalidate("BTC/USDT")
    assert c.get("BTC/USDT", a, r) is None


# ── Narrative ────────────────────────────────────────────────────────────────

def test_narrative_mentions_symbol_and_action():
    text = build_narrative(_analysis(), _Regime("BULL_TREND"), _signal("BUY", 0.72))
    assert "BTC" in text
    assert "ซื้อ" in text          # action rendered in Thai
    assert "72%" in text           # confidence surfaced
    assert "ขาขึ้น" in text        # bull regime phrase


def test_narrative_flags_divergence_and_volume_spike():
    a = _analysis(rsi_divergence="BEARISH", volume_spike=True)
    text = build_narrative(a, _Regime("VOLATILE"), _signal("HOLD", 0.3))
    assert "divergence" in text
    assert "วอลุ่มพุ่งผิดปกติ" in text


def test_narrative_unknown_regime_safe():
    text = build_narrative(_analysis(), _Regime(""), _signal("HOLD", 0.5))
    assert isinstance(text, str) and text          # never empty / never raises
