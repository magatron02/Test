"""Multi-agent consensus panel — Technical + Sentiment + Risk agents vote
before the final trading decision is made.

Inspired by virattt/ai-hedge-fund: each agent specialises in one domain;
the Panel synthesises their votes into a weighted consensus signal that
acts as a pre-flight gate alongside the existing 7-gate risk pipeline.

Weights: Technical 40% · Sentiment 30% · Risk 30%
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Literal, Optional

import numpy as np

AgentAction   = Literal["BUY",     "SELL",    "HOLD"]
SentimentCall = Literal["BULLISH", "BEARISH", "NEUTRAL"]
RiskStatus    = Literal["GREEN",   "YELLOW",  "RED"]

_WEIGHTS = {"Technical": 0.40, "Sentiment": 0.30, "Risk": 0.30}

# Map every vote label to a directional float (-1 .. +1).
# Risk agent is NEUTRAL or NEGATIVE only — GREEN=0.0 so the Risk agent never
# nudges toward BUY (it only vetoes or stays out of the way).
_DIR = {
    "BUY": 1.0, "SELL": -1.0, "HOLD": 0.0,
    "BULLISH": 1.0, "BEARISH": -1.0, "NEUTRAL": 0.0,
    "GREEN": 0.0, "YELLOW": 0.0, "RED": -1.0,
}

# Maximum positive weighted-score achievable (Risk contributes 0 or negative).
# Used to normalise displayed confidence so operators see a proper 0-100% figure.
_DISPLAY_MAX: float = _WEIGHTS["Technical"] + _WEIGHTS["Sentiment"]  # 0.70


@dataclass
class AgentVote:
    agent:      str
    vote:       str
    confidence: float
    score:      float
    signals:    List[str] = field(default_factory=list)


@dataclass
class PanelConsensus:
    action:         AgentAction
    confidence:     float
    weighted_score: float
    votes:          List[AgentVote]
    veto:           Optional[str] = None   # non-None when Risk RED blocks trade
    agree:          bool = False           # all 3 point same direction


# ── Individual agents ─────────────────────────────────────────────────────────

class TechnicalAgent:
    """Price-action, indicator and pattern analysis → BUY / SELL / HOLD."""

    def analyze(self, features: dict) -> AgentVote:
        f = features
        score = 0.0
        sigs: list = []

        # RSI
        rsi = float(f.get("rsi", 50) or 50)
        if rsi < 32:
            score += 0.30; sigs.append(f"RSI oversold ({rsi:.0f})")
        elif rsi < 40:
            score += 0.15; sigs.append(f"RSI low ({rsi:.0f})")
        elif rsi > 68:
            score -= 0.30; sigs.append(f"RSI overbought ({rsi:.0f})")
        elif rsi > 60:
            score -= 0.15; sigs.append(f"RSI high ({rsi:.0f})")

        # MACD histogram
        if float(f.get("macd_hist", 0) or 0) > 0:
            score += 0.12; sigs.append("MACD positive")
        else:
            score -= 0.12; sigs.append("MACD negative")

        # Smart Money Concepts
        if f.get("smc_buy"):
            score += 0.22; sigs.append("SMC Buy Zone")
        if f.get("smc_sell"):
            score -= 0.22; sigs.append("SMC Sell Zone")

        # Supertrend
        if f.get("supertrend_buy"):
            score += 0.15; sigs.append("Supertrend bullish")

        # Bollinger position
        bb = float(f.get("bb_position", 0.5) or 0.5)
        if bb < 0.15:
            score += 0.12; sigs.append("Near lower BB")
        elif bb > 0.85:
            score -= 0.12; sigs.append("Near upper BB")

        # Kalman filter velocity
        kv = float(f.get("kalman_velocity", 0) or 0)
        score += float(np.clip(kv * 3.0, -0.12, 0.12))

        # RSI divergence
        if f.get("rsi_div_bull"):
            score += 0.10; sigs.append("Bullish RSI div")
        if f.get("rsi_div_bear"):
            score -= 0.10; sigs.append("Bearish RSI div")

        # Ichimoku
        if f.get("ichimoku_bull"):
            score += 0.08; sigs.append("Ichimoku bullish")

        score = float(np.clip(score, -1.0, 1.0))
        vote: AgentAction = "BUY" if score > 0.18 else "SELL" if score < -0.18 else "HOLD"
        return AgentVote("Technical", vote, round(min(abs(score) * 1.2, 1.0), 3),
                         round(score, 3), sigs[:4])


class SentimentAgent:
    """Macro sentiment — Fear & Greed, funding, flows → BULLISH / BEARISH / NEUTRAL."""

    def analyze(self, features: dict) -> AgentVote:
        f = features
        score = 0.0
        sigs: list = []

        # Fear & Greed — contrarian at extremes
        fng = float(f.get("fng_value", 0.5) or 0.5)  # already 0-1 from Phase 1
        fng_int = int(fng * 100)
        if fng < 0.20:
            score += 0.35; sigs.append(f"Extreme Fear F&G={fng_int}")
        elif fng < 0.35:
            score += 0.18; sigs.append(f"Fear F&G={fng_int}")
        elif fng > 0.80:
            score -= 0.30; sigs.append(f"Extreme Greed F&G={fng_int}")
        elif fng > 0.65:
            score -= 0.15; sigs.append(f"Greed F&G={fng_int}")

        # F&G momentum (falling sentiment = contrarian opportunity)
        fng_mom = float(f.get("fng_momentum", 0) or 0)
        if fng_mom < -0.10:
            score += 0.10; sigs.append("Sentiment deteriorating (contrarian)")

        # Perpetual funding rate
        funding = float(f.get("funding_rate_hist", 0) or 0)
        if funding < -0.0003:
            score += 0.22; sigs.append(f"Neg funding {funding*100:.3f}%")
        elif funding > 0.0015:
            score -= 0.22; sigs.append(f"High funding {funding*100:.3f}%")
        elif funding > 0.0005:
            score -= 0.10

        # Taker buy/sell ratio
        taker = float(f.get("taker_buy_sell_ratio", 1.0) or 1.0)
        if taker > 1.25:
            score += 0.12; sigs.append(f"Taker buy {taker:.2f}×")
        elif taker < 0.80:
            score -= 0.12; sigs.append(f"Taker sell {taker:.2f}×")

        # Order book imbalance
        imb = float(f.get("book_imbalance", 0.5) or 0.5)
        if imb > 0.62:
            score += 0.08
        elif imb < 0.38:
            score -= 0.08

        score = float(np.clip(score, -1.0, 1.0))
        vote: SentimentCall = ("BULLISH" if score > 0.12 else
                               "BEARISH" if score < -0.12 else "NEUTRAL")
        return AgentVote("Sentiment", vote, round(min(abs(score) * 1.3, 1.0), 3),
                         round(score, 3), sigs[:4])


class RiskAgent:
    """Portfolio risk conditions → GREEN / YELLOW / RED.  RED vetoes all buys."""

    def analyze(self, features: dict, risk_state: dict, regime: str) -> AgentVote:
        f = features
        score = 0.0
        sigs: list = []

        # Market regime
        regime_score = {
            "BULL_TREND": +0.20, "RANGING": 0.00,
            "BEAR_TREND": -0.20, "VOLATILE": -0.28, "CRASH": -0.58,
        }
        score += regime_score.get((regime or "").upper(), 0.0)
        if (regime or "").upper() in ("VOLATILE", "CRASH", "BEAR_TREND"):
            sigs.append(f"Regime {regime}")

        # Portfolio heat
        heat = float(risk_state.get("portfolio_heat", 0) or 0)
        if heat > 0.18:
            score -= 0.35; sigs.append(f"High heat {heat:.0%}")
        elif heat > 0.12:
            score -= 0.15; sigs.append(f"Heat {heat:.0%}")

        # Drawdown
        dd = float(risk_state.get("current_drawdown", 0) or 0)
        if dd > 0.08:
            score -= 0.40; sigs.append(f"Drawdown {dd:.0%}")
        elif dd > 0.04:
            score -= 0.20; sigs.append(f"DD {dd:.0%}")

        # GARCH volatility spike
        garch = float(f.get("garch_vol_ratio", 1.0) or 1.0)
        if garch > 2.5:
            score -= 0.18; sigs.append(f"Vol spike ×{garch:.1f}")
        elif garch > 1.5:
            score -= 0.08

        if not sigs:
            sigs.append("Risk conditions normal")

        score = float(np.clip(score, -1.0, 1.0))
        vote: RiskStatus = "GREEN" if score > -0.10 else "RED" if score < -0.38 else "YELLOW"
        return AgentVote("Risk", vote, round(min(abs(score) * 1.1, 1.0), 3),
                         round(score, 3), sigs[:4])


# ── Panel synthesiser ─────────────────────────────────────────────────────────

class AgentPanel:
    """Run all three agents and produce a weighted consensus."""

    def __init__(self):
        self.technical = TechnicalAgent()
        self.sentiment = SentimentAgent()
        self.risk      = RiskAgent()

    def vote(
        self,
        features:   dict,
        risk_state: dict,
        regime:     str,
    ) -> PanelConsensus:
        tech = self.technical.analyze(features)
        sent = self.sentiment.analyze(features)
        risk = self.risk.analyze(features, risk_state, regime)
        votes = [tech, sent, risk]

        # Risk RED → veto any directional trade
        veto: Optional[str] = None
        if risk.vote == "RED":
            veto = f"Risk VETO — {', '.join(risk.signals[:2])}"

        # Weighted directional score
        weighted = sum(
            _WEIGHTS.get(v.agent, 0.33) * _DIR.get(v.vote, 0) * v.confidence
            for v in votes
        )

        if veto:
            action: AgentAction = "HOLD"
        else:
            action = "BUY" if weighted > 0.18 else "SELL" if weighted < -0.18 else "HOLD"

        # Normalise confidence to [0, 1] against _DISPLAY_MAX so the UI shows
        # a meaningful percentage instead of a structurally-capped raw score.
        confidence = float(np.clip(abs(weighted) / max(_DISPLAY_MAX, 1e-9), 0.0, 1.0))

        # UNANIMOUS: Tech + Sentiment agree (Risk is excluded — it is neutral/veto-only)
        tech_dir = _DIR.get(next((v.vote for v in votes if v.agent == "Technical"), "HOLD"), 0)
        sent_dir = _DIR.get(next((v.vote for v in votes if v.agent == "Sentiment"), "NEUTRAL"), 0)
        agree = (tech_dir > 0 and sent_dir > 0) or (tech_dir < 0 and sent_dir < 0)

        return PanelConsensus(
            action         = action,
            confidence     = round(confidence, 3),
            weighted_score = round(float(weighted), 3),
            votes          = votes,
            veto           = veto,
            agree          = agree,
        )

    @staticmethod
    def to_dict(c: PanelConsensus) -> dict:
        return {
            "action":         c.action,
            "confidence":     c.confidence,
            "weighted_score": c.weighted_score,
            "agree":          c.agree,
            "veto":           c.veto,
            "votes": [
                {
                    "agent":      v.agent,
                    "vote":       v.vote,
                    "confidence": v.confidence,
                    "score":      v.score,
                    "signals":    v.signals,
                }
                for v in c.votes
            ],
        }
