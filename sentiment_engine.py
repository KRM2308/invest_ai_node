from __future__ import annotations

import hashlib
from typing import Any, Dict, List

import requests

try:
    import praw
except Exception:  # pragma: no cover - optional dependency
    praw = None


def _seed(entity: str) -> int:
    digest = hashlib.sha256((entity or "").encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _label_from_ratio(ratio: float) -> str:
    if ratio >= 0.7:
        return "VERY BULLISH"
    if ratio >= 0.56:
        return "BULLISH"
    if ratio >= 0.45:
        return "NEUTRAL"
    if ratio >= 0.33:
        return "BEARISH"
    return "VERY BEARISH"


def _public_reddit_sentiment(entity: str) -> Dict[str, Any] | None:
    query = (entity or "").strip()
    if not query:
        return None
    headers = {"User-Agent": "InvestAI/1.0 (due-diligence)"}
    try:
        res = requests.get(
            "https://www.reddit.com/search.json",
            params={"q": query, "sort": "top", "limit": 15, "t": "month"},
            headers=headers,
            timeout=12,
        )
        res.raise_for_status()
        posts = res.json().get("data", {}).get("children", [])
        if not posts:
            return None
        values: List[int] = []
        titles: List[str] = []
        for p in posts:
            d = p.get("data", {})
            title = str(d.get("title") or "").strip()
            score = int(d.get("score") or 0)
            if title:
                titles.append(title)
                values.append(score)
        if not values:
            return None
        positive = sum(1 for v in values if v > 20)
        ratio = positive / max(1, len(values))
        intensity = min(100, int((sum(values) / len(values)) / 8 + ratio * 40))
        return {
            "ratio": ratio,
            "intensity": intensity,
            "top_post": titles[0] if titles else "No significant thread",
            "sample_size": len(values),
            "source": "reddit-public",
        }
    except Exception:
        return None


def _praw_sentiment(entity: str, client_id: str, client_secret: str, user_agent: str) -> Dict[str, Any] | None:
    if praw is None or not client_id or not client_secret:
        return None
    try:
        reddit = praw.Reddit(client_id=client_id, client_secret=client_secret, user_agent=user_agent or "InvestAI/1.0")
        posts = list(reddit.subreddit("all").search(entity, sort="relevance", time_filter="month", limit=20))
        if not posts:
            return None
        values = [int(getattr(p, "score", 0) or 0) for p in posts]
        top_post = posts[0].title if posts else "No significant thread"
        positive = sum(1 for v in values if v > 20)
        ratio = positive / max(1, len(values))
        intensity = min(100, int((sum(values) / len(values)) / 8 + ratio * 40))
        return {
            "ratio": ratio,
            "intensity": intensity,
            "top_post": top_post,
            "sample_size": len(values),
            "source": "praw",
        }
    except Exception:
        return None


def get_social_sentiment(entity: str, demo_mode: bool = False, reddit_config: Dict[str, str] | None = None) -> Dict[str, Any]:
    if not entity:
        raise ValueError("entity is required")

    if demo_mode:
        seed = _seed(entity)
        ratio = 0.4 + ((seed % 48) / 100.0)
        intensity = 55 + (seed % 35)
        return {
            "score": min(100, max(0, int(ratio * 100))),
            "sentiment": _label_from_ratio(ratio),
            "intensity": intensity,
            "bullish_ratio": round(ratio, 3),
            "top_post": "Demo mode: market chatter is simulated.",
            "sample_size": 25,
            "source": "demo",
        }

    reddit_config = reddit_config or {}
    res = _praw_sentiment(
        entity,
        reddit_config.get("client_id", ""),
        reddit_config.get("client_secret", ""),
        reddit_config.get("user_agent", ""),
    )
    if res is None:
        res = _public_reddit_sentiment(entity)
    if res is None:
        seed = _seed(f"fallback:{entity}")
        ratio = 0.35 + ((seed % 42) / 100.0)
        intensity = 48 + (seed % 29)
        res = {
            "ratio": ratio,
            "intensity": intensity,
            "top_post": "No live Reddit data available; fallback model used.",
            "sample_size": 0,
            "source": "fallback",
        }

    ratio = float(res["ratio"])
    score = min(100, max(0, int(ratio * 100)))
    return {
        "score": score,
        "sentiment": _label_from_ratio(ratio),
        "intensity": int(res["intensity"]),
        "bullish_ratio": round(ratio, 3),
        "top_post": res["top_post"],
        "sample_size": int(res["sample_size"]),
        "source": res["source"],
    }

