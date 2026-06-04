"""Tests for order book microstructure analysis (F1.2)."""
import pytest
from src.data.orderbook import analyze_order_book


def _book(bid_qtys, ask_qtys, base_price=50000.0):
    """Build a minimal bids/asks list from qty lists."""
    bids = [[base_price - i * 10, q] for i, q in enumerate(bid_qtys)]
    asks = [[base_price + i * 10 + 10, q] for i, q in enumerate(ask_qtys)]
    return bids, asks


def test_empty_bids_returns_error():
    result = analyze_order_book([], [[50001, 1.0]])
    assert "error" in result


def test_empty_asks_returns_error():
    result = analyze_order_book([[50000, 1.0]], [])
    assert "error" in result


def test_balanced_book_is_neutral():
    qty = [1.0] * 10
    bids, asks = _book(qty, qty)
    result = analyze_order_book(bids, asks)
    assert result["signal"] == "NEUTRAL"
    assert abs(result["bid_ask_imbalance"] - 0.5) < 0.01


def test_dominant_bid_depth_is_bullish():
    # 70% of depth on bids
    bids, asks = _book([3.0] * 10, [1.0] * 10)
    result = analyze_order_book(bids, asks)
    assert result["signal"] == "BULLISH"
    assert result["bid_ask_imbalance"] > 0.60


def test_dominant_ask_depth_is_bearish():
    bids, asks = _book([1.0] * 10, [3.0] * 10)
    result = analyze_order_book(bids, asks)
    assert result["signal"] == "BEARISH"
    assert result["bid_ask_imbalance"] < 0.40


def test_bid_wall_detected_as_bullish():
    # One giant bid (support wall), modest asks
    bid_qtys = [50.0] + [1.0] * 9   # first entry is wall (50× average)
    ask_qtys = [1.0] * 10
    bids, asks = _book(bid_qtys, ask_qtys)
    result = analyze_order_book(bids, asks)
    assert result["signal"] == "BULLISH"


def test_ask_wall_detected_as_bearish():
    bid_qtys = [1.0] * 10
    ask_qtys = [50.0] + [1.0] * 9
    bids, asks = _book(bid_qtys, ask_qtys)
    result = analyze_order_book(bids, asks)
    assert result["signal"] == "BEARISH"


def test_spread_bps_is_positive():
    bids, asks = _book([1.0] * 5, [1.0] * 5)
    result = analyze_order_book(bids, asks)
    assert result["spread_bps"] is not None
    assert result["spread_bps"] > 0


def test_wall_pct_fields_populated():
    bid_qtys = [10.0] + [1.0] * 9
    ask_qtys = [1.0] * 10
    bids, asks = _book(bid_qtys, ask_qtys)
    result = analyze_order_book(bids, asks)
    assert result["bid_wall_pct"] > 0
    assert result["ask_wall_pct"] > 0
    assert result["bid_wall_pct"] <= 1.0
    assert result["ask_wall_pct"] <= 1.0


def test_imbalance_bounded():
    bids, asks = _book([5.0] * 10, [2.0] * 10)
    result = analyze_order_book(bids, asks)
    assert 0.0 <= result["bid_ask_imbalance"] <= 1.0
