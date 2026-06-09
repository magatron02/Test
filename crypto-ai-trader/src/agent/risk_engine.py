"""
Advanced Risk Engine — portfolio-level risk management with dynamic limits.

Tracks:
  - High-water mark & current drawdown
  - Portfolio heat (total open risk as % of equity)
  - Per-symbol risk budget
  - Circuit-breaker: halts all new trades on limit breach
  - VaR / CVaR + Monte-Carlo tail-risk (F3.3)

Regime multipliers reduce/increase allowed risk based on detected market state.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np

from .var_engine import summarize as _var_summarize

logger = logging.getLogger(__name__)


@dataclass
class RiskState:
    equity: float = 0.0
    high_water_mark: float = 0.0
    current_drawdown_pct: float = 0.0
    portfolio_heat_pct: float = 0.0   # sum of open risk as % of equity
    daily_pnl: float = 0.0
    daily_pnl_pct: float = 0.0
    regime: str = "RANGING"
    circuit_open: bool = False
    circuit_reason: str = ""


class RiskEngine:
    """
    Call update() on every trading cycle to keep the risk state current,
    then call can_trade() before opening any new position.
    """

    # Risk multipliers per regime (fraction of base position size)
    _REGIME_MULT: Dict[str, float] = {
        "BULL_TREND": 1.00,
        "BEAR_TREND": 0.50,
        "RANGING":    0.80,
        "VOLATILE":   0.40,
        "CRASH":      0.10,
    }

    def __init__(self, config: dict = None):
        cfg = config or {}
        self._max_drawdown_pct   = float(cfg.get("max_drawdown_pct",   0.10))
        self._max_daily_loss_pct = float(cfg.get("max_daily_loss_pct", 0.05))
        self._max_portfolio_heat = float(cfg.get("max_portfolio_heat", 0.20))
        self._max_position_pct   = float(cfg.get("max_position_pct",   0.10))
        self._max_var_pct        = float(cfg.get("max_var_pct",        0.02))
        self._max_prob_ruin      = float(cfg.get("max_prob_ruin",      0.10))
        # Correlation guard: block a new BUY if it is too correlated with
        # the symbols already held (avoids fake diversification).
        self._max_correlation    = float(cfg.get("max_correlation",    0.80))
        self._correlation_guard  = bool(cfg.get("correlation_guard_enabled", True))

        self._high_water_mark: float = 0.0
        self._equity_history: List[Tuple[datetime, float]] = []
        self._state = RiskState()
        self._open_risks: Dict[str, float] = {}   # symbol → risk in quote currency
        self._daily_returns: List[float] = []     # for VaR/CVaR (F3.3)
        self._prev_equity: Optional[float] = None

        # F2.4 — adaptive meta-params: record the base (operator-configured)
        # limits so adaptive_adjust() can always anchor to them.
        self._base_max_drawdown_pct   = self._max_drawdown_pct
        self._base_max_var_pct        = self._max_var_pct
        self._base_max_daily_loss_pct = self._max_daily_loss_pct
        self._adaptive_mult: float = 1.0   # last applied multiplier (for dashboard)

    # ── State update ──────────────────────────────────────────────────────

    def update(
        self,
        equity: float,
        daily_pnl: float,
        open_trades: dict,
        regime: str = "RANGING",
    ):
        self._state.equity    = equity
        self._state.daily_pnl = daily_pnl
        self._state.regime    = regime

        if equity > self._high_water_mark:
            self._high_water_mark = equity
        self._state.high_water_mark = self._high_water_mark

        if self._high_water_mark > 0:
            self._state.current_drawdown_pct = (
                (self._high_water_mark - equity) / self._high_water_mark
            )

        if equity > 0:
            self._state.daily_pnl_pct = daily_pnl / equity

        # Track daily return for VaR/CVaR (F3.3)
        if self._prev_equity and self._prev_equity > 0:
            daily_ret = (equity - self._prev_equity) / self._prev_equity
            self._daily_returns.append(daily_ret)
            if len(self._daily_returns) > 365:
                self._daily_returns = self._daily_returns[-365:]
        self._prev_equity = equity

        heat = sum(self._open_risks.values()) / equity if equity > 0 else 0.0
        self._state.portfolio_heat_pct = heat

        # Rolling equity history (7-day window)
        now = datetime.now(timezone.utc)
        self._equity_history.append((now, equity))
        cutoff = now - timedelta(days=7)
        self._equity_history = [(t, e) for t, e in self._equity_history if t > cutoff]

        self._check_circuit_breaker()

    def _check_circuit_breaker(self):
        s = self._state

        # 1. Realised drawdown from high-water mark
        if s.current_drawdown_pct >= self._max_drawdown_pct:
            s.circuit_open   = True
            s.circuit_reason = (
                f"Max drawdown {s.current_drawdown_pct:.1%} exceeded "
                f"{self._max_drawdown_pct:.1%}"
            )
            return

        # 2. Intraday loss limit
        if s.equity > 0 and (s.daily_pnl / s.equity) <= -self._max_daily_loss_pct:
            s.circuit_open   = True
            s.circuit_reason = (
                f"Daily loss limit {s.daily_pnl_pct:.1%} reached "
                f"(limit={self._max_daily_loss_pct:.1%})"
            )
            return

        # 3. F3.3 — VaR / Monte-Carlo tail-risk gate (proactive, not reactive)
        #    Requires at least 20 observations so we don't trigger on noise.
        if len(self._daily_returns) >= 20:
            try:
                tail = _var_summarize(self._daily_returns)
                var    = tail.get("var_pct", 0.0)
                p_ruin = tail.get("prob_ruin", 0.0)
                if var > self._max_var_pct:
                    s.circuit_open   = True
                    s.circuit_reason = (
                        f"VaR {var:.1%} exceeds limit {self._max_var_pct:.1%} "
                        f"(tail-risk circuit)"
                    )
                    return
                if p_ruin > self._max_prob_ruin:
                    s.circuit_open   = True
                    s.circuit_reason = (
                        f"Monte Carlo ruin probability {p_ruin:.0%} exceeds "
                        f"limit {self._max_prob_ruin:.0%}"
                    )
                    return
            except Exception:
                pass   # never let VaR failure block the circuit-breaker reset

        s.circuit_open   = False
        s.circuit_reason = ""

    # ── F2.4 Adaptive meta-parameters ────────────────────────────────────

    def adaptive_adjust(self) -> float:
        """
        Recalibrate ``max_drawdown_pct``, ``max_var_pct``, and
        ``max_daily_loss_pct`` based on the rolling realised volatility of
        the equity curve (measured from ``_daily_returns``).

        Logic:
          * Compute the annualised vol of the last ≤ 60 daily returns.
          * Map it to a tightening/loosening multiplier in [0.5, 1.2]:
              - vol < 1.0 × base_var_pct → calm → loosen slightly  (×1.1)
              - 1.0 – 1.5 × base_var_pct → normal → stay at base   (×1.0)
              - 1.5 – 2.5 × base_var_pct → elevated → tighten      (×0.80)
              - > 2.5 × base_var_pct     → high-vol → tighten hard  (×0.60)
          * All adjustments are anchored to the *base* (operator-configured)
            limits, so the system can never permanently drift to laxer limits
            than the operator intended.
          * Requires ≥ 10 observations; returns 1.0 unchanged below that.

        Returns the multiplier that was applied.
        """
        if len(self._daily_returns) < 10:
            return self._adaptive_mult

        window = self._daily_returns[-60:]
        ann_vol = float(np.std(window, ddof=1) * (252 ** 0.5))

        ref = self._base_max_var_pct or 0.05
        ratio = ann_vol / ref if ref > 0 else 1.0

        if ratio < 1.0:
            mult = 1.10       # calm market: slightly loosen
        elif ratio < 1.5:
            mult = 1.00       # normal: stay at base
        elif ratio < 2.5:
            mult = 0.80       # elevated vol: tighten
        else:
            mult = 0.60       # high vol: tighten hard

        self._max_drawdown_pct   = round(self._base_max_drawdown_pct   * mult, 4)
        self._max_var_pct        = round(self._base_max_var_pct        * mult, 4)
        self._max_daily_loss_pct = round(self._base_max_daily_loss_pct * mult, 4)
        self._adaptive_mult      = mult

        logger.debug(
            "RiskEngine adaptive_adjust: ann_vol=%.3f ratio=%.2f mult=%.2f "
            "dd_pct=%.3f var_pct=%.3f",
            ann_vol, ratio, mult, self._max_drawdown_pct, self._max_var_pct,
        )
        return mult

    # ── Trade gating ──────────────────────────────────────────────────────

    def can_trade(self, new_trade_risk: float = 0.0) -> Tuple[bool, str]:
        """Returns (allowed, reason). Call before executing any new BUY."""
        if self._state.circuit_open:
            return False, f"Circuit breaker: {self._state.circuit_reason}"

        equity = self._state.equity or 1.0
        projected_heat = (sum(self._open_risks.values()) + new_trade_risk) / equity
        if projected_heat > self._max_portfolio_heat:
            return False, (
                f"Portfolio heat {projected_heat:.1%} would exceed "
                f"{self._max_portfolio_heat:.1%}"
            )

        return True, ""

    # ── Correlation guard ─────────────────────────────────────────────────

    @staticmethod
    def _pearson(a: List[float], b: List[float]) -> Optional[float]:
        """Pearson correlation of two return series over their common tail."""
        n = min(len(a), len(b))
        if n < 5:
            return None
        x, y = a[-n:], b[-n:]
        mx = sum(x) / n
        my = sum(y) / n
        cov = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
        vx = sum((xi - mx) ** 2 for xi in x)
        vy = sum((yi - my) ** 2 for yi in y)
        if vx <= 0 or vy <= 0:
            return None
        return cov / (vx ** 0.5 * vy ** 0.5)

    def check_correlation(
        self,
        candidate_returns: List[float],
        portfolio_returns: Dict[str, List[float]],
    ) -> Tuple[bool, str, Optional[float]]:
        """Block a new BUY whose avg correlation with held symbols is too high.

        Returns ``(allowed, reason, avg_corr)``. When the guard is disabled, no
        held positions, or insufficient history exist, it allows the trade.
        """
        if not self._correlation_guard or not portfolio_returns:
            return True, "", None

        corrs = []
        for sym, rets in portfolio_returns.items():
            c = self._pearson(candidate_returns, rets)
            if c is not None:
                corrs.append(abs(c))
        if not corrs:
            return True, "", None

        avg_corr = sum(corrs) / len(corrs)
        if avg_corr > self._max_correlation:
            return False, (
                f"Correlation {avg_corr:.2f} with held positions exceeds "
                f"{self._max_correlation:.2f}"
            ), avg_corr
        return True, "", avg_corr

    # ── Position tracking ─────────────────────────────────────────────────

    def register_open_trade(self, symbol: str, risk_amount: float):
        """risk_amount = quote-currency value at risk for this position."""
        self._open_risks[symbol] = risk_amount

    def deregister_trade(self, symbol: str):
        self._open_risks.pop(symbol, None)

    # ── Helpers ───────────────────────────────────────────────────────────

    def get_regime_multiplier(self, regime: str) -> float:
        return self._REGIME_MULT.get(regime, 0.80)

    @property
    def state(self) -> RiskState:
        return self._state

    @property
    def max_position_pct(self) -> float:
        return self._max_position_pct

    def summary(self) -> dict:
        s = self._state
        result = {
            "equity":           round(s.equity, 2),
            "high_water_mark":  round(s.high_water_mark, 2),
            "drawdown_pct":     round(s.current_drawdown_pct, 4),
            "portfolio_heat":   round(s.portfolio_heat_pct, 4),
            "daily_pnl":        round(s.daily_pnl, 2),
            "daily_pnl_pct":    round(s.daily_pnl_pct, 4),
            "circuit_open":     s.circuit_open,
            "circuit_reason":   s.circuit_reason,
            "regime":           s.regime,
            "limits": {
                "max_drawdown_pct":   self._max_drawdown_pct,
                "max_daily_loss_pct": self._max_daily_loss_pct,
                "max_var_pct":        self._max_var_pct,
                "max_prob_ruin":      self._max_prob_ruin,
            },
            "adaptive_mult": round(self._adaptive_mult, 3),
        }
        # F3.3 — VaR/CVaR + Monte-Carlo tail risk
        try:
            result["tail_risk"] = _var_summarize(self._daily_returns)
        except Exception:
            result["tail_risk"] = {}
        return result
