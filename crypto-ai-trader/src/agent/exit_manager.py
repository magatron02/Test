"""
Adaptive Dynamic SL/TP — F2.2 (Lunai v2.0.0 "Judgment").

Replaces fixed-percentage stops with ATR-scaled exits that adapt to the
current market regime.  Regime parameters follow the principle:
  - Trending:  wide stops to survive retracements, larger R:R target
  - Ranging:   tight stops, modest TP near the range boundary
  - Volatile:  tight stops (preserve capital), moderate TP
  - Crash:     minimal stop buffer — exit fast if wrong

Entry-point ATR% is supplied by the MarketAnalysis object so no extra
data fetching is needed.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ATR multiplier for initial stop-loss distance
_SL_ATR_K: dict = {
    "BULL_TREND": 2.0,
    "BEAR_TREND": 1.5,
    "RANGING":    1.5,
    "VOLATILE":   1.5,
    "CRASH":      1.0,
}

# Take-profit expressed as a multiple of the SL distance (R:R ratio)
_TP_RR: dict = {
    "BULL_TREND": 3.0,
    "BEAR_TREND": 2.0,
    "RANGING":    2.0,
    "VOLATILE":   1.5,
    "CRASH":      1.5,
}

# Trailing stop activates when unrealised profit reaches N × ATR%
_TRAIL_ACTIVATE_K: dict = {
    "BULL_TREND": 1.0,
    "BEAR_TREND": 0.5,
    "RANGING":    0.5,
    "VOLATILE":   0.75,
    "CRASH":      0.5,
}

_DEFAULT_SL_PCT    = 0.030  # 3% hard floor for SL
_DEFAULT_TP_PCT    = 0.060  # 6% hard floor for TP
_MIN_SL_PCT        = 0.005  # never tighter than 0.5%
_MIN_TP_PCT        = 0.010  # never tighter than 1%


class ExitManager:
    """Computes and checks ATR-based dynamic SL/TP + trailing stop."""

    def compute_exits(
        self,
        entry_price: float,
        atr_pct: float,        # ATR expressed as % of price (e.g. 1.5 = 1.5%)
        regime: str,
        sl_mult_override: Optional[float] = None,
    ) -> dict:
        """Return a dict with sl_pct, tp_pct, trail_activate_pct, trail_pct.

        All values are fractions (0.03 = 3%), ready to multiply against price.

        ``sl_mult_override`` replaces the regime table entry when provided —
        used by the walk-forward optimizer to apply its data-driven multiplier.
        The R:R and trail-activation ratios remain regime-specific so stop placement
        changes without collapsing the profit structure.
        """
        k_sl    = sl_mult_override if sl_mult_override is not None else _SL_ATR_K.get(regime, 1.5)
        rr      = _TP_RR.get(regime, 2.0)
        k_trail = _TRAIL_ACTIVATE_K.get(regime, 0.75)

        raw_atr = atr_pct / 100.0  # convert % → fraction

        sl_pct             = max(k_sl * raw_atr, _MIN_SL_PCT)
        tp_pct             = max(sl_pct * rr, _MIN_TP_PCT)
        trail_activate_pct = max(k_trail * raw_atr, _MIN_SL_PCT)
        trail_pct          = sl_pct  # trail width mirrors SL width

        return {
            "sl_pct":             round(sl_pct, 5),
            "tp_pct":             round(tp_pct, 5),
            "trail_activate_pct": round(trail_activate_pct, 5),
            "trail_pct":          round(trail_pct, 5),
        }

    def attach_exits(
        self,
        trade_data: dict,
        entry_price: float,
        atr_pct: float,
        regime: str,
        sl_mult_override: Optional[float] = None,
    ) -> dict:
        """Enrich a trade_data dict with ATR-based SL/TP price levels.

        Writes keys: atr_sl_price, atr_tp_price, atr_trail_activate_pct,
        atr_trail_pct, atr_regime.  Also overwrites stop_loss_price and
        take_profit_price so the rest of the system sees the dynamic values.
        """
        exits = self.compute_exits(entry_price, atr_pct, regime, sl_mult_override)

        sl_price = entry_price * (1.0 - exits["sl_pct"])
        tp_price = entry_price * (1.0 + exits["tp_pct"])

        trade_data.update({
            "atr_sl_price":           sl_price,
            "atr_tp_price":           tp_price,
            "atr_trail_activate_pct": exits["trail_activate_pct"],
            "atr_trail_pct":          exits["trail_pct"],
            "atr_regime":             regime,
            # Overwrite the fixed-% levels so existing exit-check code uses ATR levels
            "stop_loss_price":        sl_price,
            "take_profit_price":      tp_price,
        })
        logger.debug(
            "ATR exits for %s @ %.4f [%s]: SL=%.4f (%.2f%%) TP=%.4f (%.2f%%)",
            trade_data.get("symbol", "?"), entry_price, regime,
            sl_price, exits["sl_pct"] * 100,
            tp_price, exits["tp_pct"] * 100,
        )
        return trade_data

    def check_exit(
        self,
        trade: dict,
        price: float,
        atr_pct: float,
        regime: str,
    ) -> Optional[str]:
        """Return a human-readable exit reason, or None if no exit triggered.

        Also updates high_water and atr_trailing_sl in-place so the caller
        (ai_trader._check_exit_conditions) can check on every tick without
        re-computing.
        """
        entry = trade["price"]

        # ── 1. ATR stop-loss ────────────────────────────────────────────────
        sl_price = trade.get("atr_sl_price") or trade.get("stop_loss_price")
        if sl_price and price <= sl_price:
            return f"ATR SL ({price:.4f} ≤ {sl_price:.4f})"

        # ── 2. ATR trailing stop ────────────────────────────────────────────
        exits = self.compute_exits(entry, atr_pct, regime)
        trail_act = exits["trail_activate_pct"]
        trail_pct = exits["trail_pct"]

        hw = max(trade.get("high_water", entry), price)
        trade["high_water"] = hw

        profit_frac = (hw - entry) / entry if entry else 0.0
        if profit_frac >= trail_act:
            new_trail = hw * (1.0 - trail_pct)
            old_trail = trade.get("atr_trailing_sl")
            if old_trail is None or new_trail > old_trail:
                trade["atr_trailing_sl"] = new_trail

        atr_trail = trade.get("atr_trailing_sl")
        if atr_trail and price <= atr_trail:
            return f"ATR trail ({price:.4f} ≤ {atr_trail:.4f})"

        # ── 3. ATR take-profit ──────────────────────────────────────────────
        tp_price = trade.get("atr_tp_price") or trade.get("take_profit_price")
        if tp_price and price >= tp_price:
            return f"ATR TP ({price:.4f} ≥ {tp_price:.4f})"

        return None
