"""
F2.3 — Trade Journal / Memory.

A lightweight learning layer that turns *closed* trades into actionable
memory.  Every closed trade is reduced to a **setup signature**
(regime × strategy × confidence-band × RSI-signal) and its realised P&L is
folded into a running win-rate / expectancy estimate for that signature.

Before a new trade is taken, the engine can ``recall()`` the historical
performance of the matching signature and obtain a *bias* in ``[-1, +1]``:

    bias > 0   → this setup has been profitable, lean in
    bias < 0   → this setup has bled money, lean out (or veto)

The bias is deliberately conservative — it only carries weight once at least
``min_samples`` matching trades exist, so the AI never over-fits to a single
lucky or unlucky outcome.  This keeps the feedback loop stable while still
letting the system *remember* what has and hasn't worked.

No external dependencies — pure stdlib so it stays fast and testable.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Confidence banding ────────────────────────────────────────────────────────

def _conf_band(confidence: float) -> str:
    """Bucket a raw confidence into low / mid / high bands."""
    if confidence < 0.60:
        return "low"
    if confidence < 0.75:
        return "mid"
    return "high"


def _signature(regime: str, strategy: str, conf_band: str, rsi_signal: str) -> str:
    """Stable, human-readable key for a setup signature."""
    return f"{regime}|{strategy}|{conf_band}|{rsi_signal}"


# ── Per-signature aggregate ───────────────────────────────────────────────────

@dataclass
class SetupStats:
    n: int = 0
    wins: int = 0
    sum_pnl: float = 0.0          # cumulative pnl_pct
    sum_pnl_sq: float = 0.0       # for variance / stability
    recent: List[float] = field(default_factory=list)   # last N pnl_pct

    def update(self, pnl_pct: float, recent_cap: int = 20):
        self.n += 1
        if pnl_pct > 0:
            self.wins += 1
        self.sum_pnl += pnl_pct
        self.sum_pnl_sq += pnl_pct * pnl_pct
        self.recent.append(pnl_pct)
        if len(self.recent) > recent_cap:
            self.recent = self.recent[-recent_cap:]

    @property
    def win_rate(self) -> float:
        return self.wins / self.n if self.n else 0.0

    @property
    def avg_pnl(self) -> float:
        return self.sum_pnl / self.n if self.n else 0.0

    @property
    def expectancy(self) -> float:
        """Average pnl_pct per trade — the bottom line for a setup."""
        return self.avg_pnl

    def as_dict(self) -> dict:
        return {
            "n":          self.n,
            "win_rate":   round(self.win_rate, 4),
            "avg_pnl":    round(self.avg_pnl, 4),
            "expectancy": round(self.expectancy, 4),
        }


# ── Journal ───────────────────────────────────────────────────────────────────

class TradeJournal:
    """
    In-memory trade memory with optional DB hydration.

    Usage
    -----
    >>> j = TradeJournal(min_samples=5)
    >>> j.record(regime="RANGING", strategy="DCA", confidence=0.7,
    ...          rsi_signal="OVERSOLD", pnl_pct=1.2)
    >>> j.recall(regime="RANGING", strategy="DCA", confidence=0.7,
    ...          rsi_signal="OVERSOLD")
    {'n': 1, 'win_rate': 1.0, 'avg_pnl': 1.2, 'expectancy': 1.2,
     'bias': 0.0, 'confident': False}
    """

    def __init__(self, min_samples: int = 5, max_records: int = 5_000):
        self._min_samples = int(min_samples)
        self._max_records = int(max_records)
        self._stats: Dict[str, SetupStats] = defaultdict(SetupStats)
        self._log: List[dict] = []          # raw closed-trade log (capped)
        self._total = 0

    # ── Recording ─────────────────────────────────────────────────────────

    def record(
        self,
        *,
        regime: str,
        strategy: str,
        confidence: float,
        rsi_signal: str,
        pnl_pct: float,
    ) -> None:
        """Fold one closed trade into memory."""
        band = _conf_band(float(confidence))
        sig  = _signature(regime or "UNKNOWN", strategy or "UNKNOWN",
                          band, rsi_signal or "NEUTRAL")
        self._stats[sig].update(float(pnl_pct))
        self._total += 1
        self._log.append({
            "signature":  sig,
            "regime":     regime,
            "strategy":   strategy,
            "conf_band":  band,
            "rsi_signal": rsi_signal,
            "pnl_pct":    round(float(pnl_pct), 4),
        })
        if len(self._log) > self._max_records:
            self._log = self._log[-self._max_records:]

    # ── Recall ────────────────────────────────────────────────────────────

    def recall(
        self,
        *,
        regime: str,
        strategy: str,
        confidence: float,
        rsi_signal: str,
    ) -> dict:
        """
        Look up the historical performance of a candidate setup.

        Returns a dict with the matched-signature stats plus:
          * ``bias``       — float in [-1, +1]; sign follows expectancy,
                             magnitude scales with win-rate distance from 0.5.
          * ``confident``  — True once ``n >= min_samples`` (bias is trustworthy).
          * ``veto``       — True when the setup has a *statistically* losing
                             record (confident, win_rate < 0.5 *and*
                             expectancy < 0); callers may block such trades.
        """
        band = _conf_band(float(confidence))
        sig  = _signature(regime or "UNKNOWN", strategy or "UNKNOWN",
                          band, rsi_signal or "NEUTRAL")
        st = self._stats.get(sig)
        if st is None or st.n == 0:
            return {"n": 0, "win_rate": 0.0, "avg_pnl": 0.0, "expectancy": 0.0,
                    "bias": 0.0, "confident": False, "veto": False}

        confident = st.n >= self._min_samples
        # Bias: direction from expectancy, magnitude from win-rate edge.
        # Damped while we are below the confidence threshold so a handful of
        # early trades cannot swing the engine hard either way.
        edge = (st.win_rate - 0.5) * 2.0           # [-1, +1]
        direction = 1.0 if st.expectancy >= 0 else -1.0
        magnitude = min(abs(edge), 1.0)
        bias = direction * magnitude
        if not confident:
            bias *= st.n / self._min_samples       # linear ramp-in

        veto = bool(confident and st.win_rate < 0.5 and st.expectancy < 0)

        out = st.as_dict()
        out.update({
            "bias":      round(bias, 4),
            "confident": confident,
            "veto":      veto,
        })
        return out

    # ── Hydration from DB ─────────────────────────────────────────────────

    def load_from_db(self, session_factory, trade_model, *, limit: int = 5_000) -> int:
        """
        Rebuild memory from previously-closed trades on startup.

        ``regime`` is best-effort: it is read from the trade's ``indicators``
        JSON when present (the live path stores it there), otherwise falls back
        to ``UNKNOWN``.  Returns the number of trades hydrated.
        """
        db = session_factory()
        loaded = 0
        try:
            # Select only the columns we consume. This keeps hydration working
            # even if the physical table has drifted from the ORM model (e.g. a
            # column added to the model but not yet migrated into an old DB).
            rows = (
                db.query(
                    trade_model.strategy,
                    trade_model.confidence,
                    trade_model.pnl_pct,
                    trade_model.indicators,
                )
                  .filter(trade_model.status == "closed",
                          trade_model.pnl_pct.isnot(None))
                  .order_by(trade_model.closed_at.asc())
                  .limit(limit)
                  .all()
            )
            for strategy, confidence, pnl_pct, indicators in rows:
                ind = indicators or {}
                regime     = ind.get("regime", "UNKNOWN") if isinstance(ind, dict) else "UNKNOWN"
                rsi_signal = ind.get("rsi_signal", "NEUTRAL") if isinstance(ind, dict) else "NEUTRAL"
                self.record(
                    regime=regime,
                    strategy=strategy or "UNKNOWN",
                    confidence=float(confidence or 0.0),
                    rsi_signal=rsi_signal,
                    pnl_pct=float(pnl_pct),
                )
                loaded += 1
        except Exception as exc:                       # pragma: no cover
            logger.warning("TradeJournal: DB hydration failed — %s", exc)
        finally:
            db.close()
        if loaded:
            logger.info("TradeJournal: hydrated %d closed trades into memory", loaded)
        return loaded

    # ── Introspection ─────────────────────────────────────────────────────

    def best_setups(self, top: int = 5, min_n: Optional[int] = None) -> List[dict]:
        """Top setups by expectancy (filtered to those with enough samples)."""
        floor = self._min_samples if min_n is None else min_n
        ranked = [
            {"signature": sig, **st.as_dict()}
            for sig, st in self._stats.items() if st.n >= floor
        ]
        ranked.sort(key=lambda d: d["expectancy"], reverse=True)
        return ranked[:top]

    def worst_setups(self, top: int = 5, min_n: Optional[int] = None) -> List[dict]:
        """Bottom setups by expectancy — the ones to avoid or veto."""
        floor = self._min_samples if min_n is None else min_n
        ranked = [
            {"signature": sig, **st.as_dict()}
            for sig, st in self._stats.items() if st.n >= floor
        ]
        ranked.sort(key=lambda d: d["expectancy"])
        return ranked[:top]

    def summary(self) -> dict:
        """Dashboard-friendly snapshot of trade memory."""
        confident = [s for s in self._stats.values() if s.n >= self._min_samples]
        overall_wr = (
            sum(s.wins for s in self._stats.values())
            / self._total if self._total else 0.0
        )
        return {
            "total_trades":     self._total,
            "distinct_setups":  len(self._stats),
            "confident_setups": len(confident),
            "overall_win_rate": round(overall_wr, 4),
            "min_samples":      self._min_samples,
            "best":             self.best_setups(top=3),
            "worst":            self.worst_setups(top=3),
        }
