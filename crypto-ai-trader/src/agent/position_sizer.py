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
from pathlib import Path
from typing import Optional

from .market_analyzer import MarketAnalysis
from ..core.persistence import atomic_write_json, safe_read_json

logger = logging.getLogger(__name__)


class PositionSizer:
    def __init__(self, config: dict = None, models_dir: Optional[Path] = None):
        cfg = config or {}
        self._kelly_fraction    = float(cfg.get("kelly_fraction",    0.25))
        self._min_trade_usdt    = float(cfg.get("min_trade_usdt",    10.0))
        self._max_trade_usdt    = float(cfg.get("max_trade_usdt",    5000.0))
        self._fallback_risk_pct = float(cfg.get("fallback_risk_pct", 0.02))
        self._target_atr_pct    = float(cfg.get("target_atr_pct",    2.0))

        # Per-symbol running win/loss stats (persisted so Kelly survives restart)
        self._stats_path: Optional[Path] = (
            (Path(models_dir) / "position_sizer_stats.json") if models_dir else None
        )
        self._stats: dict = self._load_stats()

    # ── Persistence ───────────────────────────────────────────────────────

    def _load_stats(self) -> dict:
        if self._stats_path is None:
            return {}
        data = safe_read_json(self._stats_path)
        if isinstance(data, dict):
            logger.info("PositionSizer: restored stats for %d symbols", len(data))
            return data
        return {}

    def _save_stats(self):
        if self._stats_path is not None:
            atomic_write_json(self._stats_path, self._stats)

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
        self._save_stats()

    # ── Kelly calculation ─────────────────────────────────────────────────

    def _kelly_fraction_for(self, symbol: str) -> float:
        s = self._stats.get(symbol, {})
        wins   = s.get("wins",   0)
        losses = s.get("losses", 0)
        total  = wins + losses

        # Bayesian warm-start: blend actual data with a weak prior (5-trade
        # weight, 55% win rate, 1.5:1 win/loss → raw Kelly ≈ 25%) so cold-
        # start positions are ~5% instead of the static 2% fallback.
        PRIOR_N   = 5
        PRIOR_P   = 0.55
        PRIOR_B   = 1.5        # avg_win / avg_loss assumption

        if total == 0:
            # Fully prior-based
            raw_kelly = (PRIOR_P * PRIOR_B - (1 - PRIOR_P)) / PRIOR_B
            return max(0.0, raw_kelly * self._kelly_fraction)

        # Once we have some data, blend actual stats with the prior
        blended_wins    = wins   + PRIOR_N * PRIOR_P
        blended_losses  = losses + PRIOR_N * (1 - PRIOR_P)
        blended_total   = blended_wins + blended_losses
        p  = blended_wins / blended_total
        q  = 1.0 - p

        avg_win  = ((s.get("gain_sum", 0.0) + PRIOR_N * PRIOR_P * PRIOR_B) /
                    blended_wins)   if blended_wins  > 0 else PRIOR_B
        avg_loss = ((s.get("loss_sum", 0.0) + PRIOR_N * (1 - PRIOR_P) * 1.0) /
                    blended_losses) if blended_losses > 0 else 1.0
        b = avg_win / avg_loss if avg_loss > 0 else PRIOR_B

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

        # GARCH forward-vol adjustment (ML4T Ch.9): trim size pre-emptively when
        # the model forecasts rising volatility, even if current ATR is still calm.
        garch_adj = 1.0
        vol_ratio = getattr(analysis, "garch_vol_ratio", 1.0) or 1.0
        if vol_ratio > 1.15:        # forecast vol >15% above current → de-risk
            garch_adj = max(1.0 / vol_ratio, 0.6)
        elif vol_ratio < 0.85:      # vol expected to fall → modest size-up room
            garch_adj = min(1.1, 1.0 / vol_ratio)

        fraction = base_fraction * atr_adj * garch_adj * regime_multiplier
        fraction = min(fraction, max_position_pct)

        size_usdt = portfolio_value * fraction
        size_usdt = min(size_usdt, available_cash * 0.95)
        size_usdt = min(size_usdt, self._max_trade_usdt)
        size_usdt = max(size_usdt, 0.0)

        logger.debug(
            "PositionSizer %s: kelly=%.3f atr_adj=%.2f garch_adj=%.2f regime_mult=%.2f → %.2f USDT",
            symbol, base_fraction, atr_adj, garch_adj, regime_multiplier, size_usdt,
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
