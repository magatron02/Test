"""Rule-based market narrative — a plain-language Thai summary of the state.

Inspired by Understand-Anything's "domain view": instead of leaving the user to
read raw numbers, this composes the analysis + regime + final signal into a
short, human-readable paragraph that explains *what the market is doing and why
the AI leans the way it does*. Entirely rule-based, so it costs nothing and is
always available — even when Claude is disabled.
"""
from typing import Optional

_REGIME_TH = {
    "BULL_TREND": "อยู่ในแนวโน้มขาขึ้น",
    "BEAR_TREND": "อยู่ในแนวโน้มขาลง",
    "RANGING":    "แกว่งตัวออกข้าง (sideways)",
    "VOLATILE":   "ผันผวนสูง ทิศทางยังไม่ชัด",
    "CRASH":      "กำลังร่วงแรง ระวังความเสี่ยง",
}

_EMA_TH = {
    "BULLISH": "EMA เรียงตัวขาขึ้น",
    "BEARISH": "EMA เรียงตัวขาลง",
    "NEUTRAL": "EMA ไม่มีทิศทางชัด",
}

_MACD_TH = {
    "BULLISH": "MACD หนุนฝั่งซื้อ",
    "BEARISH": "MACD กดฝั่งขาย",
    "NEUTRAL": "MACD เป็นกลาง",
}

_VOL_TH = {
    "LOW":    "ความผันผวนต่ำ",
    "MEDIUM": "ความผันผวนปานกลาง",
    "HIGH":   "ความผันผวนสูง",
}

_ACTION_TH = {
    "BUY":  "ซื้อ",
    "SELL": "ขาย",
    "HOLD": "ถือ/รอดูจังหวะ",
}


def _rsi_phrase(rsi: float) -> str:
    if rsi >= 70:
        return f"RSI {rsi:.0f} (ซื้อมากเกินไป — ระวังย่อ)"
    if rsi <= 30:
        return f"RSI {rsi:.0f} (ขายมากเกินไป — ลุ้นเด้ง)"
    if rsi >= 55:
        return f"RSI {rsi:.0f} (โมเมนตัมเอียงขึ้น)"
    if rsi <= 45:
        return f"RSI {rsi:.0f} (โมเมนตัมเอียงลง)"
    return f"RSI {rsi:.0f} (เป็นกลาง)"


def _bb_phrase(pos: float) -> Optional[str]:
    if pos >= 0.9:
        return "ราคาชนกรอบบน Bollinger"
    if pos <= 0.1:
        return "ราคาชนกรอบล่าง Bollinger"
    if pos >= 0.7:
        return "ราคาค่อนไปทางกรอบบน"
    if pos <= 0.3:
        return "ราคาค่อนไปทางกรอบล่าง"
    return None  # mid-band is unremarkable; keep the narrative tight


def build_narrative(analysis, regime, signal) -> str:
    """Return a one-paragraph Thai summary of the current market state.

    analysis: MarketAnalysis, regime: RegimeResult|None, signal: TradingSignal.
    """
    sym = analysis.symbol.split("/")[0]
    clauses = []

    regime_name = getattr(regime, "regime", "") if regime else ""
    regime_txt = _REGIME_TH.get(regime_name, "สภาพตลาดยังไม่ชัดเจน")
    clauses.append(f"{sym} {regime_txt}")

    # Trend + momentum core
    core = [
        _EMA_TH.get(analysis.ema_trend, ""),
        _rsi_phrase(analysis.rsi),
        _MACD_TH.get(analysis.macd_trend, ""),
    ]
    clauses.append(", ".join(c for c in core if c))

    # Notable extras — only include when they say something
    extras = []
    bb = _bb_phrase(analysis.bb_position)
    if bb:
        extras.append(bb)
    if analysis.volume_spike:
        extras.append("วอลุ่มพุ่งผิดปกติ")
    elif analysis.volume_signal and analysis.volume_signal not in ("NORMAL", ""):
        extras.append(f"วอลุ่ม {analysis.volume_signal}")
    if analysis.rsi_divergence == "BULLISH":
        extras.append("พบ divergence ฝั่งขึ้น")
    elif analysis.rsi_divergence == "BEARISH":
        extras.append("พบ divergence ฝั่งลง")
    if analysis.ichimoku_signal in ("BULL", "BEAR"):
        extras.append(f"Ichimoku {'หนุนขึ้น' if analysis.ichimoku_signal == 'BULL' else 'กดลง'}")
    if analysis.smc_summary:
        extras.append(f"SMC: {analysis.smc_summary}")
    vol_txt = _VOL_TH.get(analysis.volatility)
    if vol_txt and analysis.volatility != "MEDIUM":
        extras.append(vol_txt)
    if extras:
        clauses.append(" · ".join(extras))

    # Verdict
    action_txt = _ACTION_TH.get(signal.action, signal.action)
    conf = f"{signal.confidence * 100:.0f}%"
    clauses.append(f"AI แนะนำ: {action_txt} (มั่นใจ {conf})")

    return " | ".join(c for c in clauses if c)
