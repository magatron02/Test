"""
Chart Pattern Detector — detects 13 classic price action patterns.

Patterns detected:
  Reversal:   Double Top/Bottom, Triple Top/Bottom,
              Head & Shoulder, Inverted Head & Shoulder
  Continuation/Neutral:
              Ascending/Horizontal/Descending Channel,
              Ascending/Symmetrical/Descending Triangle,
              Falling Wedge, Rising Wedge

Each pattern returns:
  PatternResult(name, type, signal, confidence, description_th)

signal: "BUY" | "SELL" | "NEUTRAL"
"""
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np
from scipy.signal import argrelextrema

logger = logging.getLogger(__name__)


@dataclass
class PatternResult:
    name: str           # e.g. "Double Top"
    name_th: str        # Thai name
    pattern_type: str   # reversal | continuation | neutral
    signal: str         # BUY | SELL | NEUTRAL
    confidence: float   # 0.0 – 1.0
    description: str    # reasoning in English
    description_th: str # reasoning in Thai


def _find_pivots(closes: np.ndarray, order: int = 5) -> Tuple[np.ndarray, np.ndarray]:
    """Find local highs and lows in a price series."""
    highs = argrelextrema(closes, np.greater_equal, order=order)[0]
    lows  = argrelextrema(closes, np.less_equal,    order=order)[0]
    return highs, lows


def _pct_diff(a: float, b: float) -> float:
    return abs(a - b) / max(abs(a), abs(b), 1e-9)


# ── Reversal Patterns ─────────────────────────────────────────────────────────

def _double_top(closes: np.ndarray, tol: float = 0.015) -> Optional[PatternResult]:
    """Two peaks at similar price → bearish reversal."""
    highs, lows = _find_pivots(closes[-60:], order=4)
    if len(highs) < 2 or len(lows) < 1:
        return None
    h1, h2 = highs[-2], highs[-1]
    p1, p2  = closes[-60:][h1], closes[-60:][h2]
    if _pct_diff(p1, p2) > tol:
        return None
    # Valley between the two tops must exist
    valley_slice = closes[-60:][h1:h2]
    if len(valley_slice) < 3:
        return None
    valley = valley_slice.min()
    neck   = valley
    conf   = max(0.5, 1.0 - _pct_diff(p1, p2) / tol)
    # Price should be near or below neckline
    current = closes[-1]
    if current > neck * 1.03:
        return None
    return PatternResult(
        name="Double Top", name_th="ดับเบิ้ลท็อป",
        pattern_type="reversal", signal="SELL", confidence=conf,
        description=f"Two peaks at similar price ({p1:.2f}, {p2:.2f}), neckline {neck:.2f}",
        description_th=f"ยอดสองยอดที่ราคาใกล้เคียงกัน → สัญญาณขาลง",
    )


def _double_bottom(closes: np.ndarray, tol: float = 0.015) -> Optional[PatternResult]:
    """Two troughs at similar price → bullish reversal."""
    highs, lows = _find_pivots(closes[-60:], order=4)
    if len(lows) < 2:
        return None
    l1, l2 = lows[-2], lows[-1]
    p1, p2  = closes[-60:][l1], closes[-60:][l2]
    if _pct_diff(p1, p2) > tol:
        return None
    peak_slice = closes[-60:][l1:l2]
    if len(peak_slice) < 3:
        return None
    neck = peak_slice.max()
    conf = max(0.5, 1.0 - _pct_diff(p1, p2) / tol)
    current = closes[-1]
    if current < neck * 0.97:
        return None
    return PatternResult(
        name="Double Bottom", name_th="ดับเบิ้ลบอทเทิม",
        pattern_type="reversal", signal="BUY", confidence=conf,
        description=f"Two troughs at similar price ({p1:.2f}, {p2:.2f}), neck {neck:.2f}",
        description_th=f"ก้นสองก้นที่ราคาใกล้เคียงกัน → สัญญาณขาขึ้น",
    )


def _triple_top(closes: np.ndarray, tol: float = 0.02) -> Optional[PatternResult]:
    highs, _ = _find_pivots(closes[-80:], order=4)
    if len(highs) < 3:
        return None
    h1, h2, h3 = highs[-3], highs[-2], highs[-1]
    prices = [closes[-80:][i] for i in (h1, h2, h3)]
    if max(_pct_diff(prices[0], prices[1]),
           _pct_diff(prices[1], prices[2]),
           _pct_diff(prices[0], prices[2])) > tol:
        return None
    conf = 0.70
    return PatternResult(
        name="Triple Top", name_th="ทริปเปิ้ลท็อป",
        pattern_type="reversal", signal="SELL", confidence=conf,
        description=f"Three peaks near same level ({prices[0]:.2f})",
        description_th="สามยอดที่ระดับราคาเดียวกัน → แรงต้านแข็งแกร่ง สัญญาณขาลง",
    )


def _triple_bottom(closes: np.ndarray, tol: float = 0.02) -> Optional[PatternResult]:
    _, lows = _find_pivots(closes[-80:], order=4)
    if len(lows) < 3:
        return None
    l1, l2, l3 = lows[-3], lows[-2], lows[-1]
    prices = [closes[-80:][i] for i in (l1, l2, l3)]
    if max(_pct_diff(prices[0], prices[1]),
           _pct_diff(prices[1], prices[2]),
           _pct_diff(prices[0], prices[2])) > tol:
        return None
    return PatternResult(
        name="Triple Bottom", name_th="ทริปเปิ้ลบอทเทิม",
        pattern_type="reversal", signal="BUY", confidence=0.70,
        description=f"Three troughs near same level ({prices[0]:.2f})",
        description_th="สามก้นที่ระดับราคาเดียวกัน → แรงรับแข็งแกร่ง สัญญาณขาขึ้น",
    )


def _head_and_shoulder(closes: np.ndarray, tol: float = 0.02) -> Optional[PatternResult]:
    highs, _ = _find_pivots(closes[-80:], order=4)
    if len(highs) < 3:
        return None
    l, h, r = highs[-3], highs[-2], highs[-1]
    pl = closes[-80:][l]
    ph = closes[-80:][h]
    pr = closes[-80:][r]
    # Head must be higher than both shoulders
    if not (ph > pl and ph > pr):
        return None
    if _pct_diff(pl, pr) > tol * 2:
        return None
    conf = 0.65 + 0.10 * (1.0 - _pct_diff(pl, pr) / (tol * 2))
    return PatternResult(
        name="Head & Shoulder", name_th="หัวและไหล่",
        pattern_type="reversal", signal="SELL", confidence=conf,
        description=f"Left={pl:.2f}, Head={ph:.2f}, Right={pr:.2f}",
        description_th="หัวสูงกว่าไหล่ทั้งสอง → สัญญาณพลิกขาลง",
    )


def _inv_head_and_shoulder(closes: np.ndarray, tol: float = 0.02) -> Optional[PatternResult]:
    _, lows = _find_pivots(closes[-80:], order=4)
    if len(lows) < 3:
        return None
    l, h, r = lows[-3], lows[-2], lows[-1]
    pl = closes[-80:][l]
    ph = closes[-80:][h]
    pr = closes[-80:][r]
    if not (ph < pl and ph < pr):
        return None
    if _pct_diff(pl, pr) > tol * 2:
        return None
    conf = 0.65 + 0.10 * (1.0 - _pct_diff(pl, pr) / (tol * 2))
    return PatternResult(
        name="Inverted Head & Shoulder", name_th="หัวและไหล่กลับหัว",
        pattern_type="reversal", signal="BUY", confidence=conf,
        description=f"Left={pl:.2f}, Head(low)={ph:.2f}, Right={pr:.2f}",
        description_th="หัวต่ำกว่าไหล่ทั้งสอง → สัญญาณพลิกขาขึ้น",
    )


# ── Channel Patterns ──────────────────────────────────────────────────────────

def _channel_pattern(closes: np.ndarray, highs: np.ndarray, lows: np.ndarray) -> Optional[PatternResult]:
    """Detect ascending / horizontal / descending channel."""
    n = min(len(closes), 40)
    x = np.arange(n, dtype=float)
    c_slice = closes[-n:]
    h_slice = highs[-n:]
    l_slice = lows[-n:]

    slope_h, _ = np.polyfit(x, h_slice, 1)
    slope_l, _ = np.polyfit(x, l_slice, 1)
    avg_price   = c_slice.mean()

    # Normalised slope per bar
    ns_h = slope_h / avg_price * 100
    ns_l = slope_l / avg_price * 100

    threshold = 0.02  # % per bar

    both_up   = ns_h > threshold and ns_l > threshold
    both_flat = abs(ns_h) <= threshold and abs(ns_l) <= threshold
    both_down = ns_h < -threshold and ns_l < -threshold

    if both_up:
        return PatternResult(
            name="Ascending Channel", name_th="ช่องราคาขาขึ้น",
            pattern_type="continuation", signal="BUY", confidence=0.60,
            description=f"Highs slope={ns_h:.3f}%/bar, Lows slope={ns_l:.3f}%/bar",
            description_th="ช่องราคาเคลื่อนขึ้นทั้งแนวต้านและแนวรับ → เทรนด์ขาขึ้น",
        )
    if both_flat:
        return PatternResult(
            name="Horizontal Channel", name_th="ช่องราคาแนวนอน",
            pattern_type="neutral", signal="NEUTRAL", confidence=0.55,
            description=f"Flat channel, slope≈0",
            description_th="ราคาเคลื่อนในกรอบแนวนอน → sideways market",
        )
    if both_down:
        return PatternResult(
            name="Descending Channel", name_th="ช่องราคาขาลง",
            pattern_type="continuation", signal="SELL", confidence=0.60,
            description=f"Highs slope={ns_h:.3f}%/bar, Lows slope={ns_l:.3f}%/bar",
            description_th="ช่องราคาเคลื่อนลงทั้งแนวต้านและแนวรับ → เทรนด์ขาลง",
        )
    return None


# ── Triangle Patterns ─────────────────────────────────────────────────────────

def _triangle_pattern(closes: np.ndarray, highs: np.ndarray, lows: np.ndarray) -> Optional[PatternResult]:
    n = min(len(closes), 40)
    x = np.arange(n, dtype=float)
    h_slice = highs[-n:]
    l_slice = lows[-n:]
    avg_price = closes[-n:].mean()

    slope_h, _ = np.polyfit(x, h_slice, 1)
    slope_l, _ = np.polyfit(x, l_slice, 1)
    ns_h = slope_h / avg_price * 100
    ns_l = slope_l / avg_price * 100
    thresh = 0.015

    # Ascending triangle: flat top, rising bottom → breakout UP
    if abs(ns_h) <= thresh and ns_l > thresh:
        return PatternResult(
            name="Ascending Triangle", name_th="สามเหลี่ยมขาขึ้น",
            pattern_type="continuation", signal="BUY", confidence=0.65,
            description=f"Flat resistance, rising support slope={ns_l:.3f}%/bar",
            description_th="แนวต้านแนวนอน แนวรับขึ้น → คาดว่าราคาจะทะลุขึ้น",
        )

    # Descending triangle: falling top, flat bottom → breakout DOWN
    if ns_h < -thresh and abs(ns_l) <= thresh:
        return PatternResult(
            name="Descending Triangle", name_th="สามเหลี่ยมขาลง",
            pattern_type="continuation", signal="SELL", confidence=0.65,
            description=f"Declining resistance slope={ns_h:.3f}%/bar, flat support",
            description_th="แนวต้านลง แนวรับแนวนอน → คาดว่าราคาจะทะลุลง",
        )

    # Symmetrical triangle: converging highs and lows → breakout direction uncertain
    if ns_h < -thresh * 0.5 and ns_l > thresh * 0.5:
        return PatternResult(
            name="Symmetrical Triangle", name_th="สามเหลี่ยมสมมาตร",
            pattern_type="neutral", signal="NEUTRAL", confidence=0.55,
            description=f"Converging: highs slope={ns_h:.3f}%, lows slope={ns_l:.3f}%",
            description_th="แนวต้านลง แนวรับขึ้น บีบเข้าหากัน → รอทิศทาง breakout",
        )
    return None


# ── Wedge Patterns ────────────────────────────────────────────────────────────

def _wedge_pattern(closes: np.ndarray, highs: np.ndarray, lows: np.ndarray) -> Optional[PatternResult]:
    n = min(len(closes), 40)
    x = np.arange(n, dtype=float)
    h_slice = highs[-n:]
    l_slice = lows[-n:]
    avg_price = closes[-n:].mean()

    slope_h, _ = np.polyfit(x, h_slice, 1)
    slope_l, _ = np.polyfit(x, l_slice, 1)
    ns_h = slope_h / avg_price * 100
    ns_l = slope_l / avg_price * 100

    # Rising wedge: both lines rise but converge → bearish
    if ns_h > 0.01 and ns_l > 0.01 and ns_l > ns_h:
        return PatternResult(
            name="Rising Wedge", name_th="ลิ่มขาขึ้น",
            pattern_type="reversal", signal="SELL", confidence=0.60,
            description=f"Both rising, converging: h={ns_h:.3f}% l={ns_l:.3f}%",
            description_th="ลิ่มขาขึ้น (ทั้งคู่วิ่งขึ้นแต่บีบเข้า) → มักพลิกขาลง",
        )

    # Falling wedge: both lines fall but converge → bullish
    if ns_h < -0.01 and ns_l < -0.01 and ns_h < ns_l:
        return PatternResult(
            name="Falling Wedge", name_th="ลิ่มขาลง",
            pattern_type="reversal", signal="BUY", confidence=0.60,
            description=f"Both falling, converging: h={ns_h:.3f}% l={ns_l:.3f}%",
            description_th="ลิ่มขาลง (ทั้งคู่วิ่งลงแต่บีบเข้า) → มักพลิกขาขึ้น",
        )
    return None


# ── Main detector ─────────────────────────────────────────────────────────────

def detect_patterns(
    closes: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    min_confidence: float = 0.50,
) -> List[PatternResult]:
    """
    Run all 13 pattern detectors and return those that pass the confidence threshold.
    Returns the top-3 by confidence (avoid noise from many low-quality matches).
    """
    if len(closes) < 30:
        return []

    results: List[PatternResult] = []

    detectors = [
        lambda: _double_top(closes),
        lambda: _double_bottom(closes),
        lambda: _triple_top(closes),
        lambda: _triple_bottom(closes),
        lambda: _head_and_shoulder(closes),
        lambda: _inv_head_and_shoulder(closes),
        lambda: _channel_pattern(closes, highs, lows),
        lambda: _triangle_pattern(closes, highs, lows),
        lambda: _wedge_pattern(closes, highs, lows),
    ]

    for fn in detectors:
        try:
            r = fn()
            if r and r.confidence >= min_confidence:
                results.append(r)
        except Exception as e:
            logger.debug("Pattern detector error: %s", e)

    results.sort(key=lambda r: r.confidence, reverse=True)
    return results[:3]


def patterns_to_signal_boost(patterns: List[PatternResult]) -> Tuple[float, float, str]:
    """
    Aggregate pattern signals into (buy_boost, sell_boost, summary_th).
    Boost values are added to the rule-based composite signal scores.
    """
    buy_boost  = 0.0
    sell_boost = 0.0
    names      = []

    for p in patterns:
        if p.signal == "BUY":
            buy_boost  += p.confidence * 0.15
            names.append(f"[{p.name_th}↑]")
        elif p.signal == "SELL":
            sell_boost += p.confidence * 0.15
            names.append(f"[{p.name_th}↓]")

    summary = " ".join(names) if names else ""
    return buy_boost, sell_boost, summary
