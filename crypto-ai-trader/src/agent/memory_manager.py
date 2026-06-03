"""
AI Trade Memory — supermemory.ai integration.

Stores trade outcomes, analysis reasoning, and market patterns so Claude can
recall past decisions before making new ones. Falls back silently when no API
key is configured.

Usage:
  memory = MemoryManager()
  await memory.add_analysis("BTC/THB", signal="BUY", confidence=0.72,
                             reasoning="RSI 45 oversold + MACD crossover",
                             price=3_500_000)
  await memory.add_outcome("BTC/THB", side="buy", pnl_pct=4.1,
                            reason="tp.hit", holding_hours=2.5)
  memories = await memory.recall("BTC/THB", context="RSI oversold, MACD bullish")
"""
import json
import logging
import time
from typing import Optional

import httpx

from ..core.config import settings

logger = logging.getLogger(__name__)

_BASE = "https://api.supermemory.ai/v1"
_TIMEOUT = 8.0


class MemoryManager:
    def __init__(self):
        cfg = settings.get("ai", "supermemory") or {}
        self._key: str = cfg.get("api_key", "") or ""
        self._enabled: bool = bool(cfg.get("enabled", False)) and bool(self._key)
        self._cache: dict[str, tuple[list, float]] = {}  # symbol → (memories, timestamp)

    def is_enabled(self) -> bool:
        return self._enabled

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
        }

    # ── write ──────────────────────────────────────────────────────────────

    async def add_analysis(
        self,
        symbol: str,
        signal: str,
        confidence: float,
        reasoning: str,
        price: float,
    ) -> None:
        if not self._enabled:
            return
        content = (
            f"[ANALYSIS] {symbol} → {signal} (confidence {confidence:.0%}) "
            f"@ {price:,.0f}\n"
            f"Reasoning: {reasoning}"
        )
        await self._add(content, {"type": "analysis", "symbol": symbol, "signal": signal})

    async def add_outcome(
        self,
        symbol: str,
        side: str,
        pnl_pct: float,
        reason: str,
        holding_hours: float = 0,
        entry: float = 0,
        exit_price: float = 0,
    ) -> None:
        if not self._enabled:
            return
        result = "PROFIT" if pnl_pct > 0 else "LOSS"
        content = (
            f"[OUTCOME] {symbol} {side.upper()} → {result} {pnl_pct:+.2f}% "
            f"(held {holding_hours:.1f}h, exit reason: {reason})\n"
            f"Entry {entry:,.0f} → Exit {exit_price:,.0f}"
        )
        await self._add(content, {
            "type": "outcome", "symbol": symbol, "side": side,
            "pnl_pct": round(pnl_pct, 2), "result": result.lower(),
        })
        # Invalidate cache for this symbol
        self._cache.pop(symbol, None)

    async def _add(self, content: str, metadata: dict) -> None:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                r = await c.post(
                    f"{_BASE}/memories",
                    headers=self._headers(),
                    json={"content": content, "metadata": metadata},
                )
                if r.status_code not in (200, 201):
                    logger.debug(f"Supermemory add {r.status_code}: {r.text[:120]}")
        except Exception as e:
            logger.debug(f"Supermemory add failed: {e}")

    # ── read ───────────────────────────────────────────────────────────────

    async def recall(
        self,
        symbol: str,
        context: str = "",
        limit: int = 6,
        cache_ttl: int = 120,
    ) -> list[str]:
        """Return relevant memories for a symbol. Cached for cache_ttl seconds."""
        if not self._enabled:
            return []

        cached = self._cache.get(symbol)
        if cached and time.time() - cached[1] < cache_ttl:
            return cached[0]

        query = f"{symbol} trade history and analysis. {context}".strip()
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                r = await c.post(
                    f"{_BASE}/memories/search",
                    headers=self._headers(),
                    json={"query": query, "limit": limit},
                )
                if r.status_code == 200:
                    data = r.json()
                    memories = [
                        m.get("content", "")
                        for m in data.get("memories", data.get("results", []))
                        if m.get("content")
                    ]
                    self._cache[symbol] = (memories, time.time())
                    return memories
                logger.debug(f"Supermemory search {r.status_code}: {r.text[:120]}")
        except Exception as e:
            logger.debug(f"Supermemory recall failed: {e}")
        return []

    def recall_as_text(self, memories: list[str]) -> str:
        if not memories:
            return ""
        lines = "\n".join(f"• {m}" for m in memories)
        return f"--- Past memory for this symbol ---\n{lines}\n---"
