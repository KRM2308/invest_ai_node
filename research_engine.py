from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from financial_analyzer import analyze_financials
from founder_checker import check_founders
from sentiment_engine import get_social_sentiment


APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
RESULTS_FILE = DATA_DIR / "results.json"
WATCHLIST_FILE = DATA_DIR / "watchlist.json"
SETTINGS_FILE = DATA_DIR / "settings.json"


def ensure_storage() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not RESULTS_FILE.exists():
        RESULTS_FILE.write_text("[]", encoding="utf-8")
    if not WATCHLIST_FILE.exists():
        WATCHLIST_FILE.write_text("[]", encoding="utf-8")
    if not SETTINGS_FILE.exists():
        SETTINGS_FILE.write_text(
            json.dumps(
                {
                    "demo_mode": False,
                    "coingecko_api_key": "",
                    "reddit_client_id": "",
                    "reddit_client_secret": "",
                    "reddit_user_agent": "InvestAI/1.0",
                    "telegram_bot_token": "",
                    "telegram_chat_id": "",
                },
                indent=2,
            ),
            encoding="utf-8",
        )


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def load_settings() -> Dict[str, Any]:
    ensure_storage()
    return _read_json(SETTINGS_FILE, {})


def save_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    ensure_storage()
    current = load_settings()
    current.update(settings or {})
    _write_json(SETTINGS_FILE, current)
    return current


def load_results() -> List[Dict[str, Any]]:
    ensure_storage()
    return _read_json(RESULTS_FILE, [])


def save_result(item: Dict[str, Any]) -> None:
    rows = load_results()
    rows = [r for r in rows if str(r.get("entity", "")).lower() != str(item.get("entity", "")).lower()]
    rows.insert(0, item)
    _write_json(RESULTS_FILE, rows[:250])


def load_watchlist() -> List[str]:
    ensure_storage()
    arr = _read_json(WATCHLIST_FILE, [])
    return [str(x) for x in arr]


def add_watchlist(entity: str) -> List[str]:
    items = [x for x in load_watchlist() if x.lower() != entity.lower()]
    items.insert(0, entity)
    _write_json(WATCHLIST_FILE, items[:200])
    return items


def _verdict(score: int) -> str:
    if score >= 76:
        return "INVESTIR"
    if score >= 56:
        return "OBSERVER"
    return "FUIR"


def _reason(fin: Dict[str, Any], founders: Dict[str, Any], social: Dict[str, Any]) -> str:
    return (
        f"Financial momentum {fin.get('score', 0)}/100, "
        f"founder reliability {founders.get('reliability', 0)}%, "
        f"social sentiment {social.get('sentiment', 'NEUTRAL')}."
    )


async def run_research(entity: str, demo_mode: bool = False, settings: Dict[str, Any] | None = None) -> Dict[str, Any]:
    settings = settings or load_settings()
    demo = bool(demo_mode or settings.get("demo_mode"))
    reddit_cfg = {
        "client_id": settings.get("reddit_client_id", ""),
        "client_secret": settings.get("reddit_client_secret", ""),
        "user_agent": settings.get("reddit_user_agent", "InvestAI/1.0"),
    }

    loop = asyncio.get_running_loop()
    fin_f = loop.run_in_executor(None, lambda: analyze_financials(entity, demo))
    founder_f = loop.run_in_executor(None, lambda: check_founders(entity, demo))
    social_f = loop.run_in_executor(None, lambda: get_social_sentiment(entity, demo, reddit_cfg))
    financials, founders, social = await asyncio.gather(fin_f, founder_f, social_f)

    final_score = int(round(financials["score"] * 0.4 + founders["score"] * 0.3 + social["score"] * 0.3))
    verdict = _verdict(final_score)
    result = {
        "entity": entity,
        "score": max(0, min(100, final_score)),
        "verdict": verdict,
        "reason": _reason(financials, founders, social),
        "financials": financials,
        "founders": founders,
        "social": social,
        "weights": {"financials": 0.4, "founders": 0.3, "social": 0.3},
        "mode": "demo" if demo else "real",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    save_result(result)
    return result

