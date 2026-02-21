from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, Optional

import requests


class InvestTelegramAlerts:
    def __init__(self, bot_token: str = "", chat_id: str = "") -> None:
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "").strip()
        self._legacy_notifier = self._load_legacy_notifier()

    def _load_legacy_notifier(self):
        try:
            root = Path(__file__).resolve().parents[1]
            legacy_src = root / "mollbot_startup" / "src"
            if legacy_src.exists():
                sys.path.append(str(legacy_src))
                from telegram_notifier import TelegramNotifier  # type: ignore

                return TelegramNotifier()
        except Exception:
            return None
        return None

    @property
    def active(self) -> bool:
        if self._legacy_notifier is not None and getattr(self._legacy_notifier, "active", False):
            return True
        return bool(self.bot_token and self.chat_id)

    def _post(self, text: str) -> bool:
        if not self.bot_token or not self.chat_id:
            return False
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {"chat_id": self.chat_id, "text": text}
            resp = requests.post(url, json=payload, timeout=12)
            return resp.status_code == 200
        except Exception:
            return False

    def send(self, text: str) -> bool:
        if self._legacy_notifier is not None and getattr(self._legacy_notifier, "active", False):
            try:
                return bool(self._legacy_notifier.send_message(text))
            except Exception:
                pass
        return self._post(text)

    def send_investment_card(self, result: Dict) -> bool:
        text = (
            f"INVESTAI ALERT\n"
            f"Entity: {result.get('entity','?')}\n"
            f"Score: {result.get('score','-')}\n"
            f"Verdict: {result.get('verdict','-')}\n"
            f"Financial: {result.get('financials',{}).get('score','-')}\n"
            f"Founders: {result.get('founders',{}).get('score','-')}\n"
            f"Social: {result.get('social',{}).get('score','-')}"
        )
        return self.send(text)

    def send_test(self) -> bool:
        return self.send("InvestAI test message: Telegram channel is connected.")

