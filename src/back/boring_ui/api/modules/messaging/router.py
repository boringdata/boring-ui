"""Messaging gateway router.

Routes external messaging channels (Telegram, Slack, etc.) through the
PI agent service for multi-turn conversations with workspace tools.

Provides:
- POST /channels/telegram/webhook/{workspace_id} — Telegram webhook
- POST /channels/telegram/connect — Register bot token + set webhook
- POST /channels/telegram/disconnect — Remove webhook + clear token
- GET  /channels — List connected channels for a workspace
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from ...config import APIConfig
from ...storage import Storage, LocalStorage
from ...subprocess_git import SubprocessGitBackend
from ...workspace import WorkspaceContext, resolve_workspace_context
from . import telegram

logger = logging.getLogger(__name__)


class TelegramConnectRequest(BaseModel):
    bot_token: str
    workspace_id: str


class TelegramDisconnectRequest(BaseModel):
    workspace_id: str


def _channels_file(workspace_root) -> str:
    """Path to the channels config file in a workspace."""
    return str(workspace_root / ".boring" / "channels.json")


def _read_channels(workspace_root) -> dict[str, Any]:
    """Read the channels config for a workspace."""
    path = _channels_file(workspace_root)
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write_channels(workspace_root, data: dict[str, Any]) -> None:
    """Write the channels config for a workspace."""
    path = _channels_file(workspace_root)
    import pathlib
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _session_id_for_chat(channel: str, chat_id: str) -> str:
    """Deterministic session ID so the same chat always resumes the same PI session."""
    return f"msg-{channel}-{chat_id}"


def create_messaging_router(
    config: APIConfig,
    storage: Storage,
    git_backend=None,
) -> APIRouter:
    """Create the messaging gateway router."""
    router = APIRouter(tags=["messaging"])

    async def _workspace_context(request: Request) -> WorkspaceContext:
        return await resolve_workspace_context(request, config=config, storage=storage)

    def _get_pi_harness(request: Request):
        return getattr(request.app.state, "pi_harness", None)

    @router.post("/channels/telegram/connect")
    async def telegram_connect(body: TelegramConnectRequest, request: Request):
        """Connect a Telegram bot to a workspace."""
        bot_info = await telegram.get_bot_info(body.bot_token)
        if not bot_info:
            return {"ok": False, "error": "Invalid bot token"}

        base_url = str(request.base_url).rstrip("/")
        forwarded_host = request.headers.get("x-forwarded-host")
        forwarded_proto = request.headers.get("x-forwarded-proto", "https")
        if forwarded_host:
            base_url = f"{forwarded_proto}://{forwarded_host}"
        webhook_url = f"{base_url}/api/v1/messaging/channels/telegram/webhook/{body.workspace_id}"

        result = await telegram.set_webhook(body.bot_token, webhook_url)
        if not result.get("ok"):
            return {"ok": False, "error": f"Webhook registration failed: {result}"}

        from ...workspace.paths import resolve_workspace_root
        ws_root = resolve_workspace_root(
            config.workspace_root,
            body.workspace_id,
            single_mode=not config.control_plane_enabled,
        )

        channels = _read_channels(ws_root)
        channels["telegram"] = {
            "bot_token": body.bot_token,
            "bot_username": bot_info.get("username", ""),
            "webhook_url": webhook_url,
        }
        _write_channels(ws_root, channels)

        logger.info(
            "Telegram connected: bot=@%s workspace=%s",
            bot_info.get("username"),
            body.workspace_id,
        )
        return {
            "ok": True,
            "bot_username": bot_info.get("username"),
            "webhook_url": webhook_url,
        }

    @router.post("/channels/telegram/disconnect")
    async def telegram_disconnect(body: TelegramDisconnectRequest):
        """Disconnect Telegram from a workspace."""
        from ...workspace.paths import resolve_workspace_root
        ws_root = resolve_workspace_root(
            config.workspace_root,
            body.workspace_id,
            single_mode=not config.control_plane_enabled,
        )

        channels = _read_channels(ws_root)
        tg_config = channels.get("telegram", {})
        bot_token = tg_config.get("bot_token")

        if bot_token:
            await telegram.delete_webhook(bot_token)

        channels.pop("telegram", None)
        _write_channels(ws_root, channels)

        return {"ok": True}

    @router.post("/channels/telegram/webhook/{workspace_id}")
    async def telegram_webhook(workspace_id: str, request: Request):
        """Receive Telegram webhook updates and route through PI agent service."""
        body = await request.json()

        msg = telegram.extract_message(body)
        if not msg:
            return {"ok": True}

        from ...workspace.paths import resolve_workspace_root
        ws_root = resolve_workspace_root(
            config.workspace_root,
            workspace_id,
            single_mode=not config.control_plane_enabled,
        )

        channels = _read_channels(ws_root)
        tg_config = channels.get("telegram", {})
        bot_token = tg_config.get("bot_token", "")
        if not bot_token:
            logger.warning("Telegram webhook for %s but no bot token configured", workspace_id)
            return {"ok": True}

        pi_harness = _get_pi_harness(request)
        if pi_harness is None:
            await telegram.send_message(
                bot_token, msg["chat_id"],
                "Agent not available (backend agent mode required).",
            )
            return {"ok": True}

        # Typing indicator and harness readiness are independent — run concurrently
        await asyncio.gather(
            telegram.send_typing(bot_token, msg["chat_id"]),
            pi_harness.ensure_ready(),
            return_exceptions=True,
        )

        session_id = _session_id_for_chat("telegram", str(msg["chat_id"]))
        ctx = WorkspaceContext(
            workspace_id=workspace_id,
            root_path=ws_root,
            storage=LocalStorage(ws_root),
            git_backend=SubprocessGitBackend(ws_root),
        )

        try:
            response_text = await pi_harness.prompt_session(
                ctx, session_id, msg["text"],
            )
        except Exception as e:
            logger.exception("Agent error for workspace %s", workspace_id)
            response_text = f"Error: {e}"

        await telegram.send_message(bot_token, msg["chat_id"], response_text)
        return {"ok": True}

    @router.get("/channels")
    async def list_channels(
        ctx: WorkspaceContext = Depends(_workspace_context),
    ):
        """List connected messaging channels for the current workspace."""
        channels = _read_channels(ctx.root_path)
        result = []
        for name, cfg in channels.items():
            entry = {"channel": name, "connected": True}
            if name == "telegram":
                entry["bot_username"] = cfg.get("bot_username", "")
            result.append(entry)
        return {"channels": result}

    return router
