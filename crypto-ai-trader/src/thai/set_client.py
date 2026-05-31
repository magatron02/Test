"""
SET stock client using yfinance (.BK suffix for Thailand).
Falls back to Brownian-motion simulation when network is unavailable.
"""
import logging
import math
import random
import time as _time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ─── Catalogue ───────────────────────────────────────────────
SET_STOCKS = [
    {"symbol": "PTT.BK",    "name": "PTT",     "thai": "ปตท.",           "sector": "พลังงาน"},
    {"symbol": "PTTEP.BK",  "name": "PTTEP",   "thai": "ปตท.สำรวจ",      "sector": "พลังงาน"},
    {"symbol": "AOT.BK",    "name": "AOT",     "thai": "ท่าอากาศยาน",    "sector": "ขนส่ง"},
    {"symbol": "ADVANC.BK", "name": "ADVANC",  "thai": "แอดวานซ์ (AIS)", "sector": "สื่อสาร"},
    {"symbol": "KBANK.BK",  "name": "KBANK",   "thai": "กสิกรไทย",       "sector": "การเงิน"},
    {"symbol": "SCB.BK",    "name": "SCB",     "thai": "ไทยพาณิชย์",     "sector": "การเงิน"},
    {"symbol": "BBL.BK",    "name": "BBL",     "thai": "กรุงเทพ",        "sector": "การเงิน"},
    {"symbol": "SCC.BK",    "name": "SCC",     "thai": "ซิเมนต์ไทย",    "sector": "อุตสาหกรรม"},
    {"symbol": "CPALL.BK",  "name": "CPALL",   "thai": "ซีพีออล",       "sector": "พาณิชย์"},
    {"symbol": "BDMS.BK",   "name": "BDMS",    "thai": "บำรุงราษฎร์",   "sector": "สุขภาพ"},
    {"symbol": "DELTA.BK",  "name": "DELTA",   "thai": "เดลต้า",         "sector": "อุตสาหกรรม"},
    {"symbol": "GULF.BK",   "name": "GULF",    "thai": "กัลฟ์",         "sector": "พลังงาน"},
    {"symbol": "IVL.BK",    "name": "IVL",     "thai": "อินโดรามา",     "sector": "อุตสาหกรรม"},
    {"symbol": "MINT.BK",   "name": "MINT",    "thai": "มายเนอร์",      "sector": "ท่องเที่ยว"},
    {"symbol": "CPFTH.BK",  "name": "CPF",     "thai": "เจริญโภคภัณฑ์", "sector": "เกษตร"},
]

# Realistic THB seed prices (approximate)
_SEED_THB = {
    "PTT.BK": 32.0, "PTTEP.BK": 150.0, "AOT.BK": 58.0, "ADVANC.BK": 220.0,
    "KBANK.BK": 130.0, "SCB.BK": 100.0, "BBL.BK": 145.0, "SCC.BK": 230.0,
    "CPALL.BK": 58.0, "BDMS.BK": 26.0, "DELTA.BK": 65.0, "GULF.BK": 40.0,
    "IVL.BK": 25.0, "MINT.BK": 28.0, "CPFTH.BK": 28.0,
}

_sim_state: Dict[str, dict] = {}


def _sim_price(symbol: str) -> float:
    state = _sim_state.setdefault(symbol, {
        "price": _SEED_THB.get(symbol, 50.0),
        "last_t": _time.time(),
    })
    now = _time.time()
    dt = min(now - state["last_t"], 86400)
    vol = 0.015 * math.sqrt(dt / 86400)      # ~1.5% daily vol for SET stocks
    state["price"] *= math.exp(random.gauss(0, vol))
    state["last_t"] = now
    return state["price"]


def _mock_history(symbol: str, days: int = 100) -> List[dict]:
    base = _SEED_THB.get(symbol, 50.0) * random.uniform(0.90, 1.10)
    rows = []
    p = base
    for i in range(days):
        dt = datetime.utcnow() - timedelta(days=days - i)
        # skip weekends
        if dt.weekday() >= 5:
            continue
        o = p
        c = p * math.exp(random.gauss(0.0001, 0.012))
        h = max(o, c) * random.uniform(1.0, 1.008)
        l = min(o, c) * random.uniform(0.992, 1.0)
        v = random.uniform(5_000_000, 50_000_000)
        rows.append({"date": dt.date(), "open": o, "high": h, "low": l, "close": c, "volume": v})
        p = c
    return rows


class SETClient:
    """SET stock data — yfinance when available, simulation otherwise."""

    def _yf_fetch(self, symbol: str, period: str = "6mo"):
        import logging as _log
        import yfinance as yf
        # Suppress yfinance's own verbose warnings
        _log.getLogger("yfinance").setLevel(_log.CRITICAL)
        t = yf.Ticker(symbol)
        hist = t.history(period=period)
        if hist.empty:
            raise ValueError("empty history")
        rows = []
        for ts, row in hist.iterrows():
            rows.append({
                "date":   ts.date(),
                "open":   float(row["Open"]),
                "high":   float(row["High"]),
                "low":    float(row["Low"]),
                "close":  float(row["Close"]),
                "volume": float(row["Volume"]),
            })
        return rows

    def get_history(self, symbol: str, days: int = 100) -> List[dict]:
        try:
            rows = self._yf_fetch(symbol)
            logger.info(f"yfinance: fetched {len(rows)} days for {symbol}")
            return rows[-days:]
        except Exception as e:
            logger.info(f"yfinance unavailable ({e}), using simulation for {symbol}")
            return _mock_history(symbol, days)

    def get_quote(self, symbol: str) -> dict:
        history = self.get_history(symbol, days=5)
        if not history:
            return {}
        latest = history[-1]
        prev   = history[-2] if len(history) >= 2 else latest
        change = (latest["close"] - prev["close"]) / prev["close"] * 100
        seed   = _SEED_THB.get(symbol, latest["close"])
        ytd_pct = (latest["close"] - seed) / seed * 100
        info   = next((s for s in SET_STOCKS if s["symbol"] == symbol), {})
        return {
            "symbol":   symbol,
            "name":     info.get("name", symbol),
            "thai":     info.get("thai", ""),
            "sector":   info.get("sector", ""),
            "price":    round(latest["close"], 2),
            "change_1d": round(change, 2),
            "ytd_pct":  round(ytd_pct, 2),
            "volume":   int(latest["volume"]),
            "high":     round(latest["high"], 2),
            "low":      round(latest["low"], 2),
            "currency": "THB",
        }

    def get_all_quotes(self, symbols: Optional[List[str]] = None) -> List[dict]:
        targets = symbols or [s["symbol"] for s in SET_STOCKS]
        return [self.get_quote(sym) for sym in targets]


# Singleton
set_client = SETClient()
