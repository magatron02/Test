"""
Social / News Sentiment — F1.3 (Lunai v1.3.0 "Perception").

Data source: CryptoCompare news API (free, no API key for basic queries).
Endpoint: https://min-api.cryptocompare.com/data/v2/news/?lang=EN

Scoring:
  • Count bullish vs bearish keywords in article titles & body snippets.
  • Sentiment ratio > 0.55 → BULLISH, < 0.45 → BEARISH, else NEUTRAL.
  • Score ∈ [-1, 1] — used as an additive signal in the trading engine.
  • High mention volume amplifies the existing lean (same logic as OI change).
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import aiohttp

logger = logging.getLogger(__name__)

_CC_NEWS_URL = "https://min-api.cryptocompare.com/data/v2/news/?lang=EN"
_CACHE_TTL   = 300   # 5 min

_cache: Dict[str, tuple] = {}

_BULLISH_WORDS: frozenset = frozenset({
    "surge", "rally", "bull", "bullish", "breakout", "pump", "soar", "rise",
    "gain", "record", "high", "adoption", "etf", "approval", "approved",
    "launch", "partnership", "upgrade", "halving", "institutional", "buy",
    "accumulate", "support", "recovery", "rebound", "explode", "milestone",
    "inflow", "positive", "optimistic", "growth", "expand",
})

_BEARISH_WORDS: frozenset = frozenset({
    "crash", "dump", "bear", "bearish", "drop", "plunge", "fall", "lose",
    "loss", "ban", "hack", "scam", "fraud", "regulation", "lawsuit", "fear",
    "sell", "collapse", "liquidat", "bankrupt", "fail", "reject", "rejected",
    "outflow", "negative", "pessimistic", "concern", "risk", "warning",
    "penalty", "fine", "seized", "shutdown", "exploit",
})


# ── Data class ────────────────────────────────────────────────────────────────

@dataclass
class SocialSnapshot:
    symbol: str
    article_count: int = 0
    bullish_count: int = 0
    bearish_count: int = 0
    sentiment_ratio: Optional[float] = None   # bullish/(bull+bear) — [0,1]
    label: str = "NEUTRAL"
    score: float = 0.0                        # [-1, 1]
    error: Optional[str] = None
    ts: float = field(default_factory=time.time)


# ── Pure scoring ──────────────────────────────────────────────────────────────

def social_sentiment_score(
    articles: List[dict],
    symbol_hint: str = "",
) -> Tuple[str, float, int, int]:
    """Pure function — score a list of news articles.

    Each article dict should have a 'title' key; 'body' is optional.
    symbol_hint filters articles that mention the asset (e.g. "BTC").

    Returns (label, score, bullish_count, bearish_count).
    """
    hint_lower = symbol_hint.lower() if symbol_hint else ""

    bull = 0
    bear = 0
    matched = 0

    for art in articles:
        text = " ".join([
            str(art.get("title", "")),
            str(art.get("body", ""))[:200],   # first 200 chars of body
        ]).lower()

        # Filter: only count articles mentioning the asset
        if hint_lower and hint_lower not in text:
            continue

        matched += 1
        words = set(text.split())
        article_bull = len(words & _BULLISH_WORDS)
        article_bear = len(words & _BEARISH_WORDS)
        if article_bull > article_bear:
            bull += 1
        elif article_bear > article_bull:
            bear += 1

    total = bull + bear
    if total == 0:
        return "NEUTRAL", 0.0, 0, 0

    ratio = bull / total
    score = (ratio - 0.5) * 2.0   # [0,1] → [-1, 1]

    # Amplify if there are many articles (more signal = more conviction)
    if matched >= 20:
        score *= 1.15
    score = max(-1.0, min(1.0, score))

    if score >= 0.30:
        label = "BULLISH_NEWS"
    elif score >= 0.10:
        label = "MILD_BULLISH_NEWS"
    elif score <= -0.30:
        label = "BEARISH_NEWS"
    elif score <= -0.10:
        label = "MILD_BEARISH_NEWS"
    else:
        label = "NEUTRAL"

    return label, round(score, 3), bull, bear


# ── Async fetcher ─────────────────────────────────────────────────────────────

async def get_news_sentiment(symbol: str = "BTC/USDT") -> SocialSnapshot:
    """Fetch CryptoCompare news and return a sentiment snapshot for the symbol.

    Cached for _CACHE_TTL seconds.  Gracefully returns NEUTRAL on error.
    """
    base    = symbol.split("/")[0].upper()
    cache_key = f"social:{base}"
    entry   = _cache.get(cache_key)
    if entry and time.time() < entry[1]:
        return entry[0]

    snap = SocialSnapshot(symbol=base)
    try:
        params = {"lang": "EN", "sortOrder": "latest"}
        # CryptoCompare lets you filter by coin categories tag
        params["categories"] = base

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10),
            headers={"User-Agent": "Lunai/1.3 (crypto-ai-trader)"},
        ) as session:
            async with session.get(_CC_NEWS_URL, params=params) as resp:
                if resp.status != 200:
                    snap.error = f"HTTP {resp.status}"
                    _cache[cache_key] = (snap, time.time() + _CACHE_TTL)
                    return snap
                data = await resp.json(content_type=None)

        articles = data.get("Data", [])
        snap.article_count = len(articles)

        label, score, bull, bear = social_sentiment_score(articles, symbol_hint=base)
        snap.label          = label
        snap.score          = score
        snap.bullish_count  = bull
        snap.bearish_count  = bear

        total = bull + bear
        snap.sentiment_ratio = round(bull / total, 3) if total else None

        logger.debug("Social sentiment %s: %s (%.2f) from %d articles",
                     base, label, score, snap.article_count)

    except Exception as e:
        logger.warning("Social sentiment fetch failed for %s: %s", symbol, e)
        snap.error = str(e)

    _cache[cache_key] = (snap, time.time() + _CACHE_TTL)
    return snap
