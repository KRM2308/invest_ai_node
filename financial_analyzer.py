from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

try:
    import yfinance as yf
except Exception:  # pragma: no cover - optional dependency
    yf = None


COINGECKO_SEARCH = "https://api.coingecko.com/api/v3/search"
COINGECKO_MARKETS = "https://api.coingecko.com/api/v3/coins/markets"


@dataclass
class FinancialSnapshot:
    score: int
    market_cap: float
    price_change_7d: float
    price: float
    revenue_estimate: float
    burn_rate: float
    source: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "market_cap": self.market_cap,
            "price_change_7d": self.price_change_7d,
            "price": self.price,
            "revenue_estimate": self.revenue_estimate,
            "burn_rate": self.burn_rate,
            "source": self.source,
        }


def _hash_score(seed: str, low: int = 45, high: int = 82) -> int:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    value = int(digest[:8], 16)
    return low + (value % max(1, (high - low + 1)))


def _is_probable_crypto(entity: str) -> bool:
    s = (entity or "").strip().lower()
    return s.startswith("$") or any(k in s for k in ("btc", "eth", "sol", "coin", "token", "crypto"))


def _coingecko_lookup(entity: str, timeout: int = 12) -> Optional[dict]:
    query = entity.replace("$", "").strip()
    if not query:
        return None
    try:
        res = requests.get(COINGECKO_SEARCH, params={"query": query}, timeout=timeout)
        res.raise_for_status()
        coins = res.json().get("coins", [])
        if not coins:
            return None
        coin_id = coins[0]["id"]
        mr = requests.get(
            COINGECKO_MARKETS,
            params={"vs_currency": "usd", "ids": coin_id, "price_change_percentage": "7d"},
            timeout=timeout,
        )
        mr.raise_for_status()
        rows = mr.json() or []
        if not rows:
            return None
        return rows[0]
    except Exception:
        return None


def _yahoo_lookup(entity: str) -> Optional[dict]:
    if yf is None:
        return None
    ticker = (entity or "").strip().upper().replace("$", "")
    if not ticker:
        return None
    try:
        tk = yf.Ticker(ticker)
        info = tk.info or {}
        hist = tk.history(period="7d")
        pct = 0.0
        if not hist.empty and "Close" in hist:
            first = float(hist["Close"].iloc[0])
            last = float(hist["Close"].iloc[-1])
            if first:
                pct = ((last - first) / first) * 100.0
        return {
            "market_cap": float(info.get("marketCap") or 0.0),
            "current_price": float(info.get("currentPrice") or info.get("regularMarketPrice") or 0.0),
            "price_change_7d": pct,
            "revenue": float(info.get("totalRevenue") or 0.0),
        }
    except Exception:
        return None


def analyze_financials(entity: str, demo_mode: bool = False) -> Dict[str, Any]:
    if not entity:
        raise ValueError("entity is required")

    if demo_mode:
        score = _hash_score(f"demo:{entity}", 55, 88)
        snap = FinancialSnapshot(
            score=score,
            market_cap=float(score) * 2_200_000.0,
            price_change_7d=float((score % 24) - 8),
            price=float(score) * 1.7,
            revenue_estimate=float(score) * 420_000.0,
            burn_rate=float(score) * 160_000.0,
            source="demo",
        )
        return snap.as_dict()

    if _is_probable_crypto(entity):
        coin = _coingecko_lookup(entity)
        if coin:
            change_7d = float(coin.get("price_change_percentage_7d_in_currency") or 0.0)
            market_cap = float(coin.get("market_cap") or 0.0)
            price = float(coin.get("current_price") or 0.0)
            momentum = max(-20.0, min(30.0, change_7d))
            base = 64 + int(momentum)
            score = max(0, min(100, base))
            revenue = market_cap * 0.03
            burn = max(120000.0, market_cap * 0.005)
            return FinancialSnapshot(
                score=score,
                market_cap=market_cap,
                price_change_7d=change_7d,
                price=price,
                revenue_estimate=revenue,
                burn_rate=burn,
                source="coingecko",
            ).as_dict()

    eq = _yahoo_lookup(entity)
    if eq:
        change_7d = float(eq.get("price_change_7d") or 0.0)
        market_cap = float(eq.get("market_cap") or 0.0)
        revenue = float(eq.get("revenue") or 0.0)
        price = float(eq.get("current_price") or 0.0)
        score = max(0, min(100, 58 + int(max(-15.0, min(22.0, change_7d)))))
        burn = max(80000.0, (revenue * 0.012) if revenue else market_cap * 0.004)
        return FinancialSnapshot(
            score=score,
            market_cap=market_cap,
            price_change_7d=change_7d,
            price=price,
            revenue_estimate=revenue,
            burn_rate=burn,
            source="yfinance",
        ).as_dict()

    # Resilient fallback if no provider data is available.
    seed = _hash_score(f"fallback:{entity}", 42, 74)
    return FinancialSnapshot(
        score=seed,
        market_cap=float(seed) * 1_800_000.0,
        price_change_7d=float((seed % 18) - 6),
        price=float(seed) * 1.2,
        revenue_estimate=float(seed) * 250_000.0,
        burn_rate=float(seed) * 140_000.0,
        source="fallback",
    ).as_dict()

