import json
import logging
from typing import Optional

from .market_analyzer import MarketAnalysis
from .strategy_manager import TradingSignal
from ..core.config import settings

logger = logging.getLogger(__name__)


class ClaudeAnalyzer:
    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            api_key = settings.claude_api_key
            if not api_key:
                raise ValueError("Claude API key not configured")
            import anthropic
            self._client = anthropic.Anthropic(api_key=api_key)
        return self._client

    def analyze(self, analysis: MarketAnalysis, portfolio_summary: dict) -> TradingSignal:
        prompt = self._build_prompt(analysis, portfolio_summary)
        try:
            client = self._get_client()
            response = client.messages.create(
                model=settings.claude_model,
                max_tokens=settings.get("ai", "claude", "max_tokens", default=1024),
                messages=[{"role": "user", "content": prompt}],
                system=(
                    "You are an expert crypto trading AI. Analyze market data and respond with a "
                    "JSON trading decision. Always respond with valid JSON only, no extra text.\n"
                    "Response format: {\"action\": \"BUY|SELL|HOLD\", \"confidence\": 0.0-1.0, "
                    "\"reasoning\": \"string\", \"risk_level\": \"LOW|MEDIUM|HIGH\", "
                    "\"stop_loss_pct\": 0.0-0.1, \"take_profit_pct\": 0.0-0.15}"
                ),
            )
            text = response.content[0].text.strip()
            data = json.loads(text)
            return TradingSignal(
                action=data.get("action", "HOLD").upper(),
                confidence=float(data.get("confidence", 0.5)),
                strategy="claude",
                reasoning=data.get("reasoning", "Claude analysis"),
                stop_loss_pct=float(data.get("stop_loss_pct", 0.03)),
                take_profit_pct=float(data.get("take_profit_pct", 0.06)),
            )
        except Exception as e:
            logger.error(f"Claude analysis failed: {e}")
            return TradingSignal("HOLD", 0.0, "claude", f"Claude error: {e}", 0.03, 0.06)

    def _build_prompt(self, analysis: MarketAnalysis, portfolio: dict) -> str:
        return f"""Analyze the following cryptocurrency market data and provide a trading decision.

Symbol: {analysis.symbol}
Current Price: {analysis.price:.6f} USDT
24h Change: {analysis.change_24h:+.2f}%

Technical Indicators:
- RSI(14): {analysis.rsi:.1f} [{analysis.rsi_signal}]
- MACD: {analysis.macd:.6f} | Signal: {analysis.macd_signal:.6f} | Hist: {analysis.macd_hist:.6f} [{analysis.macd_trend}]
- EMA 9: {analysis.ema_9:.4f} | EMA 21: {analysis.ema_21:.4f} | EMA 50: {analysis.ema_50:.4f} [{analysis.ema_trend}]
- Bollinger Bands: Upper={analysis.bb_upper:.4f} | Mid={analysis.bb_middle:.4f} | Lower={analysis.bb_lower:.4f}
  Position in band: {analysis.bb_position:.2f} (0=lower, 1=upper) [{analysis.bb_signal}]
- ATR: {analysis.atr:.4f} ({analysis.atr_pct:.2f}% volatility) [{analysis.volatility}]
- VWAP: {analysis.vwap:.4f} [price is {analysis.price_vs_vwap}]
- Volume ratio vs 20-period avg: {analysis.volume_ratio:.2f}x [{analysis.volume_signal}]

Portfolio State:
- Cash (USDT): {portfolio.get('cash_usdt', 0):.2f}
- Total Value: {portfolio.get('total_value', 0):.2f} USDT
- Open Positions: {portfolio.get('open_positions', 0)}

Rule-based signal: {analysis.overall_signal} (strength: {analysis.signal_strength:.2f})

Provide your trading decision as JSON."""
