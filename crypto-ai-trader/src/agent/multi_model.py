"""
Multi-model signal consensus framework.

Calls Claude (always), + GPT-4o (if openai_api_key configured) + Gemini (if
gemini_api_key configured) with the same market context, then takes a
confidence-weighted majority vote.

Each model receives the same structured prompt and returns a JSON blob:
  {"action": "BUY"|"SELL"|"HOLD", "confidence": 0.0-1.0, "reasoning": "..."}

The consensus is applied on top of the rule-based stack: it replaces the
Claude-only signal when multiple models agree.
"""
import asyncio
import json
import logging
from typing import Optional

from .market_analyzer import MarketAnalysis
from .strategy_manager import TradingSignal
from ..core.config import settings

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = """\
You are an expert crypto trading analyst. Analyse the following market snapshot and return ONLY a JSON object.

Symbol: {symbol}
Price: {price:.6f} USDT  |  24h change: {change_24h:+.2f}%
RSI(14): {rsi:.1f} [{rsi_signal}]
MACD: {macd_trend}  |  EMA trend: {ema_trend}
Bollinger: {bb_signal} (pos={bb_position:.2f})
ATR: {atr_pct:.2f}% [{volatility}]  |  VWAP: {price_vs_vwap}
Volume: {volume_signal}  |  Signal strength: {signal_strength:.2f}
Ichimoku: {ichimoku_signal}  |  SuperTrend: {supertrend_signal}
SMC summary: {smc_summary}  (buy={smc_buy:.2f}, sell={smc_sell:.2f})
RSI divergence: {rsi_divergence}
Market regime: {market_regime}
Rule-based signal: {overall_signal}

Respond with ONLY valid JSON — no explanation, no markdown:
{{"action": "BUY"|"SELL"|"HOLD", "confidence": <0.0-1.0>, "reasoning": "<2 sentences max>"}}
"""


def _build_prompt(analysis: MarketAnalysis) -> str:
    def _g(attr, default="N/A"):
        return getattr(analysis, attr, default) or default

    return _PROMPT_TEMPLATE.format(
        symbol=analysis.symbol,
        price=analysis.price,
        change_24h=analysis.change_24h,
        rsi=analysis.rsi,
        rsi_signal=analysis.rsi_signal,
        macd_trend=analysis.macd_trend,
        ema_trend=analysis.ema_trend,
        bb_signal=analysis.bb_signal,
        bb_position=analysis.bb_position,
        atr_pct=analysis.atr_pct,
        volatility=analysis.volatility,
        price_vs_vwap=analysis.price_vs_vwap,
        volume_signal=analysis.volume_signal,
        signal_strength=round(analysis.signal_strength, 2),
        ichimoku_signal=_g("ichimoku_signal"),
        supertrend_signal=_g("supertrend_signal"),
        smc_summary=_g("smc_summary"),
        smc_buy=_g("smc_buy", 0.0),
        smc_sell=_g("smc_sell", 0.0),
        rsi_divergence=_g("rsi_divergence", "NONE"),
        market_regime=_g("market_regime"),
        overall_signal=analysis.overall_signal,
    )


def _parse_response(text: str, model_name: str) -> Optional[dict]:
    """Extract JSON from a model response, tolerating markdown fences."""
    try:
        # Strip markdown fences if present
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:]
        data = json.loads(cleaned)
        action = str(data.get("action", "HOLD")).upper()
        if action not in ("BUY", "SELL", "HOLD"):
            action = "HOLD"
        conf = max(0.0, min(1.0, float(data.get("confidence", 0.5))))
        return {"action": action, "confidence": conf, "reasoning": data.get("reasoning", ""), "model": model_name}
    except Exception as e:
        logger.warning("Failed to parse %s response: %s | text=%s", model_name, e, text[:200])
        return None


async def _call_claude(prompt: str) -> Optional[dict]:
    api_key = settings.claude_api_key
    if not api_key:
        return None
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=api_key)
        resp = await client.messages.create(
            model=settings.claude_model,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text if resp.content else ""
        return _parse_response(text, "claude")
    except Exception as e:
        logger.warning("Claude consensus call failed: %s", e)
        return None


async def _call_gpt4(prompt: str) -> Optional[dict]:
    api_key = settings.get("ai", "openai", "api_key", default="")
    if not api_key:
        return None
    try:
        import openai
        client = openai.AsyncOpenAI(api_key=api_key)
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",  # cost-efficient; upgrade to gpt-4o for higher quality
            max_tokens=256,
            messages=[
                {"role": "system", "content": "You are a crypto trading analyst. Respond only with JSON."},
                {"role": "user", "content": prompt},
            ],
        )
        text = resp.choices[0].message.content if resp.choices else ""
        return _parse_response(text, "gpt4")
    except Exception as e:
        logger.warning("GPT-4 consensus call failed: %s", e)
        return None


async def _call_gemini(prompt: str) -> Optional[dict]:
    api_key = settings.get("ai", "gemini", "api_key", default="")
    if not api_key:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        resp = await asyncio.to_thread(
            model.generate_content,
            f"You are a crypto trading analyst. Respond only with JSON.\n\n{prompt}",
        )
        text = resp.text if hasattr(resp, "text") else ""
        return _parse_response(text, "gemini")
    except Exception as e:
        logger.warning("Gemini consensus call failed: %s", e)
        return None


def _vote(signals: list[dict]) -> TradingSignal:
    """Confidence-weighted majority vote across model signals."""
    if not signals:
        return TradingSignal("HOLD", 0.0, "multi_model", "No model responses", 0.03, 0.06)

    buy_w = sell_w = hold_w = 0.0
    buy_n = sell_n = hold_n = 0
    for s in signals:
        w = s["confidence"]
        if s["action"] == "BUY":
            buy_w += w; buy_n += 1
        elif s["action"] == "SELL":
            sell_w += w; sell_n += 1
        else:
            hold_w += w; hold_n += 1

    total = buy_w + sell_w + hold_w or 1.0
    models_str = ", ".join(s["model"] for s in signals)
    reasonings = " | ".join(f"[{s['model']}] {s['reasoning'][:80]}" for s in signals)

    def _conf(winner_w: float, winner_n: int) -> float:
        # Consensus confidence = (how strongly the winning side agrees, 0..1)
        #                        × (mean confidence of the winning-side models).
        # The agreement ratio alone would inflate a lone 0.6 vote to 1.0; scaling
        # by the winners' mean confidence keeps a single model's call honest.
        if winner_n == 0:
            return 0.0
        agreement   = winner_w / total          # 1.0 only when *all* conviction agrees
        mean_winner = winner_w / winner_n        # average confidence of agreeing models
        return round(agreement * mean_winner, 3)

    if buy_w >= sell_w and buy_w >= hold_w:
        return TradingSignal("BUY", _conf(buy_w, buy_n), "multi_model",
                             f"Consensus ({models_str}): {reasonings}", 0.025, 0.05)
    if sell_w >= buy_w and sell_w >= hold_w:
        return TradingSignal("SELL", _conf(sell_w, sell_n), "multi_model",
                             f"Consensus ({models_str}): {reasonings}", 0.025, 0.05)
    return TradingSignal("HOLD", _conf(hold_w, hold_n), "multi_model",
                         f"No consensus ({models_str}): {reasonings}", 0.03, 0.06)


async def multi_model_signal(analysis: MarketAnalysis) -> TradingSignal:
    """Call all configured AI models and return a weighted consensus signal.

    Falls back to HOLD if no keys are configured. Only adds latency when at
    least one extra model is configured (GPT-4 / Gemini), since Claude is
    always called via the main ClaudeAnalyzer in those cases — this module
    is used when the AI model is explicitly set to 'multi_model'.
    """
    prompt = _build_prompt(analysis)

    # Append live sentiment as a shared contrarian overlay for every model.
    try:
        from ..data.sentiment import get_fear_greed
        fng = await get_fear_greed()
        fgv = fng.get("value")
        if fgv is not None:
            prompt += (
                f"\n\nMarket sentiment — Fear & Greed Index: {fgv} ({fng.get('label')}). "
                "Use as a CONTRARIAN filter: Extreme Greed (>75) warns against new longs; "
                "Extreme Fear (<25) favours accumulation."
            )
    except Exception:
        pass

    tasks = [_call_claude(prompt), _call_gpt4(prompt), _call_gemini(prompt)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    signals = [r for r in results if isinstance(r, dict) and r is not None]

    if not signals:
        return TradingSignal("HOLD", 0.0, "multi_model",
                             "All model calls failed or no API keys configured", 0.03, 0.06)

    consensus = _vote(signals)
    logger.info(
        "Multi-model consensus for %s: %s (conf=%.2f) from %d model(s)",
        analysis.symbol, consensus.action, consensus.confidence, len(signals)
    )
    return consensus
