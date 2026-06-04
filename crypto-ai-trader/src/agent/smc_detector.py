"""
Smart Money Concepts (SMC) Detector
— institutional-grade price action concepts used by modern AI trading systems.

Concepts:
  Market Structure  — Higher Highs/Higher Lows (bullish) vs Lower Highs/Lower Lows (bearish)
  Break of Structure (BOS)    — confirmed continuation signal in trend direction
  Change of Character (ChoCH) — potential reversal, structure shifts against trend
  Fair Value Gaps (FVG)       — imbalance zones where price tends to return
  Order Blocks (OB)           — last candle before a strong impulse move (institutional footprint)
  Liquidity Sweeps            — stop-hunt above highs / below lows before reversal

References:
  - ICT (Inner Circle Trader) methodology
  - SMC trading community research
  - Used/recommended by AI assistants (GPT-4, Gemini, Claude) for modern crypto TA
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class FVG:
    """Fair Value Gap — price imbalance zone."""
    direction: str     # BULL | BEAR
    top: float
    bottom: float
    midpoint: float
    bar_index: int
    filled: bool = False


@dataclass
class OrderBlock:
    """Order Block — last candle before a significant impulse."""
    direction: str     # BULL | BEAR (direction of the subsequent move)
    high: float
    low: float
    close: float
    bar_index: int
    strength: float    # 0.0 – 1.0


@dataclass
class SMCResult:
    """Aggregated SMC analysis result."""
    market_structure: str      # BULLISH | BEARISH | RANGING
    bos: str                   # BULL | BEAR | NONE
    choch: str                 # BULL | BEAR | NONE
    fvgs: List[FVG] = field(default_factory=list)
    order_blocks: List[OrderBlock] = field(default_factory=list)
    liquidity_sweep: str = "NONE"   # BULL | BEAR | NONE
    buy_score: float = 0.0
    sell_score: float = 0.0
    summary: str = ""


# ── Market Structure ──────────────────────────────────────────────────────────

def _find_swing_points(
    closes: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    order: int = 3,
) -> Tuple[List[int], List[int]]:
    """Return indices of swing highs and swing lows."""
    swing_highs, swing_lows = [], []
    for i in range(order, len(closes) - order):
        if all(highs[i] >= highs[i - j] for j in range(1, order + 1)) and \
           all(highs[i] >= highs[i + j] for j in range(1, order + 1)):
            swing_highs.append(i)
        if all(lows[i] <= lows[i - j] for j in range(1, order + 1)) and \
           all(lows[i] <= lows[i + j] for j in range(1, order + 1)):
            swing_lows.append(i)
    return swing_highs, swing_lows


def market_structure(
    closes: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    lookback: int = 50,
) -> Tuple[str, str, str]:
    """
    Returns (structure, bos, choch).
    structure: BULLISH | BEARISH | RANGING
    bos:   BULL | BEAR | NONE  — break of structure (continuation)
    choch: BULL | BEAR | NONE  — change of character (reversal warning)
    """
    n = min(len(closes), lookback)
    c = closes[-n:]
    h = highs[-n:]
    l = lows[-n:]

    sh, sl = _find_swing_points(c, h, l)

    if len(sh) < 2 or len(sl) < 2:
        return "RANGING", "NONE", "NONE"

    last_sh = [c[i] for i in sh[-3:]]
    last_sl = [c[i] for i in sl[-3:]]

    hh = last_sh[-1] > last_sh[-2] if len(last_sh) >= 2 else False
    hl = last_sl[-1] > last_sl[-2] if len(last_sl) >= 2 else False
    lh = last_sh[-1] < last_sh[-2] if len(last_sh) >= 2 else False
    ll = last_sl[-1] < last_sl[-2] if len(last_sl) >= 2 else False

    # Market structure
    if hh and hl:
        struct = "BULLISH"
    elif lh and ll:
        struct = "BEARISH"
    else:
        struct = "RANGING"

    # BOS: price breaks the last swing high (in bullish) or swing low (in bearish)
    bos = "NONE"
    if struct == "BULLISH" and c[-1] > h[sh[-1]] * 1.001:
        bos = "BULL"
    elif struct == "BEARISH" and c[-1] < l[sl[-1]] * 0.999:
        bos = "BEAR"

    # ChoCH: structure shifts opposite to current trend
    choch = "NONE"
    if struct == "BULLISH" and lh:
        choch = "BEAR"
    elif struct == "BEARISH" and hl:
        choch = "BULL"

    return struct, bos, choch


# ── Fair Value Gaps ───────────────────────────────────────────────────────────

def detect_fvg(
    closes: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    lookback: int = 30,
    min_gap_pct: float = 0.005,
) -> List[FVG]:
    """
    Detect Fair Value Gaps in the last `lookback` bars.

    A bullish FVG occurs when:  low[i+1] > high[i-1]  (gap up, price didn't trade there)
    A bearish FVG occurs when:  high[i+1] < low[i-1]  (gap down)

    These zones act as magnets for price retests.
    """
    n = min(len(closes), lookback)
    fvgs: List[FVG] = []
    price = closes[-1]

    for i in range(1, n - 1):
        idx = len(closes) - n + i
        h_prev = highs[idx - 1]
        l_next = lows[idx + 1]
        l_prev = lows[idx - 1]
        h_next = highs[idx + 1]

        # Bullish FVG
        if l_next > h_prev:
            gap_pct = (l_next - h_prev) / h_prev
            if gap_pct >= min_gap_pct:
                mid = (l_next + h_prev) / 2
                filled = price <= l_next  # price came back into the gap
                fvgs.append(FVG(
                    direction="BULL",
                    top=l_next, bottom=h_prev, midpoint=mid,
                    bar_index=idx, filled=filled,
                ))

        # Bearish FVG
        if h_next < l_prev:
            gap_pct = (l_prev - h_next) / l_prev
            if gap_pct >= min_gap_pct:
                mid = (h_next + l_prev) / 2
                filled = price >= h_next
                fvgs.append(FVG(
                    direction="BEAR",
                    top=l_prev, bottom=h_next, midpoint=mid,
                    bar_index=idx, filled=filled,
                ))

    # Return most recent unfilled FVGs (up to 3)
    active = [f for f in fvgs if not f.filled]
    return sorted(active, key=lambda f: f.bar_index, reverse=True)[:3]


# ── Order Blocks ──────────────────────────────────────────────────────────────

def detect_order_blocks(
    closes: np.ndarray,
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    lookback: int = 30,
    impulse_pct: float = 0.015,
) -> List[OrderBlock]:
    """
    Order Blocks: the last opposing candle before a strong impulse move.

    A bullish OB = last bearish candle before a strong bullish impulse.
    A bearish OB = last bullish candle before a strong bearish impulse.
    """
    n = min(len(closes), lookback)
    obs: List[OrderBlock] = []

    for i in range(2, n - 1):
        idx = len(closes) - n + i
        # Measure impulse of the next bar(s)
        impulse = (closes[idx + 1] - closes[idx]) / closes[idx] if closes[idx] > 0 else 0

        if impulse >= impulse_pct:
            # Bullish impulse → look for last bearish candle (OB)
            if opens[idx] > closes[idx]:  # bearish candle
                strength = min(abs(impulse) / (impulse_pct * 2), 1.0)
                obs.append(OrderBlock(
                    direction="BULL",
                    high=highs[idx], low=lows[idx], close=closes[idx],
                    bar_index=idx, strength=strength,
                ))

        elif impulse <= -impulse_pct:
            # Bearish impulse → look for last bullish candle (OB)
            if opens[idx] < closes[idx]:  # bullish candle
                strength = min(abs(impulse) / (impulse_pct * 2), 1.0)
                obs.append(OrderBlock(
                    direction="BEAR",
                    high=highs[idx], low=lows[idx], close=closes[idx],
                    bar_index=idx, strength=strength,
                ))

    return sorted(obs, key=lambda o: o.bar_index, reverse=True)[:3]


# ── Liquidity Sweep ───────────────────────────────────────────────────────────

def detect_liquidity_sweep(
    closes: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    lookback: int = 20,
    sweep_back: int = 3,
) -> str:
    """
    Detect liquidity sweep (stop hunt):
    Price briefly exceeds a recent swing high/low but closes back inside → reversal signal.

    Returns: BULL (swept lows = buy), BEAR (swept highs = sell), NONE
    """
    if len(closes) < lookback + sweep_back:
        return "NONE"

    recent_h = highs[-lookback:-sweep_back].max()
    recent_l = lows[-lookback:-sweep_back].min()
    price = closes[-1]

    # Bearish sweep: spike above recent high but close below it
    if highs[-sweep_back:].max() > recent_h and price < recent_h:
        return "BEAR"

    # Bullish sweep: spike below recent low but close above it
    if lows[-sweep_back:].min() < recent_l and price > recent_l:
        return "BULL"

    return "NONE"


# ── Main SMC Analyser ─────────────────────────────────────────────────────────

def analyse_smc(
    closes: np.ndarray,
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
) -> SMCResult:
    """Run all SMC detectors and aggregate into buy/sell scores."""
    closes = np.asarray(closes, dtype=float)
    opens  = np.asarray(opens,  dtype=float)
    highs  = np.asarray(highs,  dtype=float)
    lows   = np.asarray(lows,   dtype=float)

    struct, bos, choch = market_structure(closes, highs, lows)
    fvgs = detect_fvg(closes, highs, lows)
    obs  = detect_order_blocks(closes, opens, highs, lows)
    liq  = detect_liquidity_sweep(closes, highs, lows)

    buy = sell = 0.0
    notes = []

    # Market structure (0.30 weight)
    if struct == "BULLISH":
        buy  += 0.30
        notes.append("Bullish structure")
    elif struct == "BEARISH":
        sell += 0.30
        notes.append("Bearish structure")

    # BOS (0.20 weight — continuation)
    if bos == "BULL":
        buy  += 0.20
        notes.append("BOS↑")
    elif bos == "BEAR":
        sell += 0.20
        notes.append("BOS↓")

    # ChoCH (0.15 weight — early reversal warning)
    if choch == "BULL":
        buy  += 0.15
        notes.append("ChoCH↑")
    elif choch == "BEAR":
        sell += 0.15
        notes.append("ChoCH↓")

    # FVG bias (0.20 weight)
    price = closes[-1]
    bull_fvg = [f for f in fvgs if f.direction == "BULL" and f.bottom <= price <= f.top]
    bear_fvg = [f for f in fvgs if f.direction == "BEAR" and f.bottom <= price <= f.top]
    if bull_fvg:
        buy  += 0.20
        notes.append("In bullFVG")
    elif bear_fvg:
        sell += 0.20
        notes.append("In bearFVG")

    # Order Blocks (0.15 weight)
    bull_ob = [o for o in obs if o.direction == "BULL" and o.low <= price <= o.high]
    bear_ob = [o for o in obs if o.direction == "BEAR" and o.low <= price <= o.high]
    if bull_ob:
        buy  += 0.15 * max(o.strength for o in bull_ob)
        notes.append("In bullOB")
    elif bear_ob:
        sell += 0.15 * max(o.strength for o in bear_ob)
        notes.append("In bearOB")

    # Liquidity sweep (0.10 — counter-sweep entry)
    if liq == "BULL":
        buy  += 0.10
        notes.append("LiqSweep↑")
    elif liq == "BEAR":
        sell += 0.10
        notes.append("LiqSweep↓")

    return SMCResult(
        market_structure=struct,
        bos=bos,
        choch=choch,
        fvgs=fvgs,
        order_blocks=obs,
        liquidity_sweep=liq,
        buy_score=round(buy,  3),
        sell_score=round(sell, 3),
        summary=" | ".join(notes) if notes else "No SMC signal",
    )
