"""
Arbitrage strategies for Lunai.

TriangularArbScanner
  Scans 3-leg cycles on a single exchange (USDT→A→B→USDT and reverse).
  Uses real bid/ask from get_orderbook_top() for accurate profitability.
  Auto-executes the best opportunity when net profit exceeds threshold.

FundingRateMonitor
  Tracks perpetual futures funding rates across configured symbols.
  Identifies delta-neutral carry trades: long spot + short perp (positive rate)
  or short spot + long perp (negative rate).
  Reports annualised yield; advisory output — user opens perp legs manually.

ArbitrageEngine
  Orchestrates both scanners each trading cycle.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Each (A, B) pair generates two triangles:
#   Forward:  USDT→A→B→USDT  (buy A/USDT, buy B/A, sell B/USDT)
#   Reverse:  USDT→B→A→USDT  (buy B/USDT, sell B/A, sell A/USDT)
_TRIANGLES: List[Tuple[str, str]] = [
    ("BTC", "ETH"),
    ("BTC", "BNB"),
    ("BTC", "SOL"),
    ("BTC", "XRP"),
    ("ETH", "BNB"),
    ("ETH", "SOL"),
]


# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class TriLeg:
    symbol: str
    side:   str     # BUY | SELL
    price:  float   # expected execution price


@dataclass
class TriangularOpportunity:
    cycle:            str
    legs:             List[TriLeg]
    gross_profit_pct: float
    net_profit_pct:   float     # after 3 × fee
    amount_usdt:      float     # recommended trade size
    detected_at:      datetime = field(default_factory=datetime.utcnow)


@dataclass
class FundingRateInfo:
    symbol:           str
    funding_rate:     float         # e.g. 0.0001 = 0.01% per 8h
    funding_rate_pct: float
    annualized_pct:   float         # rate × 3 × 365 × 100
    next_funding_at:  Optional[datetime]
    arb_viable:       bool
    direction:        str           # LONG_SPOT_SHORT_PERP | SHORT_SPOT_LONG_PERP
    note:             str


# ── Triangular Arb Scanner ────────────────────────────────────────────────────

class TriangularArbScanner:
    """Scan and execute 3-leg triangular arbitrage on a single exchange."""

    def __init__(
        self,
        exchange,
        fee_pct:            float = 0.001,   # 0.1% per leg
        min_net_profit_pct: float = 0.15,    # min net profit after fees (%)
        max_amount_usdt:    float = 200.0,
    ):
        self._exchange   = exchange
        self._fee_pct    = fee_pct
        self._min_net    = min_net_profit_pct
        self._max_amount = max_amount_usdt
        self._latest:    List[TriangularOpportunity] = []
        self._stats: Dict = {
            "scans": 0, "found": 0, "executed": 0,
            "profit_usdt": 0.0, "last_scan": None,
        }

    async def scan(self) -> List[TriangularOpportunity]:
        self._stats["scans"]    += 1
        self._stats["last_scan"] = datetime.utcnow().isoformat()

        # Gather bid/ask for every symbol needed by all triangles
        needed = set()
        for a, b in _TRIANGLES:
            needed.update([f"{a}/USDT", f"{b}/USDT", f"{b}/{a}"])

        prices: Dict[str, Dict[str, float]] = {}
        for sym in needed:
            try:
                top = await self._exchange.get_orderbook_top(sym)
                if top:
                    prices[sym] = {"bid": top.bid, "ask": top.ask}
            except Exception:
                pass

        opportunities: List[TriangularOpportunity] = []
        for a, b in _TRIANGLES:
            sym_a  = f"{a}/USDT"
            sym_b  = f"{b}/USDT"
            sym_ba = f"{b}/{a}"   # cross pair B quoted in A

            if not all(s in prices for s in [sym_a, sym_b, sym_ba]):
                continue

            # Forward:  buy A/USDT ask → buy B/A ask → sell B/USDT bid
            opp = self._calc(
                f"USDT→{a}→{b}→USDT",
                [
                    TriLeg(sym_a,  "BUY",  prices[sym_a]["ask"]),
                    TriLeg(sym_ba, "BUY",  prices[sym_ba]["ask"]),
                    TriLeg(sym_b,  "SELL", prices[sym_b]["bid"]),
                ],
            )
            if opp and opp.net_profit_pct >= self._min_net:
                opportunities.append(opp)

            # Reverse: buy B/USDT ask → sell B/A bid → sell A/USDT bid
            opp = self._calc(
                f"USDT→{b}→{a}→USDT",
                [
                    TriLeg(sym_b,  "BUY",  prices[sym_b]["ask"]),
                    TriLeg(sym_ba, "SELL", prices[sym_ba]["bid"]),
                    TriLeg(sym_a,  "SELL", prices[sym_a]["bid"]),
                ],
            )
            if opp and opp.net_profit_pct >= self._min_net:
                opportunities.append(opp)

        opportunities.sort(key=lambda o: o.net_profit_pct, reverse=True)
        self._latest = opportunities
        if opportunities:
            self._stats["found"] += len(opportunities)
            logger.info(
                "TriArb: %d opportunities — best %s %.3f%%",
                len(opportunities), opportunities[0].cycle, opportunities[0].net_profit_pct,
            )
        return opportunities

    def _calc(self, cycle: str, legs: List[TriLeg]) -> Optional[TriangularOpportunity]:
        """Compute net profit for a 3-leg triangle (fees already baked in)."""
        try:
            amount = self._max_amount
            fee    = 1.0 - self._fee_pct
            for leg in legs:
                if leg.price <= 0:
                    return None
                if leg.side == "BUY":
                    amount = (amount / leg.price) * fee
                else:
                    amount = amount * leg.price * fee
            profit  = amount - self._max_amount
            net_pct = profit / self._max_amount * 100
            # gross = net + 3-leg fee drag for display only
            gross_pct = net_pct + (1 - (1 - self._fee_pct) ** 3) * 100
            return TriangularOpportunity(
                cycle=cycle, legs=legs,
                gross_profit_pct=round(gross_pct, 4),
                net_profit_pct=round(net_pct, 4),
                amount_usdt=self._max_amount,
            )
        except Exception:
            return None

    async def execute(
        self,
        opp: TriangularOpportunity,
        available_usdt: float,
        dry_run: bool = False,
    ) -> Optional[dict]:
        """Execute all 3 legs. Returns result dict or None if first leg fails."""
        amount = min(opp.amount_usdt, available_usdt * 0.90)
        if amount <= 0:
            return None

        if dry_run:
            profit = amount * opp.net_profit_pct / 100
            self._stats["executed"]    += 1
            self._stats["profit_usdt"] += profit
            logger.info("[DryRun] TriArb %s: +%.4f USDT (%.4f%%)",
                        opp.cycle, profit, opp.net_profit_pct)
            return {
                "cycle": opp.cycle, "dry_run": True,
                "profit_usdt":    round(profit, 4),
                "net_profit_pct": opp.net_profit_pct,
            }

        cur = amount
        executed_legs = []
        for i, leg in enumerate(opp.legs):
            try:
                if leg.side == "BUY":
                    qty   = cur / leg.price
                    order = await self._exchange.create_order(leg.symbol, "buy", qty)
                    cur   = order.amount * (1.0 - self._fee_pct)
                else:
                    order = await self._exchange.create_order(leg.symbol, "sell", cur)
                    cur   = order.cost * (1.0 - self._fee_pct)
                executed_legs.append({"leg": i + 1, "symbol": leg.symbol, "side": leg.side})
                logger.info("TriArb leg %d/%d OK: %s %s", i + 1, len(opp.legs),
                            leg.side, leg.symbol)
            except Exception as exc:
                logger.error("TriArb leg %d FAILED (%s %s): %s",
                             i + 1, leg.side, leg.symbol, exc)
                return {"cycle": opp.cycle, "failed_at_leg": i + 1, "error": str(exc)}

        profit = cur - amount
        self._stats["executed"]    += 1
        self._stats["profit_usdt"] += profit
        logger.info("TriArb COMPLETE %s: +%.4f USDT", opp.cycle, profit)
        return {
            "cycle":          opp.cycle,
            "profit_usdt":    round(profit, 4),
            "net_profit_pct": round(profit / amount * 100, 4),
            "legs":           executed_legs,
        }

    @property
    def latest(self) -> List[TriangularOpportunity]:
        return self._latest

    @property
    def stats(self) -> dict:
        return dict(self._stats)


# ── Funding Rate Monitor ──────────────────────────────────────────────────────

class FundingRateMonitor:
    """Track perpetual futures funding rates for delta-neutral carry-trade signals.

    A positive funding rate (longs pay shorts) means:
      Long spot + Short perp → collect funding (annualised yield).

    A negative rate:
      Short spot + Long perp → collect funding from shorts.

    This class is advisory — it reports opportunities and lets the user
    (or a futures-capable executor) open the perp legs.
    """

    def __init__(self, exchange, min_annualized_pct: float = 15.0):
        self._exchange = exchange
        self._min_ann  = min_annualized_pct
        self._latest:  List[FundingRateInfo] = []
        self._stats: Dict = {"scans": 0, "viable_count": 0, "last_scan": None}

    async def scan(self, symbols: List[str]) -> List[FundingRateInfo]:
        self._stats["scans"]    += 1
        self._stats["last_scan"] = datetime.utcnow().isoformat()
        results: List[FundingRateInfo] = []

        for sym in symbols:
            try:
                data = await self._exchange.get_funding_rate(sym)
                if not data:
                    continue
                rate     = float(data.get("fundingRate", 0))
                next_raw = data.get("fundingDatetime")
                try:
                    # Binance returns epoch-ms as string; ISO strings also handled
                    next_dt: Optional[datetime] = (
                        datetime.fromtimestamp(int(next_raw) / 1000)
                        if str(next_raw).isdigit()
                        else datetime.fromisoformat(str(next_raw))
                    ) if next_raw else None
                except Exception:
                    next_dt = None

                ann    = rate * 3 * 365 * 100   # 3 settlements/day × 365
                viable = abs(ann) >= self._min_ann
                if viable:
                    self._stats["viable_count"] += 1

                if rate >= 0:
                    direction = "LONG_SPOT_SHORT_PERP"
                    note = (f"Longs pay {rate*100:.4f}%/8h → "
                            f"long spot + short perp earns ~{abs(ann):.1f}%/yr")
                else:
                    direction = "SHORT_SPOT_LONG_PERP"
                    note = (f"Shorts pay {abs(rate)*100:.4f}%/8h → "
                            f"short spot + long perp earns ~{abs(ann):.1f}%/yr")

                results.append(FundingRateInfo(
                    symbol=sym,
                    funding_rate=rate,
                    funding_rate_pct=round(rate * 100, 6),
                    annualized_pct=round(abs(ann), 2),
                    next_funding_at=next_dt,
                    arb_viable=viable,
                    direction=direction,
                    note=note,
                ))
            except Exception as exc:
                logger.debug("FundingRate %s failed: %s", sym, exc)

        results.sort(key=lambda r: r.annualized_pct, reverse=True)
        self._latest = results
        viable = [r for r in results if r.arb_viable]
        if viable:
            logger.info("FundingArb: %d viable (best: %s %.1f%%/yr)",
                        len(viable), viable[0].symbol, viable[0].annualized_pct)
        return results

    @property
    def latest(self) -> List[FundingRateInfo]:
        return self._latest

    @property
    def stats(self) -> dict:
        return dict(self._stats)


# ── Arbitrage Engine ──────────────────────────────────────────────────────────

class ArbitrageEngine:
    """Orchestrates tri-arb + funding-rate scan on every trading cycle."""

    def __init__(self, exchange, config: dict = None, dry_run: bool = False):
        cfg = config or {}
        self._dry_run = dry_run
        self._tri  = TriangularArbScanner(
            exchange,
            fee_pct            = float(cfg.get("fee_pct",            0.001)),
            min_net_profit_pct = float(cfg.get("min_profit_pct",     0.15)),
            max_amount_usdt    = float(cfg.get("max_amount_usdt",    200.0)),
        )
        self._fund = FundingRateMonitor(
            exchange,
            min_annualized_pct = float(cfg.get("min_funding_ann_pct", 15.0)),
        )
        self._last_result: dict = {
            "tri_opportunities": [], "funding_rates": [], "executed": [],
        }

    async def run_cycle(self, symbols: List[str], available_usdt: float) -> dict:
        """Scan both strategies; auto-execute best tri-arb if profitable."""
        tri_opps  = await self._tri.scan()
        fund_info = await self._fund.scan(symbols)

        executed = []
        for opp in tri_opps:
            if available_usdt >= 10.0:
                result = await self._tri.execute(opp, available_usdt,
                                                 dry_run=self._dry_run)
                if result:
                    executed.append(result)
                break  # only best opportunity per cycle

        self._last_result = {
            "tri_opportunities": [
                {
                    "cycle":          o.cycle,
                    "net_profit_pct": o.net_profit_pct,
                    "gross_profit_pct": o.gross_profit_pct,
                    "amount_usdt":    o.amount_usdt,
                    "detected_at":    o.detected_at.isoformat(),
                }
                for o in tri_opps
            ],
            "funding_rates": [
                {
                    "symbol":          r.symbol,
                    "rate_pct_8h":     r.funding_rate_pct,
                    "annualized_pct":  r.annualized_pct,
                    "viable":          r.arb_viable,
                    "direction":       r.direction,
                    "note":            r.note,
                    "next_funding_at": (r.next_funding_at.isoformat()
                                       if r.next_funding_at else None),
                }
                for r in fund_info
            ],
            "executed": executed,
        }
        return self._last_result

    @property
    def last_result(self) -> dict:
        return self._last_result

    def full_stats(self) -> dict:
        return {
            "triangular": self._tri.stats,
            "funding":    self._fund.stats,
        }
