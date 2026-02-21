from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any, Dict

from flask import Flask, jsonify, request, send_from_directory

from research_engine import (
    add_watchlist,
    ensure_storage,
    load_results,
    load_settings,
    load_watchlist,
    run_research,
    save_settings,
)
from telegram_alerts import InvestTelegramAlerts


APP_DIR = Path(__file__).resolve().parent
PORT = int(os.getenv("PORT", "5001"))

app = Flask(__name__, static_folder=str(APP_DIR), static_url_path="")


@app.after_request
def add_cors_headers(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return resp


@app.route("/", methods=["GET"])
def root():
    return send_from_directory(APP_DIR, "index.html")


@app.route("/dashboard", methods=["GET"])
def dashboard_page():
    return send_from_directory(APP_DIR, "dashboard.html")


@app.route("/report", methods=["GET"])
def report_page():
    return send_from_directory(APP_DIR, "report.html")


@app.route("/settings", methods=["GET"])
def settings_page():
    return send_from_directory(APP_DIR, "settings.html")


@app.route("/api/health", methods=["GET"])
def health():
    ensure_storage()
    return jsonify({"ok": True, "app": "invest_ai_node"})


@app.route("/api/analyze", methods=["GET"])
def api_analyze():
    entity = (request.args.get("entity") or "").strip()
    if not entity:
        return jsonify({"error": "Missing query parameter: entity"}), 400
    settings = load_settings()
    demo_mode = str(request.args.get("demo_mode", "")).lower() in {"1", "true", "yes", "on"}
    try:
        result = asyncio.run(run_research(entity, demo_mode=demo_mode, settings=settings))
    except Exception as exc:
        return jsonify({"error": f"Research failed: {exc}"}), 500

    notifier = InvestTelegramAlerts(
        bot_token=settings.get("telegram_bot_token", ""),
        chat_id=settings.get("telegram_chat_id", ""),
    )
    telegram_sent = notifier.send_investment_card(result) if notifier.active else False
    result["telegram_sent"] = bool(telegram_sent)
    return jsonify(result)


@app.route("/api/portfolio", methods=["GET"])
def api_portfolio():
    rows = load_results()
    return jsonify({"items": rows})


@app.route("/api/watchlist", methods=["POST"])
def api_watchlist():
    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    entity = str(payload.get("entity") or "").strip()
    if not entity:
        return jsonify({"error": "Missing entity"}), 400
    items = add_watchlist(entity)
    return jsonify({"watchlist": items})


@app.route("/api/watchlist", methods=["GET"])
def api_watchlist_get():
    return jsonify({"watchlist": load_watchlist()})


@app.route("/api/settings", methods=["GET"])
def api_settings_get():
    cfg = load_settings()
    return jsonify(cfg)


@app.route("/api/settings", methods=["POST"])
def api_settings_set():
    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    cfg = save_settings(payload)
    return jsonify(cfg)


@app.route("/api/test-telegram", methods=["POST"])
def api_test_telegram():
    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    cfg = load_settings()
    token = str(payload.get("telegram_bot_token") or cfg.get("telegram_bot_token") or "")
    chat_id = str(payload.get("telegram_chat_id") or cfg.get("telegram_chat_id") or "")
    notifier = InvestTelegramAlerts(bot_token=token, chat_id=chat_id)
    ok = notifier.send_test() if notifier.active else False
    return jsonify({"ok": bool(ok), "active": notifier.active})


if __name__ == "__main__":
    ensure_storage()
    app.run(host="0.0.0.0", port=PORT, debug=False)
