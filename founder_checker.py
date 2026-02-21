from __future__ import annotations

import hashlib
from typing import Any, Dict, List


def _seed(entity: str) -> int:
    digest = hashlib.sha256((entity or "").encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _pick_name(seed: int) -> str:
    first = ["Alex", "Sam", "Maya", "Nina", "Leo", "Iris", "Noah", "Ava", "Lina", "Hugo"]
    last = ["Barton", "Elwood", "Kell", "Mendoza", "Vega", "Sloan", "Briant", "Dumas", "Rossi", "Fisher"]
    return f"{first[seed % len(first)]} {last[(seed // 7) % len(last)]}"


def check_founders(entity: str, demo_mode: bool = False) -> Dict[str, Any]:
    if not entity:
        raise ValueError("entity is required")

    seed = _seed(entity)
    past_exits = 1 + (seed % 4)
    reliability = 52 + (seed % 44)
    red_flag_pool = [
        "No critical red flags found",
        "Limited governance disclosure",
        "Aggressive hiring despite weak treasury",
        "Concentrated decision power",
        "Inconsistent public roadmap cadence",
    ]
    red_flag = red_flag_pool[(seed // 5) % len(red_flag_pool)]
    if demo_mode:
        reliability = min(98, reliability + 6)
        red_flag = "Demo mode: simulated profile"

    names: List[str] = [_pick_name(seed), _pick_name(seed // 2 + 19)]
    score = max(0, min(100, reliability))
    return {
        "score": score,
        "name": names[0],
        "founders": names,
        "reliability": reliability,
        "past_exits": past_exits,
        "red_flags": red_flag,
        "source": "simulation",
    }

