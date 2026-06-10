"""
Model router — selects which Claude model to call based on market context.

Haiku (fast + cheap) handles clear-trend, routine decisions.
Sonnet (powerful) handles ambiguous, high-stakes, or crisis situations.

Routing criteria
----------------
Use Sonnet when ANY of the following:
  • regime is CRASH or VOLATILE
  • regime is RANGING (direction unclear → needs deeper reasoning)
  • recent_win_rate < threshold (model struggling → escalate)
  • atr_pct > threshold (explosive price action)
  • routing disabled (always use configured model)

Otherwise use Haiku.

Settings (ai.routing in settings.yml)
--------------------------------------
  enabled: true
  haiku_model:  "claude-haiku-4-5-20251001"
  sonnet_model: "claude-sonnet-4-6"
  sonnet_regimes: ["CRASH", "VOLATILE", "RANGING"]
  low_win_rate:   0.40   # win rate below this → sonnet
  high_atr_pct:   3.0    # ATR% above this → sonnet
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Model IDs ─────────────────────────────────────────────────────────────────

HAIKU_MODEL  = "claude-haiku-4-5-20251001"
SONNET_MODEL = "claude-sonnet-4-6"

# Rough input cost per million tokens (USD) for cost estimation
_COST_PER_MTOK = {
    HAIKU_MODEL:  0.80,
    SONNET_MODEL: 3.00,
}
_AVG_TOKENS_PER_CALL = 4_000   # rough estimate for trading analysis

# ── Router ────────────────────────────────────────────────────────────────────

class ModelRouter:
    """Selects Claude model per trading analysis call.

    Instantiate once per session and reuse. Tracks per-model call counts and
    estimated cost. Thread-safe for asyncio (no shared mutable state between
    concurrent coroutines; counters are updated after each call).
    """

    def __init__(self):
        self._calls: dict[str, int] = {HAIKU_MODEL: 0, SONNET_MODEL: 0}
        self._last_model: str = SONNET_MODEL
        self._last_reason: str = ""

    # ── Public API ────────────────────────────────────────────────────────────

    def select(
        self,
        regime: str = "RANGING",
        atr_pct: float = 1.0,
        recent_win_rate: Optional[float] = None,
        override: Optional[str] = None,
    ) -> str:
        """Return the model ID to use for the next analysis call.

        Parameters
        ----------
        regime:          Market regime string from RegimeResult (e.g. "BULL_TREND")
        atr_pct:         ATR as % of price (higher = more volatile)
        recent_win_rate: Last N-trade win rate (None if no history)
        override:        Hard model override (bypasses routing, e.g. "sonnet" / "haiku")
        """
        from ..core.config import settings

        cfg = settings.get("ai", "routing") or {}
        enabled = bool(cfg.get("enabled", True))

        if not enabled:
            # Routing disabled — respect the global model setting
            model = settings.claude_model
            self._last_reason = "routing disabled"
            return self._record(model)

        if override:
            model = self._resolve_alias(override)
            self._last_reason = f"override={override}"
            return self._record(model)

        sonnet_regimes = cfg.get("sonnet_regimes", ["CRASH", "VOLATILE", "RANGING"])
        low_win_rate   = float(cfg.get("low_win_rate",  0.40))
        high_atr_pct   = float(cfg.get("high_atr_pct",  3.0))

        haiku_id  = cfg.get("haiku_model",  HAIKU_MODEL)
        sonnet_id = cfg.get("sonnet_model", SONNET_MODEL)

        # Sonnet conditions (any → escalate)
        if regime in sonnet_regimes:
            self._last_reason = f"regime={regime}"
            return self._record(sonnet_id)

        if recent_win_rate is not None and recent_win_rate < low_win_rate:
            self._last_reason = f"win_rate={recent_win_rate:.0%}<{low_win_rate:.0%}"
            return self._record(sonnet_id)

        if atr_pct > high_atr_pct:
            self._last_reason = f"atr_pct={atr_pct:.1f}%>{high_atr_pct}%"
            return self._record(sonnet_id)

        self._last_reason = f"routine regime={regime}"
        return self._record(haiku_id)

    def record_call(self, model: str) -> None:
        """Call after each API response to increment the counter."""
        self._calls[model] = self._calls.get(model, 0) + 1

    @property
    def stats(self) -> dict:
        total = sum(self._calls.values())
        est_cost = sum(
            n * _AVG_TOKENS_PER_CALL / 1_000_000 * _COST_PER_MTOK.get(m, 3.0)
            for m, n in self._calls.items()
        )
        haiku_calls  = self._calls.get(HAIKU_MODEL, 0)
        sonnet_calls = self._calls.get(SONNET_MODEL, 0)
        return {
            "total_calls":       total,
            "haiku_calls":       haiku_calls,
            "sonnet_calls":      sonnet_calls,
            "haiku_pct":         round(haiku_calls / total * 100, 1) if total else 0.0,
            "last_model":        self._last_model,
            "last_reason":       self._last_reason,
            "est_cost_usd":      round(est_cost, 4),
        }

    # ── Internal ──────────────────────────────────────────────────────────────

    def _record(self, model: str) -> str:
        self._last_model = model
        return model

    @staticmethod
    def _resolve_alias(alias: str) -> str:
        alias = alias.lower().strip()
        if alias in ("haiku", "fast", "cheap"):
            return HAIKU_MODEL
        if alias in ("sonnet", "smart", "full"):
            return SONNET_MODEL
        return alias  # pass-through full model ID


# Module-level singleton — shared across all ClaudeAnalyzer instances
_router = ModelRouter()


def get_router() -> ModelRouter:
    return _router
