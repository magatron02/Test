"""
Thai mutual fund NAV client.
Primary source: SEC Thailand API (api-portal.sec.or.th) — requires free API key.
Fallback: simulated NAV based on realistic fund-type volatility.

How to get SEC API key:
  1. Register at https://api-portal.sec.or.th
  2. Subscribe to "Fund Factsheet API" and "Fund Daily Info API"
  3. Add key to config/settings.yml under thai.sec_api_key
"""
import logging
import math
import random
import time as _time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import aiohttp

from ..core.config import settings

logger = logging.getLogger(__name__)

SEC_BASE = "https://api.sec.or.th/FundData"

# Fund type → (daily_vol, expected_annual_return)
_TYPE_PARAMS = {
    "equity":       (0.012,  0.08),
    "equity_esg":   (0.011,  0.07),
    "mixed":        (0.007,  0.05),
    "fixed_income": (0.002,  0.03),
    "money_market": (0.0002, 0.018),
    "commodity":    (0.015,  0.06),
    "foreign":      (0.010,  0.07),
}

# Curated list of popular Thai mutual funds
POPULAR_FUNDS: List[dict] = [
    {"code": "KFSDIV",        "name": "KF หุ้นทุนปันผล",         "amcTH": "กสิกรไทย",    "type": "equity",       "nav_seed": 12.50,  "proj_id": "3019"},
    {"code": "SCBDIV",        "name": "SCB หุ้นปันผล",           "amcTH": "ไทยพาณิชย์",  "type": "equity",       "nav_seed": 8.30,   "proj_id": "2541"},
    {"code": "TMBAM-ES-THAI", "name": "TMBAM หุ้นไทย ESG",      "amcTH": "ทหารไทย",     "type": "equity_esg",   "nav_seed": 15.20,  "proj_id": "4512"},
    {"code": "KT-PRECIOUS",   "name": "KT ทองคำ",                "amcTH": "กรุงไทย",     "type": "commodity",    "nav_seed": 22.10,  "proj_id": "3421"},
    {"code": "PRINCIPAL-TDIF","name": "Principal ตราสารหนี้",   "amcTH": "พรินซิเพิล",  "type": "fixed_income", "nav_seed": 10.85,  "proj_id": "4110"},
    {"code": "KFMONEY",       "name": "KF ตลาดเงิน",             "amcTH": "กสิกรไทย",    "type": "money_market", "nav_seed": 10.05,  "proj_id": "3011"},
    {"code": "ASP-DIVSM",     "name": "ASP หุ้น Small-Mid",      "amcTH": "เอเซียพลัส",  "type": "equity",       "nav_seed": 5.75,   "proj_id": "4801"},
    {"code": "UOBSF",         "name": "UOB Smart Fund",          "amcTH": "ยูโอบี",       "type": "mixed",        "nav_seed": 14.30,  "proj_id": "4230"},
    {"code": "BBLAM-SCCS",    "name": "BBLAM หุ้น SET50",        "amcTH": "บัวหลวง",     "type": "equity",       "nav_seed": 9.80,   "proj_id": "2890"},
    {"code": "PHATRA-GIF",    "name": "ภัทร Global Infra",       "amcTH": "ภัทร",         "type": "foreign",      "nav_seed": 11.40,  "proj_id": "4670"},
]

_sim_navs: Dict[str, dict] = {}


def _sim_nav(fund: dict, days: int = 365) -> List[dict]:
    """Generate synthetic NAV history for a fund."""
    code = fund["code"]
    state = _sim_navs.setdefault(code, {"nav": fund["nav_seed"]})
    vol, drift_yr = _TYPE_PARAMS.get(fund["type"], (0.008, 0.05))
    drift_day = drift_yr / 252

    rows = []
    p = fund["nav_seed"] * random.uniform(0.88, 1.02)
    for i in range(days):
        dt = datetime.utcnow().date() - timedelta(days=days - i)
        if dt.weekday() >= 5:
            continue
        p *= math.exp(random.gauss(drift_day, vol))
        rows.append({"date": str(dt), "nav": round(p, 4)})

    # update current simulated nav
    state["nav"] = rows[-1]["nav"] if rows else fund["nav_seed"]
    return rows


def _calc_returns(history: List[dict]) -> dict:
    if not history:
        return {}
    nav_now = history[-1]["nav"]

    def _ret(n):
        if len(history) < n:
            return None
        return round((nav_now / history[-n]["nav"] - 1) * 100, 2)

    return {
        "nav":     nav_now,
        "ret_1d":  _ret(2),
        "ret_1m":  _ret(22),
        "ret_3m":  _ret(66),
        "ret_6m":  _ret(126),
        "ret_1y":  _ret(252),
        "ret_ytd": _ytd_return(history),
    }


def _ytd_return(history: List[dict]) -> Optional[float]:
    this_year = str(datetime.utcnow().year)
    ytd_start = next((r for r in history if r["date"].startswith(this_year)), None)
    if not ytd_start or not history:
        return None
    return round((history[-1]["nav"] / ytd_start["nav"] - 1) * 100, 2)


class FundClient:
    """Thai mutual fund NAV client — SEC API with simulation fallback."""

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._cache: Dict[str, dict] = {}

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            api_key = settings.get("thai", "sec_api_key", default="")
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Ocp-Apim-Subscription-Key"] = api_key
            self._session = aiohttp.ClientSession(
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            )
        return self._session

    async def _fetch_nav_sec(self, proj_id: str, days: int = 365) -> Optional[List[dict]]:
        """Fetch NAV history from SEC Thailand API."""
        end = datetime.utcnow().date()
        start = end - timedelta(days=days)
        session = await self._get_session()
        try:
            url = f"{SEC_BASE}/nav/daily"
            async with session.get(url, params={
                "proj_id": proj_id,
                "start_date": str(start),
                "end_date": str(end),
            }) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                if not isinstance(data, list):
                    return None
                return [
                    {"date": row.get("nav_date", ""), "nav": float(row.get("nav", 0))}
                    for row in data
                    if row.get("nav")
                ]
        except Exception:
            return None

    async def get_fund_data(self, fund: dict, days: int = 365) -> dict:
        code = fund["code"]

        # Try SEC API first
        if settings.get("thai", "sec_api_key"):
            nav_history = await self._fetch_nav_sec(fund.get("proj_id", ""), days)
            if nav_history:
                rets = _calc_returns(nav_history)
                return {**fund, **rets, "source": "sec_api", "history": nav_history[-30:]}

        # Fallback to simulation
        nav_history = _sim_nav(fund, days)
        rets = _calc_returns(nav_history)
        return {**fund, **rets, "source": "simulation", "history": nav_history[-30:]}

    async def get_all_funds(self) -> List[dict]:
        import asyncio
        tasks = [self.get_fund_data(f) for f in POPULAR_FUNDS]
        return await asyncio.gather(*tasks)

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()


# Singleton
fund_client = FundClient()
