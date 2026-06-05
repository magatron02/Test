"""Tests for src/data/sentiment.py derivatives_bias (F1.4)."""
from src.data.sentiment import derivatives_bias


def test_crowded_longs_are_contrarian_bearish():
    # Very high long/short ratio + stretched positive funding → bearish lean
    label, score = derivatives_bias(
        long_short_ratio=2.5, taker_buy_sell_ratio=1.0,
        oi_change_pct=0.0, funding_rate=0.0008,
    )
    assert score < 0
    assert label in ("CAUTIOUS_SELL", "CONTRARIAN_SELL")


def test_crowded_shorts_are_contrarian_bullish():
    label, score = derivatives_bias(
        long_short_ratio=0.45, taker_buy_sell_ratio=1.0,
        oi_change_pct=0.0, funding_rate=-0.0008,
    )
    assert score > 0
    assert label in ("CAUTIOUS_BUY", "CONTRARIAN_BUY")


def test_neutral_when_balanced():
    label, score = derivatives_bias(
        long_short_ratio=1.0, taker_buy_sell_ratio=1.0,
        oi_change_pct=0.0, funding_rate=0.0,
    )
    assert label == "NEUTRAL"
    assert score == 0.0


def test_none_inputs_are_neutral():
    label, score = derivatives_bias(None, None, None, None)
    assert label == "NEUTRAL"
    assert score == 0.0


def test_rising_oi_amplifies_existing_lean():
    base = derivatives_bias(2.5, 1.0, 0.0, 0.0)[1]
    amplified = derivatives_bias(2.5, 1.0, 0.10, 0.0)[1]
    # Same bearish lean, but rising OI makes the magnitude larger
    assert abs(amplified) >= abs(base)


def test_score_is_clamped():
    label, score = derivatives_bias(
        long_short_ratio=5.0, taker_buy_sell_ratio=0.5,
        oi_change_pct=0.5, funding_rate=0.01,
    )
    assert -1.0 <= score <= 1.0


def test_taker_buying_is_bullish():
    _, with_buy = derivatives_bias(1.0, 1.5, 0.0, 0.0)
    _, with_sell = derivatives_bias(1.0, 0.5, 0.0, 0.0)
    assert with_buy > with_sell
