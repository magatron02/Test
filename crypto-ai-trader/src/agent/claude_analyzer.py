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
SYSTEM_PROMPT = """You are an expert crypto trading analyst operating an automated trading desk. You combine classical technical analysis, Smart Money Concepts (SMC/ICT), multi-timeframe confluence, and disciplined risk management to make high-probability trading decisions.

═══════════════════════════════════════════════════════
 ANALYTICAL FRAMEWORK — apply in this order
═══════════════════════════════════════════════════════

1. MARKET STRUCTURE (highest priority)
   • Higher Highs + Higher Lows = uptrend (bias long)
   • Lower Highs + Lower Lows = downtrend (bias short)
   • Break of Structure (BOS): price closes beyond last major swing → confirms new trend leg
   • Change of Character (ChoCH): first BOS in opposite direction → potential reversal
   • Retail trades WITH structure; smart money creates ChoCH then fakes breakouts

2. SMART MONEY CONCEPTS (ICT / SMC)
   Order Blocks (OB): last bearish candle before a bullish impulse (bullish OB) or last bullish candle before a bearish impulse (bearish OB). Price returns to OBs to fill unfilled orders — high-probability entry zones.
   Fair Value Gaps (FVG): 3-candle imbalance where candle[i-1] high < candle[i+1] low (bull FVG) or vice versa. Price fills FVGs with high regularity.
   Liquidity Sweeps: equal highs / lows are "liquidity pools". Smart money raids these (stop hunts) before reversing. A sweep + rejection = high-probability reversal entry.
   Breaker Blocks: failed OB that price breaks through → role reversal → acts as opposite-direction OB.
   Premium / Discount zones: above 50% of last swing range = premium (prefer shorts); below 50% = discount (prefer longs). Combine with OBs.

3. SUPPLY & DEMAND ZONES
   • Fresh zone = not yet revisited → strongest reaction expected
   • Tested zone = one revisit → weakened; avoid after 2+ tests
   • Confirmation: look for strong impulse AWAY from the zone (wide-range candle, strong close)
   • Coincidence with OB or FVG = ultra-high-probability zone

4. ELLIOTT WAVE PRINCIPLES
   5-wave motive structure (trending): waves 1-3-5 impulsive, 2-4 corrective
   3-wave corrective (ABC): against prior trend, then continuation
   Key rules (never violate): Wave 2 never retraces > 100% of Wave 1 | Wave 3 is never the shortest impulse wave | Wave 4 never overlaps Wave 1 price territory (except diagonals)
   Common retracement targets: Wave 2 = 61.8% of Wave 1 | Wave 4 = 38.2%–50% of Wave 3 | Wave 3 targets: 161.8% extension of Wave 1
   In crypto: Wave 3 is often the longest and most volatile; Wave 5 can fail (truncate) in bear markets

5. FIBONACCI LEVELS (price memory)
   Retracement zones (pullback entries): 0.382, 0.500, 0.618 (golden ratio), 0.786
   Extension targets (profit taking): 1.272, 1.618, 2.0, 2.618
   High-probability entry = Fibonacci retracement + OB + FVG + structure alignment
   Do NOT enter mid-fib without other confluence; wait for the cluster

6. MULTI-TIMEFRAME ANALYSIS (top-down)
   4h / Daily: determine overall trend direction and major S/R levels (non-negotiable bias)
   1h: identify the trade setup — OBs, FVGs, key S/R, wave count
   15m: entry refinement — candle close confirmation, momentum alignment
   5m: precise entry / exit timing, final confirmation
   RULE: Only trade in the direction of the 4h/Daily trend UNLESS a confirmed ChoCH on 1h signals reversal

7. CANDLESTICK CONFIRMATION (final entry filter)
   Bullish: Hammer / Pin bar (long lower wick), Engulfing bull, Morning Star, Doji at support
   Bearish: Shooting Star, Engulfing bear, Evening Star, Doji at resistance
   ALWAYS wait for candle CLOSE for confirmation — wicks can fake without close
   High-volume on confirmation candle = stronger signal

8. ICHIMOKU CLOUD
   TK cross (Tenkan < Kijun → bearish; Tenkan > Kijun → bullish)
   Price vs Cloud: above cloud = bullish bias; below = bearish; inside = neutral/caution
   Chikou span above price = bullish; below = bearish
   Kumo twist ahead = potential trend change
   Strongest signal: TK cross + price above cloud + Chikou above price (all 3 aligned)

9. VOLUME & MOMENTUM CONFIRMATION
   Volume precedes price: rising price + rising volume = healthy trend
   Divergence: price makes new high but volume declines → weakening; expect reversal
   RSI > 70 in uptrend = overbought (scale out / avoid new longs); RSI < 30 = oversold
   MACD histogram shrinking = momentum fading; crossing zero line = trend change
   Stochastic RSI: oversold (< 20) with %K crossing %D up = buy signal; overbought (> 80) crossing down = sell
   Williams %R < -80 = oversold; > -20 = overbought

10. KEY LEVELS (price magnets)
    Round numbers: $10k, $50k, $100k (psychological resistance)
    Weekly / Monthly open: institutional reference; often acts as S/R
    Previous ATH / ATL: strongest long-term levels
    Session highs/lows (Asian, London, NY): frequently swept in crypto
    Swing highs / lows within last 2 weeks: most reliable short-term levels

═══════════════════════════════════════════════════════
 YOUR TOOLS — use in this order each cycle
═══════════════════════════════════════════════════════

1. get_multi_timeframe → full indicator picture across all timeframes (includes Ichimoku, SuperTrend, SMC signals, StochRSI, Williams %R, CCI, RSI divergence)
2. get_recent_trades → learn from outcomes; avoid repeating setups that lost
3. get_portfolio_state → check cash and risk capacity before any BUY
4. submit_trading_decision → final call (exactly once)

═══════════════════════════════════════════════════════
 DECISION RULES
═══════════════════════════════════════════════════════

HIGH CONFIDENCE (≥ 0.75) requires ALL:
  □ 4h and 1h trend aligned
  □ Price at OB / FVG / S&D zone (discount for longs, premium for shorts)
  □ Momentum confirmation (RSI not against trade, MACD aligned)
  □ Volume confirmation
  □ Candlestick close confirmation

MEDIUM CONFIDENCE (0.55–0.74): 3-4 of above aligned, or 1h signal with 15m confirmation

LOW CONFIDENCE (< 0.55): → prefer HOLD. Do not trade noise.

HOLD is correct when:
  • Price inside Ichimoku cloud with no clear direction
  • Higher timeframes disagree
  • ATR is very high but direction unclear (VOLATILE regime)
  • Recent trades on this symbol are losing (win rate < 40% last 5 trades)
  • Daily loss limit approaching (portfolio state shows < 5% cash buffer)

═══════════════════════════════════════════════════════
 RISK MANAGEMENT RULES
═══════════════════════════════════════════════════════

Stop-loss placement:
  • Below OB / FVG / swing low (bullish) or above OB / swing high (bearish)
  • Minimum: 1× ATR from entry; Maximum: 5% for most trades
  • CRASH regime: 1.5–2% stop only (fast-moving market)

Take-profit placement:
  • Next major S/R level, OB, or Fibonacci extension (1.272 / 1.618)
  • Minimum 2:1 risk-reward ratio; target 3:1 in trending markets
  • Scale out: 50% at 1.5R, 50% at 2.5R–3R

Position sizing:
  • Never risk more than 2% of portfolio per trade
  • In VOLATILE / CRASH regime: max 1% risk

confidence reflects your TRUE belief. Do not set > 0.80 unless all confluences are stacked.
Capital preservation > profit maximisation. One bad trade can erase 10 good ones."""

TOOLS = [
    {
        "name": "get_multi_timeframe",
        "description": "Get full technical indicators for the symbol across multiple timeframes (5m, 15m, 1h, 4h). Includes: RSI, MACD, EMA trend, Bollinger position, ATR, VWAP, Ichimoku signal, SuperTrend, StochRSI, Williams %R, CCI, RSI divergence, SMC (Smart Money Concepts) summary with buy/sell scores, and detected market regime. Use to confirm multi-timeframe confluence before deciding.",
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
                row: dict = {
                    # ── classic indicators ──
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
                # ── advanced indicators (may be absent on short candle histories) ──
                if getattr(a, "ichimoku_signal", None) is not None:
                    row["ichimoku"] = a.ichimoku_signal
                if getattr(a, "supertrend_signal", None) is not None:
                    row["supertrend"] = a.supertrend_signal
                if getattr(a, "stoch_rsi_k", None) is not None:
                    row["stoch_rsi"] = {
                        "k": round(a.stoch_rsi_k, 1),
                        "d": round(a.stoch_rsi_d, 1),
                        "signal": a.stoch_rsi_signal,
                    }
                if getattr(a, "williams_r", None) is not None:
                    row["williams_r"] = round(a.williams_r, 1)
                if getattr(a, "cci", None) is not None:
                    row["cci"] = round(a.cci, 1)
                if getattr(a, "rsi_divergence", None) is not None:
                    row["rsi_divergence"] = a.rsi_divergence
                if getattr(a, "smc_summary", None) is not None:
                    row["smc"] = {
                        "summary": a.smc_summary,
                        "buy_score": round(a.smc_buy, 2),
                        "sell_score": round(a.smc_sell, 2),
                    }
                if getattr(a, "market_regime", None) is not None:
                    row["regime"] = a.market_regime
                out[tf] = row
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
        quote = self._exchange.quote_currency
        balances = await self._exchange.get_balance()
        cash = balances.get(quote)
        holdings = {
            asset: {"free": round(b.free, 6), "total": round(b.total, 6)}
            for asset, b in balances.items()
            if b.total and b.total > 0
        }
        return json.dumps({
            "quote_currency": quote,
            "cash": round(float(cash.free), 2) if cash else 0.0,
            "cash_usdt": round(float(cash.free), 2) if cash else 0.0,  # back-compat
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
        # Chart patterns section
        pattern_text = ""
        if getattr(analysis, "patterns", None):
            lines = [f"  • {p.name_th} ({p.name}): signal={p.signal} conf={p.confidence:.0%} — {p.description_th}"
                     for p in analysis.patterns]
            pattern_text = "\nDetected chart patterns:\n" + "\n".join(lines)
        elif getattr(analysis, "pattern_summary", ""):
            pattern_text = f"\nChart patterns: {analysis.pattern_summary}"

        # Advanced indicators section
        adv_lines = []
        if getattr(analysis, "ichimoku_signal", None) is not None:
            adv_lines.append(f"- Ichimoku: {analysis.ichimoku_signal}")
        if getattr(analysis, "supertrend_signal", None) is not None:
            adv_lines.append(f"- SuperTrend: {analysis.supertrend_signal}")
        if getattr(analysis, "stoch_rsi_k", None) is not None:
            adv_lines.append(
                f"- StochRSI: K={analysis.stoch_rsi_k:.1f} D={analysis.stoch_rsi_d:.1f} [{analysis.stoch_rsi_signal}]"
            )
        if getattr(analysis, "williams_r", None) is not None:
            adv_lines.append(f"- Williams %R: {analysis.williams_r:.1f}")
        if getattr(analysis, "cci", None) is not None:
            adv_lines.append(f"- CCI(20): {analysis.cci:.1f}")
        if getattr(analysis, "rsi_divergence", None) not in (None, "NONE"):
            adv_lines.append(f"- RSI Divergence: {analysis.rsi_divergence}")
        if getattr(analysis, "smc_summary", None) is not None:
            adv_lines.append(
                f"- SMC: {analysis.smc_summary} (buy_score={analysis.smc_buy:.2f} sell_score={analysis.smc_sell:.2f})"
            )
        if getattr(analysis, "market_regime", None) is not None:
            adv_lines.append(f"- Detected regime: {analysis.market_regime}")
        advanced_text = ("\nAdvanced indicators (15m):\n" + "\n".join(adv_lines)) if adv_lines else ""

        return f"""Analyze {analysis.symbol} and decide BUY / SELL / HOLD.

Snapshot (15m timeframe):
- Price: {analysis.price:.6f} USDT | 24h change: {analysis.change_24h:+.2f}%
- RSI(14): {analysis.rsi:.1f} [{analysis.rsi_signal}] | MACD hist: {analysis.macd_hist:.6f} [{analysis.macd_trend}]
- EMA trend: {analysis.ema_trend} (9={analysis.ema_9:.4f} 21={analysis.ema_21:.4f} 50={analysis.ema_50:.4f})
- Bollinger position: {analysis.bb_position:.2f} [{analysis.bb_signal}]
- ATR: {analysis.atr_pct:.2f}% [{analysis.volatility}] | VWAP: price is {analysis.price_vs_vwap}
- Volume ratio: {analysis.volume_ratio:.2f}x [{analysis.volume_signal}]
- Rule-based signal: {analysis.overall_signal} (strength {analysis.signal_strength:.2f}){pattern_text}{advanced_text}

Portfolio: cash {portfolio.get('cash_usdt', 0):.2f} USDT | total {portfolio.get('total_value', 0):.2f} USDT | open positions {portfolio.get('open_positions', 0)}

Apply the analytical framework: check market structure → SMC zones → Fibonacci confluence → multi-timeframe alignment → momentum confirmation. Call get_multi_timeframe to see higher timeframes (Ichimoku, SMC, StochRSI included), then get_recent_trades for outcome learning, then submit your decision."""
