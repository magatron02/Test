"""
F5.3 Champion/Challenger — strategy-level A/B testing.

Defines trading strategies as portable config dicts and runs them against
real backtest data. The strategy with the best out-of-sample Sharpe is
promoted as champion. Inspired by fast-trade's declarative strategy format.

Strategy config schema
----------------------
{
    "name":          str,           # human label
    "strategy_type": str,           # "trend" | "mean_reversion" | "ichimoku" | "smc" | "dca"
    "tp_pct":        float,         # take-profit % (default 0.04)
    "sl_pct":        float,         # stop-loss    % (default 0.02)
    "min_confidence":float,         # signal gate  (default 0.58)
    "description":   str,           # optional notes
}

Usage
-----
from .champion_challenger import ChampionChallenger

cc = ChampionChallenger(symbol="BTC/USDT")
await cc.run_tournament(days=60)
print(cc.champion)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

_CHAMP_FILE = "champion_strategy.json"

# ── Built-in challenger pool ──────────────────────────────────────────────────

DEFAULT_CHALLENGERS: List[Dict[str, Any]] = [
    {
        "name": "trend-standard",
        "strategy_type": "trend",
        "tp_pct": 0.040,
        "sl_pct": 0.020,
        "min_confidence": 0.58,
        "description": "EMA trend-following, moderate TP/SL",
    },
    {
        "name": "mean-rev-tight",
        "strategy_type": "mean_reversion",
        "tp_pct": 0.025,
        "sl_pct": 0.015,
        "min_confidence": 0.60,
        "description": "Mean-reversion with tighter exits",
    },
    {
        "name": "ichimoku-wide",
        "strategy_type": "ichimoku",
        "tp_pct": 0.055,
        "sl_pct": 0.025,
        "min_confidence": 0.62,
        "description": "Ichimoku trend, wider TP for trending markets",
    },
    {
        "name": "smc-aggressive",
        "strategy_type": "smc",
        "tp_pct": 0.060,
        "sl_pct": 0.030,
        "min_confidence": 0.65,
        "description": "SMC with wider R:R, higher confidence gate",
    },
    {
        "name": "trend-conservative",
        "strategy_type": "trend",
        "tp_pct": 0.030,
        "sl_pct": 0.015,
        "min_confidence": 0.65,
        "description": "Trend-following, conservative sizing",
    },
]


# ── Core runner ───────────────────────────────────────────────────────────────

async def _run_strategy_backtest(
    symbol: str,
    candles: List[dict],
    strategy_cfg: Dict[str, Any],
) -> Dict[str, Any]:
    """Run _run_loop with a forced strategy type and return key metrics."""
    from .backtest import _run_loop
    from .risk_analytics import compute_metrics

    tp   = float(strategy_cfg.get("tp_pct", 0.040))
    sl   = float(strategy_cfg.get("sl_pct", 0.020))
    mode = "autotrade"
    strategy_override = strategy_cfg.get("strategy_type", "trend")

    metrics, _, trades, equity = _run_loop(
        symbol,
        candles,
        tp_pct=tp,
        sl_pct=sl,
        initial_capital=10_000.0,
        mode=mode,
        strategy_override=strategy_override,
    )
    analytics = compute_metrics(trades, equity, 10_000.0)

    return {
        "name":          strategy_cfg["name"],
        "strategy_type": strategy_override,
        "tp_pct":        tp,
        "sl_pct":        sl,
        "sharpe":        analytics["sharpe"],
        "sortino":       analytics["sortino"],
        "win_rate":      metrics["win_rate"],
        "total_return":  metrics["total_return_pct"],
        "max_drawdown":  metrics["max_drawdown_pct"],
        "total_trades":  metrics["total_trades"],
        "profit_factor": analytics["profit_factor"],
    }


# ── Main class ────────────────────────────────────────────────────────────────

class ChampionChallenger:
    """
    Runs a tournament of strategy configs and keeps the best one as champion.

    The current champion must be beaten by at least _MIN_SHARPE_IMPROVEMENT
    before it is replaced, preventing churn on noise.
    """

    _MIN_SHARPE_IMPROVEMENT = 0.10

    def __init__(
        self,
        symbol: str,
        challengers: Optional[List[Dict[str, Any]]] = None,
        models_dir: Optional[Path] = None,
    ):
        self.symbol = symbol
        self._challengers = challengers or DEFAULT_CHALLENGERS
        self._models_dir = models_dir or _default_models_dir()
        self._champion: Optional[Dict[str, Any]] = self._load_champion()

    @property
    def champion(self) -> Optional[Dict[str, Any]]:
        return self._champion

    async def run_tournament(
        self,
        days: int = 60,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Fetch klines, evaluate all challengers, promote winner if it beats champion.

        Returns a summary dict with all results and the current champion.
        """
        candles = await self._fetch(days, use_cache)
        if len(candles) < 100:
            return {"error": "insufficient data", "symbol": self.symbol}

        # Split in-sample (first 60%) / out-of-sample (last 40%) to avoid lookahead
        split = int(len(candles) * 0.60)
        oos_candles = candles[split:]

        results: List[Dict[str, Any]] = []
        for cfg in self._challengers:
            try:
                r = await _run_strategy_backtest(self.symbol, oos_candles, cfg)
                results.append(r)
                logger.info(
                    "C/C %s: %s sharpe=%.2f wr=%.1f%% ret=%.1f%%",
                    self.symbol, r["name"], r["sharpe"], r["win_rate"], r["total_return"],
                )
            except Exception as exc:
                logger.warning("C/C: strategy %s failed — %s", cfg["name"], exc)

        if not results:
            return {"error": "all strategies failed", "symbol": self.symbol}

        best = max(results, key=lambda r: r["sharpe"])
        champion_sharpe = (self._champion or {}).get("sharpe", -999.0)

        promoted = False
        if best["sharpe"] > champion_sharpe + self._MIN_SHARPE_IMPROVEMENT:
            self._champion = {**best, "promoted_at": datetime.utcnow().isoformat()}
            self._save_champion()
            promoted = True
            logger.info(
                "C/C: NEW CHAMPION %s (sharpe %.2f → %.2f)",
                best["name"], champion_sharpe, best["sharpe"],
            )
        else:
            logger.info(
                "C/C: champion %s retained (sharpe %.2f vs challenger %.2f)",
                (self._champion or {}).get("name", "none"), champion_sharpe, best["sharpe"],
            )

        return {
            "symbol":    self.symbol,
            "champion":  self._champion,
            "promoted":  promoted,
            "results":   sorted(results, key=lambda r: -r["sharpe"]),
            "oos_bars":  len(oos_candles),
            "run_at":    datetime.utcnow().isoformat(),
        }

    # ── Persistence ──────────────────────────────────────────────────────────

    def _champ_path(self) -> Path:
        return self._models_dir / f"champion_{self.symbol.replace('/', '')}.json"

    def _load_champion(self) -> Optional[Dict[str, Any]]:
        p = self._champ_path()
        if not p.exists():
            return None
        try:
            with open(p) as f:
                return json.load(f)
        except Exception:
            return None

    def _save_champion(self) -> None:
        p = self._champ_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w") as f:
            json.dump(self._champion, f, indent=2)

    # ── Data ─────────────────────────────────────────────────────────────────

    async def _fetch(self, days: int, use_cache: bool) -> List[dict]:
        try:
            from .kline_cache import KlineCache
            cache = KlineCache()
            return await cache.get_or_fetch(self.symbol, days=days, force_refresh=not use_cache)
        except Exception as exc:
            logger.warning("C/C: kline_cache unavailable (%s); fetching direct", exc)
            from .backtest import _fetch_real_ohlcv
            return await _fetch_real_ohlcv(self.symbol, days)


def _default_models_dir() -> Path:
    try:
        from ..core.config import settings
        return settings.models_dir
    except Exception:
        return Path("models")
