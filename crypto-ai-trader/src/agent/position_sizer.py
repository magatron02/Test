"""
Smart Position Sizer — Kelly Criterion + ATR volatility adjustment + regime scaling.

Kelly fraction formula:
    f* = (p × b − q) / b
    p  = historical win rate
    b  = average win / average loss ratio
    q  = 1 − p

We apply fractional Kelly (f* × kelly_fraction, default 0.25) to reduce variance
(a full Kelly bet is mathematically optimal but practically too aggressive).

Final size is further adjusted by:
  - ATR scaling:   high-volatility regime → smaller position
  - Regime mult:   bear/volatile/crash    → further reduction
  - Portfolio cap: never exceed max_position_pct of total equity
  - Cash guard:    never use more than 95% of available quote balance
"""
import logging
from typing import Optional

from .market_analyzer import MarketAnalysis

logger = logging.getLogger(__name__)


class PositionSizer:
    def __init__(self, config: dict = None):
        cfg = config or {}
        self._kelly_fraction    = float(cfg.get("kelly_fraction",    0.25))
        self._min_trade_usdt    = float(cfg.get("min_trade_usdt",    10.0))
        self._max_trade_usdt    = float(cfg.get("max_trade_usdt",    5000.0))
        self._fallback_risk_pct = float(cfg.get("fallback_risk_pct", 0.02))
        self._target_atr_pct    = float(cfg.get("target_atr_pct",    2.0))

        # Per-symbol running win/loss stats
        self._stats: dict = {}

    # ── Outcome tracking ──────────────────────────────────────────────────

    def update_outcome(self, symbol: str, pnl_pct: float):
        s = self._stats.setdefault(
            symbol, {"wins": 0, "losses": 0, "gain_sum": 0.0, "loss_sum": 0.0}
        )
        if pnl_pct > 0:
            s["wins"]     += 1
            s["gain_sum"] += pnl_pct
        else:
            s["losses"]   += 1
            s["loss_sum"] += abs(pnl_pct)

    # ── Kelly calculation ─────────────────────────────────────────────────

    def _kelly_fraction_for(self, symbol: str) -> float:
        s = self._stats.get(symbol, {})
        wins   = s.get("wins",   0)
        losses = s.get("losses", 0)
        total  = wins + losses

        if total < 10:
            return self._fallback_risk_pct

        p = wins / total
        q = 1.0 - p
        avg_win  = s["gain_sum"] / wins   if wins   > 0 else 0.01
        avg_loss = s["loss_sum"] / losses if losses > 0 else 0.01
        b = avg_win / avg_loss
        kelly = (p * b - q) / b
        return max(0.0, kelly * self._kelly_fraction)

    # ── Main sizing API ───────────────────────────────────────────────────

    def compute(
        self,
        symbol: str,
        portfolio_value: float,
        analysis: MarketAnalysis,
        available_cash: float,
        regime: str = "RANGING",
        regime_multiplier: float = 1.0,
        max_position_pct: float = 0.10,
    ) -> float:
        """Return recommended position size in quote currency (USDT/THB)."""
        base_fraction = self._kelly_fraction_for(symbol)

        # ATR adjustment: scale down when volatility exceeds target
        atr_adj = 1.0
        if analysis.atr_pct > 0:
            atr_adj = min(self._target_atr_pct / analysis.atr_pct, 1.5)
            atr_adj = max(atr_adj, 0.25)

        fraction = base_fraction * atr_adj * regime_multiplier
        fraction = min(fraction, max_position_pct)

        size_usdt = portfolio_value * fraction
        size_usdt = min(size_usdt, available_cash * 0.95)
        size_usdt = min(size_usdt, self._max_trade_usdt)
        size_usdt = max(size_usdt, 0.0)

        logger.debug(
            "PositionSizer %s: kelly=%.3f atr_adj=%.2f regime_mult=%.2f → %.2f USDT",
            symbol, base_fraction, atr_adj, regime_multiplier, size_usdt,
        )
        return size_usdt

    def is_tradeable(self, size_usdt: float) -> bool:
        return size_usdt >= self._min_trade_usdt

    def win_rate(self, symbol: str) -> Optional[float]:
        s = self._stats.get(symbol, {})
        total = s.get("wins", 0) + s.get("losses", 0)
        return s["wins"] / total if total > 0 else None

    def stats_for(self, symbol: str) -> dict:
        s = self._stats.get(symbol, {})
        wins   = s.get("wins",   0)
        losses = s.get("losses", 0)
        total  = wins + losses
        return {
            "symbol":   symbol,
            "total":    total,
            "wins":     wins,
            "losses":   losses,
            "win_rate": round(wins / total, 3) if total > 0 else None,
            "kelly":    round(self._kelly_fraction_for(symbol), 4),
        }
