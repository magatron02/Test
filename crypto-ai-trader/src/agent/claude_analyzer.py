"""
Agentic Claude trading analyst.

Instead of a single-shot prompt, this runs Claude in an agentic loop: Claude is
given tools to gather its own context (multi-timeframe indicators, recent trade
outcomes, live portfolio state), reasons across multiple steps, and finishes by
calling `submit_trading_decision`. The system prompt + tool schema are prompt-
cached so repeated cycles only pay for the small per-request delta.
"""
import asyncio
import json
import logging
from typing import Optional

from .market_analyzer import MarketAnalysis, analyze
from .strategy_manager import TradingSignal
from ..core.config import settings
from ..core.database import SessionLocal, Trade

logger = logging.getLogger(__name__)

# Static — frozen so the prompt-cache prefix stays byte-identical across cycles.
SYSTEM_PROMPT = """You are an expert crypto trading analyst operating an automated trading desk.

Your job: decide BUY, SELL, or HOLD for one symbol per analysis cycle.

You have tools to gather context before deciding. Use them deliberately:
- get_multi_timeframe: pull indicators across 5m / 15m / 1h / 4h to confirm the trend on multiple horizons before committing. A signal that only shows on one timeframe is weak.
- get_recent_trades: review how recent trades on this symbol played out, so you learn from wins/losses instead of repeating mistakes.
- get_portfolio_state: check cash, open positions, and today's PnL before sizing risk. Never recommend BUY if cash is thin or daily loss limits are near.

Method:
1. Start from the rule-based signal and indicators provided.
2. Call tools to confirm or refute that read across timeframes and against recent outcomes.
3. Weigh confluence: align trend (EMA/MACD), momentum (RSI), volatility (ATR), and volume.
4. Be conservative — when timeframes disagree or volatility is high without direction, prefer HOLD.
5. Finish by calling submit_trading_decision exactly once with your final call.

Risk discipline:
- stop_loss_pct and take_profit_pct must reflect current volatility (wider stops in high ATR).
- confidence is your honest probability the trade is right (0.0–1.0). Don't inflate it.
- A HOLD is a valid, often correct, decision. Capital preservation beats forced trades."""

TOOLS = [
    {
        "name": "get_multi_timeframe",
        "description": "Get technical indicators (RSI, MACD, EMA trend, Bollinger position, ATR, VWAP) for the symbol across multiple timeframes (5m, 15m, 1h, 4h). Use to confirm trend alignment before deciding.",
        "input_schema": {
            "type": "object",
            "properties": {
                "timeframes": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["5m", "15m", "1h", "4h"]},
                    "description": "Which timeframes to fetch. Default all four if omitted.",
                }
            },
            "required": [],
        },
    },
    {
        "name": "get_recent_trades",
        "description": "Get the most recent closed trades for this symbol with their PnL outcomes. Use to learn from how similar setups performed recently.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "How many recent trades to return (max 15)."}
            },
            "required": [],
        },
    },
    {
        "name": "get_portfolio_state",
        "description": "Get current portfolio: cash (USDT), total value, open positions, and today's realized PnL. Use to size risk and respect loss limits before recommending a BUY.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "submit_trading_decision",
        "description": "Submit your final trading decision. Call this exactly once when your analysis is complete.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["BUY", "SELL", "HOLD"]},
                "confidence": {"type": "number", "description": "0.0 to 1.0 — honest probability the trade is correct."},
                "reasoning": {"type": "string", "description": "Concise rationale citing the key evidence (timeframes, indicators, recent outcomes)."},
                "risk_level": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH"]},
                "stop_loss_pct": {"type": "number", "description": "Stop-loss as a fraction (e.g. 0.03 = 3%). Wider in high volatility."},
                "take_profit_pct": {"type": "number", "description": "Take-profit as a fraction (e.g. 0.06 = 6%)."},
            },
            "required": ["action", "confidence", "reasoning", "stop_loss_pct", "take_profit_pct"],
        },
    },
]

MAX_STEPS = 6  # cap the agentic loop so a cycle can't run away on tool calls


class ClaudeAnalyzer:
    def __init__(self, exchange=None):
        self._client = None
        self._exchange = exchange  # injected by AITrader for tool execution

    def set_exchange(self, exchange):
        self._exchange = exchange

    def _get_client(self):
        if self._client is None:
            api_key = settings.claude_api_key
            if not api_key:
                raise ValueError("Claude API key not configured")
            import anthropic
            self._client = anthropic.AsyncAnthropic(api_key=api_key)
        return self._client

    # ── tool execution ───────────────────────────────────────────────────
    async def _exec_tool(self, name: str, tool_input: dict, analysis: MarketAnalysis) -> str:
        try:
            if name == "get_multi_timeframe":
                return await self._tool_multi_timeframe(analysis, tool_input.get("timeframes"))
            if name == "get_recent_trades":
                return self._tool_recent_trades(analysis.symbol, tool_input.get("limit", 10))
            if name == "get_portfolio_state":
                return await self._tool_portfolio_state()
            return json.dumps({"error": f"unknown tool {name}"})
        except Exception as e:
            logger.warning(f"Tool {name} failed: {e}")
            return json.dumps({"error": str(e)})

    async def _tool_multi_timeframe(self, analysis: MarketAnalysis, timeframes) -> str:
        tfs = timeframes or ["5m", "15m", "1h", "4h"]
        if not self._exchange:
            return json.dumps({"error": "exchange unavailable"})
        out = {}
        for tf in tfs:
            try:
                candles = await self._exchange.get_ohlcv(analysis.symbol, timeframe=tf, limit=100)
                a = analyze(analysis.symbol, candles, candles[-1].close, analysis.change_24h)
                out[tf] = {
                    "rsi": round(a.rsi, 1),
                    "rsi_signal": a.rsi_signal,
                    "macd_trend": a.macd_trend,
                    "ema_trend": a.ema_trend,
                    "bb_position": round(a.bb_position, 2),
                    "atr_pct": round(a.atr_pct, 2),
                    "volatility": a.volatility,
                    "price_vs_vwap": a.price_vs_vwap,
                    "overall_signal": a.overall_signal,
                    "signal_strength": round(a.signal_strength, 2),
                }
            except Exception as e:
                out[tf] = {"error": str(e)}
        return json.dumps(out)

    def _tool_recent_trades(self, symbol: str, limit: int) -> str:
        limit = max(1, min(int(limit), 15))
        db = SessionLocal()
        try:
            rows = (
                db.query(Trade)
                .filter(Trade.symbol == symbol, Trade.status == "closed")
                .order_by(Trade.closed_at.desc())
                .limit(limit)
                .all()
            )
            trades = [
                {
                    "side": t.side,
                    "pnl_pct": round(t.pnl_pct, 2) if t.pnl_pct is not None else None,
                    "win": (t.pnl_pct or 0) > 0,
                    "strategy": t.strategy,
                    "closed_at": t.closed_at.isoformat() if t.closed_at else None,
                }
                for t in rows
            ]
            wins = sum(1 for t in trades if t["win"])
            summary = {
                "count": len(trades),
                "win_rate": round(wins / len(trades), 2) if trades else None,
                "trades": trades,
            }
            return json.dumps(summary)
        finally:
            db.close()

    async def _tool_portfolio_state(self) -> str:
        if not self._exchange:
            return json.dumps({"error": "exchange unavailable"})
        balances = await self._exchange.get_balance()
        cash = balances.get("USDT")
        holdings = {
            asset: {"free": round(b.free, 6), "total": round(b.total, 6)}
            for asset, b in balances.items()
            if b.total and b.total > 0
        }
        return json.dumps({
            "cash_usdt": round(float(cash.free), 2) if cash else 0.0,
            "holdings": holdings,
        })

    # ── agentic loop ──────────────────────────────────────────────────────
    async def analyze(self, analysis: MarketAnalysis, portfolio_summary: dict) -> TradingSignal:
        try:
            client = self._get_client()
        except Exception as e:
            return TradingSignal("HOLD", 0.0, "claude", f"Claude unavailable: {e}", 0.03, 0.06)

        max_tokens = int(settings.get("ai", "claude", "max_tokens", default=2048))
        system = [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}]
        messages = [{"role": "user", "content": self._initial_prompt(analysis, portfolio_summary)}]

        try:
            for _ in range(MAX_STEPS):
                resp = await client.messages.create(
                    model=settings.claude_model,
                    max_tokens=max_tokens,
                    system=system,
                    tools=TOOLS,
                    messages=messages,
                )

                tool_uses = [b for b in resp.content if b.type == "tool_use"]

                # Terminal: the agent submitted its decision.
                for tu in tool_uses:
                    if tu.name == "submit_trading_decision":
                        return self._to_signal(tu.input)

                if resp.stop_reason != "tool_use" or not tool_uses:
                    # No decision and no tools requested → conservative default.
                    break

                # Execute context-gathering tools and feed results back.
                messages.append({"role": "assistant", "content": resp.content})
                results = []
                for tu in tool_uses:
                    result = await self._exec_tool(tu.name, tu.input or {}, analysis)
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": tu.id,
                        "content": result,
                    })
                messages.append({"role": "user", "content": results})

            return TradingSignal("HOLD", 0.3, "claude",
                                 "Agent did not reach a decision within step budget", 0.03, 0.06)
        except Exception as e:
            logger.error(f"Claude agentic analysis failed: {e}")
            return TradingSignal("HOLD", 0.0, "claude", f"Claude error: {e}", 0.03, 0.06)

    def _to_signal(self, data: dict) -> TradingSignal:
        return TradingSignal(
            action=str(data.get("action", "HOLD")).upper(),
            confidence=float(data.get("confidence", 0.5)),
            strategy="claude",
            reasoning=data.get("reasoning", "Claude agentic analysis"),
            stop_loss_pct=float(data.get("stop_loss_pct", 0.03)),
            take_profit_pct=float(data.get("take_profit_pct", 0.06)),
        )

    def _initial_prompt(self, analysis: MarketAnalysis, portfolio: dict) -> str:
        return f"""Analyze {analysis.symbol} and decide BUY / SELL / HOLD.

Snapshot (15m timeframe):
- Price: {analysis.price:.6f} USDT | 24h change: {analysis.change_24h:+.2f}%
- RSI(14): {analysis.rsi:.1f} [{analysis.rsi_signal}]
- MACD hist: {analysis.macd_hist:.6f} [{analysis.macd_trend}]
- EMA trend: {analysis.ema_trend} (9={analysis.ema_9:.4f} 21={analysis.ema_21:.4f} 50={analysis.ema_50:.4f})
- Bollinger position: {analysis.bb_position:.2f} [{analysis.bb_signal}]
- ATR: {analysis.atr_pct:.2f}% [{analysis.volatility}] | VWAP: price is {analysis.price_vs_vwap}
- Volume ratio: {analysis.volume_ratio:.2f}x [{analysis.volume_signal}]
- Rule-based signal: {analysis.overall_signal} (strength {analysis.signal_strength:.2f})

Portfolio: cash {portfolio.get('cash_usdt', 0):.2f} USDT | total {portfolio.get('total_value', 0):.2f} USDT | open positions {portfolio.get('open_positions', 0)}

Use your tools to confirm across timeframes and against recent trade outcomes, then submit your decision."""
