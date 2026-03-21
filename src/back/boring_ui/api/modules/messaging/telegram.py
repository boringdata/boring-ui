"""Telegram channel adapter.

Handles webhook registration, incoming updates, and message delivery.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org"


async def set_webhook(bot_token: str, webhook_url: str) -> dict:
    """Register a Telegram webhook URL."""
    async with httpx.AsyncClient(timeout=15.0) as http:
        resp = await http.post(
            f"{_TELEGRAM_API}/bot{bot_token}/setWebhook",
            json={"url": webhook_url},
        )
        return resp.json()


async def delete_webhook(bot_token: str) -> dict:
    """Remove the Telegram webhook."""
    async with httpx.AsyncClient(timeout=15.0) as http:
        resp = await http.post(
            f"{_TELEGRAM_API}/bot{bot_token}/deleteWebhook",
        )
        return resp.json()


async def get_bot_info(bot_token: str) -> dict:
    """Get bot username and info."""
    async with httpx.AsyncClient(timeout=15.0) as http:
        resp = await http.get(f"{_TELEGRAM_API}/bot{bot_token}/getMe")
        data = resp.json()
        if data.get("ok"):
            return data["result"]
        return {}


async def send_message(
    bot_token: str,
    chat_id: int | str,
    text: str,
    *,
    parse_mode: str | None = None,
) -> dict:
    """Send a message to a Telegram chat."""
    # Telegram message limit is 4096 chars
    if len(text) > 4096:
        text = text[:4090] + "\n..."

    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    async with httpx.AsyncClient(timeout=15.0) as http:
        resp = await http.post(
            f"{_TELEGRAM_API}/bot{bot_token}/sendMessage",
            json=payload,
        )
        return resp.json()


async def send_typing(bot_token: str, chat_id: int | str) -> None:
    """Send typing indicator."""
    async with httpx.AsyncClient(timeout=5.0) as http:
        await http.post(
            f"{_TELEGRAM_API}/bot{bot_token}/sendChatAction",
            json={"chat_id": chat_id, "action": "typing"},
        )


def extract_message(update: dict) -> dict | None:
    """Extract message text and chat_id from a Telegram update.

    Returns dict with chat_id, text, user_id, username, or None if not a text message.
    """
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return None

    text = msg.get("text", "").strip()
    if not text:
        return None

    chat = msg.get("chat", {})
    user = msg.get("from", {})

    return {
        "chat_id": chat.get("id"),
        "text": text,
        "user_id": user.get("id"),
        "username": user.get("username", ""),
        "first_name": user.get("first_name", ""),
        "message_id": msg.get("message_id"),
    }
