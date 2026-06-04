"""Tests for social/news sentiment scoring (F1.3)."""
from src.data.social import social_sentiment_score


def _articles(titles):
    return [{"title": t, "body": ""} for t in titles]


def test_mostly_bullish_headlines():
    arts = _articles([
        "Bitcoin surges to new record high",
        "Ethereum rally continues as institutional adoption grows",
        "BTC ETF approval expected to drive bull market",
        "Crypto market gains momentum in strong rebound",
    ])
    label, score, bull, bear = social_sentiment_score(arts, "BTC")
    assert score > 0
    assert "BULLISH" in label


def test_mostly_bearish_headlines():
    arts = _articles([
        "Bitcoin crash wipes out billions in losses",
        "Crypto market dumps on SEC fraud lawsuit fears",
        "Exchange collapse triggers mass liquidation",
        "BTC plunges as bear market deepens",
    ])
    label, score, bull, bear = social_sentiment_score(arts, "BTC")
    assert score < 0
    assert "BEARISH" in label


def test_empty_articles_neutral():
    label, score, bull, bear = social_sentiment_score([], "BTC")
    assert label == "NEUTRAL"
    assert score == 0.0
    assert bull == 0 and bear == 0


def test_irrelevant_articles_filtered_out():
    # Articles about ETH shouldn't count when hint is BTC
    arts = _articles([
        "Ethereum rally to new highs",
        "ETH breaks out above resistance",
    ])
    label, score, bull, bear = social_sentiment_score(arts, "BTC")
    # No articles mention BTC → counts as zero relevant → NEUTRAL
    assert bull == 0 and bear == 0
    assert label == "NEUTRAL"


def test_symbol_hint_case_insensitive():
    arts = _articles(["btc surge record high", "bitcoin rally bullish"])
    label, score, bull, bear = social_sentiment_score(arts, "BTC")
    assert bull > 0


def test_score_bounded():
    arts = _articles([
        "Bitcoin surges rally record bull breakout adoption rise gain"
        for _ in range(30)
    ])
    label, score, bull, bear = social_sentiment_score(arts, "BTC")
    assert -1.0 <= score <= 1.0


def test_mixed_headlines_near_neutral():
    # All articles explicitly mention "BTC" so hint filtering keeps them all
    arts = _articles([
        "BTC surges amid adoption news",
        "BTC drops on regulation concerns",
        "BTC gains seen alongside losses today",
        "BTC crash fears versus bull rally expectations",
    ])
    label, score, _, _ = social_sentiment_score(arts, "BTC")
    # Mixed content → score should be within a moderate range of 0
    assert -0.8 <= score <= 0.8


def test_no_hint_counts_all_articles():
    arts = _articles([
        "market surge rally bullish",
        "crash dump bearish loss",
    ])
    _, _, bull_with_hint, _  = social_sentiment_score(arts, "BTC")
    _, _, bull_no_hint, _ = social_sentiment_score(arts, "")
    # No hint → all articles counted; with hint → only matching ones
    assert bull_no_hint >= bull_with_hint
