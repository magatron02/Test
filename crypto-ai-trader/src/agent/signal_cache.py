"""Fingerprint-based incremental analysis cache.

The expensive part of a trading cycle is the Claude agentic call. When the
market state for a symbol is materially unchanged from the previous cycle —
same regime, same indicator signals, price barely moved — re-running Claude
would just spend tokens to reach the same decision.

This cache fingerprints the *categorical* market state plus a price tolerance.
On a hit it returns the previous decision so the caller can skip the API call;
on a miss the caller computes fresh and stores the result. Entries also expire
after a max age so a stale view never persists indefinitely.

Inspired by Understand-Anything's fingerprint-based incremental re-analysis:
only re-run the costly semantic step when the underlying inputs actually change.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class SignalCache:
    def __init__(self, config: Optional[dict] = None):
        cfg = config or {}
        self.enabled = bool(cfg.get("enabled", True))
        # Skip re-analysis only if price moved less than this since the cached call
        self.price_threshold_pct = float(cfg.get("price_threshold_pct", 0.5))
        # Force re-analysis after this age regardless of how quiet the market is
        self.max_age_sec = float(cfg.get("max_age_sec", 1800))

        self._store: Dict[str, dict] = {}   # symbol -> entry
        self._hits = 0                       # cumulative reused (API calls saved)
        self._misses = 0                     # cumulative fresh computes

    @staticmethod
    def _fingerprint(analysis, regime) -> str:
        """Categorical snapshot — if every field is identical, the decision
        should be identical too. Numeric values are intentionally excluded:
        small drift in RSI/MACD shouldn't bust the cache; the price tolerance
        and the regime/signal categories capture meaningful change."""
        parts = [
            analysis.rsi_signal,
            analysis.macd_trend,
            analysis.ema_trend,
            analysis.bb_signal,
            analysis.volatility,
            analysis.price_vs_vwap,
            analysis.volume_signal,
            analysis.ichimoku_signal,
            analysis.supertrend_signal,
            analysis.stoch_rsi_signal,
            analysis.rsi_divergence,
            analysis.smc_summary,
            analysis.overall_signal,
            getattr(regime, "regime", "") if regime else "",
        ]
        return "|".join(str(p) for p in parts)

    def get(self, symbol: str, analysis, regime) -> Optional[object]:
        """Return the cached signal when the market state is unchanged, else None."""
        if not self.enabled:
            return None
        entry = self._store.get(symbol)
        if not entry:
            return None

        age = (datetime.now(timezone.utc) - entry["ts"]).total_seconds()
        if age > self.max_age_sec:
            return None
        if entry["fingerprint"] != self._fingerprint(analysis, regime):
            return None

        old_price = entry["price"]
        if old_price > 0:
            move_pct = abs(analysis.price - old_price) / old_price * 100.0
            if move_pct > self.price_threshold_pct:
                return None

        entry["reuse"] += 1
        self._hits += 1
        return entry["signal"]

    def put(self, symbol: str, analysis, regime, signal) -> None:
        if not self.enabled:
            return
        self._misses += 1
        self._store[symbol] = {
            "fingerprint": self._fingerprint(analysis, regime),
            "price": analysis.price,
            "signal": signal,
            "ts": datetime.now(timezone.utc),
            "reuse": 0,
        }

    def invalidate(self, symbol: Optional[str] = None) -> None:
        """Drop a symbol's entry (or all) — e.g. after a trade changes context."""
        if symbol is None:
            self._store.clear()
        else:
            self._store.pop(symbol, None)

    @property
    def stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "enabled": self.enabled,
            "entries": len(self._store),
            "calls_saved": self._hits,
            "calls_made": self._misses,
            "hit_rate": round(self._hits / total, 2) if total else 0.0,
        }
