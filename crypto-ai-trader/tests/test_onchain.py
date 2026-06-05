"""Tests for on-chain metrics bias scoring (F1.1)."""
from src.data.onchain import onchain_bias


def test_growing_addresses_and_txcount_bullish():
    label, score = onchain_bias(0.06, 0.12)
    assert score > 0
    assert "BULLISH" in label


def test_shrinking_network_bearish():
    label, score = onchain_bias(-0.06, -0.12)
    assert score < 0
    assert "BEARISH" in label


def test_neutral_when_all_none():
    label, score = onchain_bias(None, None)
    assert label == "NEUTRAL"
    assert score == 0.0


def test_neutral_when_small_changes():
    label, score = onchain_bias(0.01, 0.01)
    assert label == "NEUTRAL"
    assert score == 0.0


def test_hash_rate_growth_adds_bullish():
    base = onchain_bias(0.06, 0.12, None)[1]
    with_hr = onchain_bias(0.06, 0.12, 0.15)[1]
    assert with_hr >= base


def test_hash_rate_decline_reduces_score():
    base = onchain_bias(0.06, 0.12, None)[1]
    with_bad_hr = onchain_bias(0.06, 0.12, -0.15)[1]
    assert with_bad_hr <= base


def test_score_clamped():
    label, score = onchain_bias(0.50, 0.50, 0.50)
    assert -1.0 <= score <= 1.0


def test_mild_bullish_label():
    label, score = onchain_bias(0.03, None)
    assert label in ("MILD_BULLISH_ONCHAIN", "NEUTRAL")
    assert score >= 0


def test_addr_growth_dominates_tx_decline():
    # Large addr growth (+0.06) should outweigh mild tx decline (-0.03)
    label, score = onchain_bias(0.06, -0.03)
    assert score > 0
