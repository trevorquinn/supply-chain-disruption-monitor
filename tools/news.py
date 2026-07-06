"""
Supply chain disruption news via NewsAPI.
Free tier: 100 requests/day. Sign up at https://newsapi.org/
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import httpx

from tools import repository

NEWSAPI_URL = "https://newsapi.org/v2/everything"

# Default search terms to bias toward supply chain disruption signals.
# Source of truth: data/news_terms.toml
_DEFAULT_SUPPLY_CHAIN_TERMS = repository.supply_chain_terms()


async def search_disruption_news(query: str, days: int = 7, max_results: int = 10) -> dict:
    """
    Search recent news for supply chain disruption signals.

    Args:
        query: Search query (e.g. "Red Sea shipping", "Shanghai port strike")
        days: How many days back to search (default 7, free tier max 30)
        max_results: Maximum articles to return (default 10)

    Returns:
        dict with 'query', 'article_count', and 'articles' list
    """
    api_key = os.getenv("NEWS_API_KEY", "")
    if not api_key or api_key == "your_newsapi_key_here":
        return {
            "error": (
                "NEWS_API_KEY not set. Sign up free at https://newsapi.org/ "
                "and add the key to .env"
            ),
            "query": query,
            "articles": [],
        }

    from_date = (datetime.now(timezone.utc) - timedelta(days=min(days, 30))).strftime(
        "%Y-%m-%d"
    )

    params = {
        "q": query,
        "from": from_date,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": min(max_results, 100),
        "apiKey": api_key,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(NEWSAPI_URL, params=params)

    if resp.status_code == 401:
        return {"error": "Invalid NEWS_API_KEY — check your key at https://newsapi.org/", "articles": []}
    if resp.status_code == 429:
        return {"error": "NewsAPI rate limit reached (100 req/day on free tier)", "articles": []}
    resp.raise_for_status()

    data = resp.json()
    articles_raw = data.get("articles", [])

    articles = []
    for a in articles_raw[:max_results]:
        # Skip articles with no description
        if not a.get("description"):
            continue
        articles.append(
            {
                "title": a.get("title", "").strip(),
                "source": a.get("source", {}).get("name", "Unknown"),
                "published_at": a.get("publishedAt", ""),
                "description": (a.get("description") or "").strip()[:300],
                "url": a.get("url", ""),
            }
        )

    # Rough sentiment scan for high-signal terms (source: data/news_terms.toml)
    alert_terms = repository.alert_terms()

    flagged = []
    for a in articles:
        text = (a["title"] + " " + a["description"]).lower()
        hits = [t for t in alert_terms if t in text]
        if hits:
            flagged.append({"title": a["title"], "signals": hits, "url": a["url"]})

    return {
        "query": query,
        "date_range": f"Last {days} days",
        "total_results": data.get("totalResults", 0),
        "article_count": len(articles),
        "articles": articles,
        "flagged_high_signal": flagged,
    }
