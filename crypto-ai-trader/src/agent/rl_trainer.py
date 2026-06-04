"""
Reinforcement Learning strategy optimizer — multi-armed bandit (UCB1).

Each "arm" is a (strategy, regime) pair:
  strategies × regimes = 3 × 5 = 15 arms

Reward = realised PnL % (normalised to [-1, 1]).

UCB1 formula:
    UCB(a) = mean_reward(a) + C × sqrt(log(total_pulls) / pulls(a))

On every trade close the arm is updated and StrategyManager weights are
recalculated so the live system naturally shifts towards strategies that
are actually profitable in the current regime.

Arm state is persisted to disk so learning survives restarts.
"""
import logging
import math
import pickle
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

from .strategy_manager import StrategyManager

logger = logging.getLogger(__name__)

STRATEGIES = ["dca", "trend", "mean_reversion", "ichimoku", "smc"]
REGIMES    = ["BULL_TREND", "BEAR_TREND", "RANGING", "VOLATILE", "CRASH"]


class BanditArm:
    __slots__ = ("n", "reward_sum")

    def __init__(self):
        self.n          = 0
        self.reward_sum = 0.0

    @property
    def mean(self) -> float:
        return self.reward_sum / self.n if self.n > 0 else 0.0

    def ucb(self, total_pulls: int, c: float = 1.5) -> float:
        if self.n == 0:
            return float("inf")   # force exploration of untried arms
        return self.mean + c * math.sqrt(math.log(max(total_pulls, 1)) / self.n)

    def update(self, reward: float):
        self.n          += 1
        self.reward_sum += reward


class RLTrainer:
    def __init__(self, models_dir: Optional[Path] = None):
        # Reinitialise arms whenever STRATEGIES/REGIMES expands.
        # Load from disk then add any new arms not in the saved state.
        base_arms: Dict[Tuple[str, str], BanditArm] = {
            (s, r): BanditArm() for s in STRATEGIES for r in REGIMES
        }
        self._arms: Dict[Tuple[str, str], BanditArm] = base_arms
        self._total_pulls = 0
        self._pending: Dict[int, Tuple[str, str]] = {}  # trade_id → (strategy, regime)
        self._models_dir = models_dir
        self._stats = {"total_updates": 0, "last_updated": None}
        self._load()

    # ── Persistence ───────────────────────────────────────────────────────

    def _rl_path(self) -> Optional[Path]:
        return (self._models_dir / "rl_bandit.pkl") if self._models_dir else None

    def _load(self):
        p = self._rl_path()
        if p and p.exists():
            try:
                with open(p, "rb") as f:
                    data = pickle.load(f)
                saved_arms = data.get("arms", {})
                # Merge: keep existing learned arms, add any new (strategy,regime) pairs
                for key, arm in saved_arms.items():
                    if key in self._arms:
                        self._arms[key] = arm
                self._total_pulls = data.get("total_pulls", 0)
                logger.info("Loaded RL bandit state (%d pulls)", self._total_pulls)
            except Exception as e:
                logger.warning("Could not load RL state: %s", e)

    def _save(self):
        p = self._rl_path()
        if not p:
            return
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "wb") as f:
                pickle.dump({"arms": self._arms, "total_pulls": self._total_pulls}, f)
        except Exception as e:
            logger.warning("Could not save RL state: %s", e)

    # ── Public API ────────────────────────────────────────────────────────

    def record_trade(self, trade_id: int, strategy: str, regime: str):
        """Call when a trade is opened so we know which arm to update later."""
        self._pending[trade_id] = (strategy, regime)

    def update_outcome(
        self,
        trade_id: int,
        pnl_pct: float,
        strategy_manager: StrategyManager,
    ):
        """Call when a trade closes. Updates bandit + pushes new weights."""
        key = self._pending.pop(trade_id, None)
        if key is None:
            return

        strategy, regime = key
        arm = self._arms.get(key)
        if arm:
            # Normalise reward: pnl_pct clipped to ±10% → [-1, 1]
            reward = max(-1.0, min(1.0, pnl_pct / 10.0))
            arm.update(reward)
            self._total_pulls += 1
            self._stats["total_updates"] += 1
            self._stats["last_updated"]   = datetime.utcnow().isoformat()
            logger.debug("RL update arm=(%s,%s) reward=%.3f total_pulls=%d",
                         strategy, regime, reward, self._total_pulls)

        self._push_weights(regime, strategy_manager)
        self._save()

    def select_strategy(self, regime: str) -> str:
        """UCB1 arm selection — returns the strategy name for this regime."""
        best, best_ucb = "hybrid", -float("inf")
        for s in STRATEGIES:
            arm = self._arms.get((s, regime))
            if arm:
                u = arm.ucb(max(self._total_pulls, 1))
                if u > best_ucb:
                    best_ucb = u
                    best = s
        return best

    def get_arm_stats(self, regime: str) -> dict:
        return {
            s: {
                "n":    self._arms[(s, regime)].n,
                "mean": round(self._arms[(s, regime)].mean, 4),
            }
            for s in STRATEGIES
        }

    @property
    def stats(self) -> dict:
        return dict(self._stats)

    # ── Internal ─────────────────────────────────────────────────────────

    def _push_weights(self, regime: str, strategy_manager: StrategyManager):
        """Translate arm means into StrategyManager weights (sum to ~1)."""
        floor = 0.10
        raw = {s: max(self._arms[(s, regime)].mean + 1.0, floor)
               for s in STRATEGIES if (s, regime) in self._arms}
        if not raw:
            return
        total = sum(raw.values())
        weights = {s: raw[s] / total for s in raw}
        strategy_manager.update_weights(weights)
        logger.debug("RL pushed weights for regime=%s: %s", regime,
                     {s: f"{v:.3f}" for s, v in weights.items()})
