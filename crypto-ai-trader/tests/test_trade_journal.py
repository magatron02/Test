"""
F2.3 Trade Journal / Memory — unit tests.

Covers signature bucketing, win-rate / expectancy aggregation, the recall
bias contract (ramp-in, veto), best/worst ranking, and DB hydration.
"""
import pytest

from src.agent.trade_journal import (
    TradeJournal, SetupStats, _conf_band, _signature,
)


# ── Confidence banding ────────────────────────────────────────────────────────

def test_conf_band_boundaries():
    assert _conf_band(0.0)  == "low"
    assert _conf_band(0.59) == "low"
    assert _conf_band(0.60) == "mid"
    assert _conf_band(0.74) == "mid"
    assert _conf_band(0.75) == "high"
    assert _conf_band(0.99) == "high"


def test_signature_is_stable_and_readable():
    sig = _signature("RANGING", "DCA", "high", "OVERSOLD")
    assert sig == "RANGING|DCA|high|OVERSOLD"


# ── SetupStats aggregation ────────────────────────────────────────────────────

def test_setup_stats_winrate_and_expectancy():
    st = SetupStats()
    for pnl in [2.0, -1.0, 3.0, -1.0]:
        st.update(pnl)
    assert st.n == 4
    assert st.wins == 2
    assert st.win_rate == pytest.approx(0.5)
    assert st.avg_pnl == pytest.approx((2 - 1 + 3 - 1) / 4)
    assert st.expectancy == pytest.approx(0.75)


def test_setup_stats_recent_cap():
    st = SetupStats()
    for i in range(30):
        st.update(float(i), recent_cap=20)
    assert len(st.recent) == 20
    assert st.recent[-1] == 29.0


# ── Recording + recall basics ─────────────────────────────────────────────────

def test_record_then_recall_matches_signature():
    j = TradeJournal(min_samples=5)
    j.record(regime="RANGING", strategy="DCA", confidence=0.70,
             rsi_signal="OVERSOLD", pnl_pct=1.5)
    r = j.recall(regime="RANGING", strategy="DCA", confidence=0.70,
                 rsi_signal="OVERSOLD")
    assert r["n"] == 1
    assert r["win_rate"] == 1.0
    assert r["avg_pnl"] == pytest.approx(1.5)


def test_recall_unknown_setup_is_neutral():
    j = TradeJournal()
    r = j.recall(regime="BULL_TREND", strategy="MOMENTUM",
                 confidence=0.8, rsi_signal="NEUTRAL")
    assert r["n"] == 0
    assert r["bias"] == 0.0
    assert r["confident"] is False
    assert r["veto"] is False


def test_confidence_band_groups_trades():
    """0.70 and 0.72 are both 'mid' → same signature → merged stats."""
    j = TradeJournal()
    j.record(regime="RANGING", strategy="DCA", confidence=0.70,
             rsi_signal="OVERSOLD", pnl_pct=1.0)
    j.record(regime="RANGING", strategy="DCA", confidence=0.72,
             rsi_signal="OVERSOLD", pnl_pct=3.0)
    r = j.recall(regime="RANGING", strategy="DCA", confidence=0.71,
                 rsi_signal="OVERSOLD")
    assert r["n"] == 2
    assert r["avg_pnl"] == pytest.approx(2.0)


# ── Bias contract ─────────────────────────────────────────────────────────────

def test_bias_positive_for_winning_setup():
    j = TradeJournal(min_samples=5)
    for _ in range(10):
        j.record(regime="BULL_TREND", strategy="MOMENTUM", confidence=0.8,
                 rsi_signal="NEUTRAL", pnl_pct=2.0)
    r = j.recall(regime="BULL_TREND", strategy="MOMENTUM",
                 confidence=0.8, rsi_signal="NEUTRAL")
    assert r["confident"] is True
    assert r["bias"] > 0.5          # all winners → strong positive
    assert r["veto"] is False


def test_bias_negative_and_veto_for_losing_setup():
    j = TradeJournal(min_samples=5)
    for _ in range(8):
        j.record(regime="VOLATILE", strategy="DCA", confidence=0.65,
                 rsi_signal="OVERBOUGHT", pnl_pct=-2.0)
    r = j.recall(regime="VOLATILE", strategy="DCA",
                 confidence=0.65, rsi_signal="OVERBOUGHT")
    assert r["confident"] is True
    assert r["bias"] < 0
    assert r["veto"] is True         # confident + losing → veto


def test_bias_ramps_in_below_min_samples():
    """With fewer than min_samples trades, |bias| is damped."""
    j = TradeJournal(min_samples=10)
    for _ in range(2):              # only 2 of 10 samples
        j.record(regime="RANGING", strategy="DCA", confidence=0.8,
                 rsi_signal="OVERSOLD", pnl_pct=2.0)
    r = j.recall(regime="RANGING", strategy="DCA",
                 confidence=0.8, rsi_signal="OVERSOLD")
    assert r["confident"] is False
    # full edge would be 1.0 (all wins); ramp = 2/10 → 0.2
    assert r["bias"] == pytest.approx(0.2, abs=1e-6)


def test_no_veto_until_confident():
    """A single loss must not veto the whole setup."""
    j = TradeJournal(min_samples=5)
    j.record(regime="VOLATILE", strategy="DCA", confidence=0.65,
             rsi_signal="OVERBOUGHT", pnl_pct=-2.0)
    r = j.recall(regime="VOLATILE", strategy="DCA",
                 confidence=0.65, rsi_signal="OVERBOUGHT")
    assert r["veto"] is False
    assert r["confident"] is False


# ── Ranking ───────────────────────────────────────────────────────────────────

def test_best_and_worst_setups():
    j = TradeJournal(min_samples=3)
    for _ in range(3):
        j.record(regime="BULL_TREND", strategy="MOMENTUM", confidence=0.8,
                 rsi_signal="NEUTRAL", pnl_pct=3.0)   # winner
    for _ in range(3):
        j.record(regime="VOLATILE", strategy="DCA", confidence=0.6,
                 rsi_signal="OVERBOUGHT", pnl_pct=-2.0)  # loser
    best = j.best_setups(top=1)
    worst = j.worst_setups(top=1)
    assert best[0]["expectancy"] == pytest.approx(3.0)
    assert worst[0]["expectancy"] == pytest.approx(-2.0)
    assert "BULL_TREND" in best[0]["signature"]
    assert "VOLATILE" in worst[0]["signature"]


def test_ranking_filters_low_sample_setups():
    j = TradeJournal(min_samples=5)
    j.record(regime="RANGING", strategy="DCA", confidence=0.7,
             rsi_signal="OVERSOLD", pnl_pct=99.0)   # only 1 sample
    assert j.best_setups() == []                    # filtered out


# ── Summary ───────────────────────────────────────────────────────────────────

def test_summary_shape():
    j = TradeJournal(min_samples=2)
    for _ in range(3):
        j.record(regime="RANGING", strategy="DCA", confidence=0.7,
                 rsi_signal="OVERSOLD", pnl_pct=1.0)
    s = j.summary()
    assert s["total_trades"] == 3
    assert s["distinct_setups"] == 1
    assert s["confident_setups"] == 1
    assert s["overall_win_rate"] == pytest.approx(1.0)
    assert "best" in s and "worst" in s


# ── DB hydration ──────────────────────────────────────────────────────────────

# load_from_db selects column tuples: (strategy, confidence, pnl_pct, indicators)

class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows
    def filter(self, *a, **k):   return self
    def order_by(self, *a, **k): return self
    def limit(self, *a, **k):    return self
    def all(self):               return self._rows


class _FakeSession:
    def __init__(self, rows):
        self._rows = rows
    def query(self, *cols):  return _FakeQuery(self._rows)
    def close(self):         pass


# Model stand-in exposing the column objects referenced in the query
class _Model:
    strategy   = object()
    confidence = object()
    pnl_pct    = type("C", (), {"isnot": staticmethod(lambda x: True)})()
    indicators = object()
    status     = type("C", (), {"__eq__": lambda s, o: True})()
    closed_at  = type("C", (), {"asc": staticmethod(lambda: None)})()


def test_load_from_db_hydrates_memory():
    rows = [
        ("DCA", 0.7, 2.0,  {"regime": "RANGING", "rsi_signal": "OVERSOLD"}),
        ("DCA", 0.7, -1.0, {"regime": "RANGING", "rsi_signal": "OVERSOLD"}),
    ]
    j = TradeJournal(min_samples=2)
    loaded = j.load_from_db(lambda: _FakeSession(rows), _Model)
    assert loaded == 2
    r = j.recall(regime="RANGING", strategy="DCA",
                 confidence=0.7, rsi_signal="OVERSOLD")
    assert r["n"] == 2
    assert r["win_rate"] == pytest.approx(0.5)


def test_load_from_db_handles_missing_indicators():
    rows = [("DCA", 0.7, 1.0, None)]
    j = TradeJournal()
    loaded = j.load_from_db(lambda: _FakeSession(rows), _Model)
    assert loaded == 1
    # falls back to UNKNOWN regime / NEUTRAL rsi
    r = j.recall(regime="UNKNOWN", strategy="DCA",
                 confidence=0.7, rsi_signal="NEUTRAL")
    assert r["n"] == 1
