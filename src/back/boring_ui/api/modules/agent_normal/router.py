"""agent-normal HTTP router (runtime-only session lifecycle)."""

from __future__ import annotations

import uuid
from pathlib import Path
import re
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from ...config import APIConfig
from ..pty.lifecycle import list_pty_session_summaries
from ..stream import get_session_registry as get_stream_registry


def _list_stream_session_summaries() -> list[dict[str, Any]]:
    sessions: list[dict[str, Any]] = []
    for session_id, session in get_stream_registry().items():
        sessions.append(
            {
                "id": session_id,
                "type": "stream",
                "alive": session.is_alive(),
                "clients": len(session.clients),
                "history_count": len(session.history),
            }
        )
    return sessions


def _attachment_storage_root(config: APIConfig | None) -> Path:
    base = config.workspace_root if config is not None else Path.cwd()
    return base / ".attachments"


def _extract_attachment_payload(request: Request, body: bytes) -> tuple[str, bytes]:
    content_type = request.headers.get("content-type", "")
    fallback_name = "attachment.bin"
    if "multipart/form-data" not in content_type or "boundary=" not in content_type:
        return fallback_name, body

    boundary = content_type.split("boundary=", maxsplit=1)[1].strip().strip('"')
    boundary_bytes = f"--{boundary}".encode("utf-8")
    for part in body.split(boundary_bytes):
        if b'filename="' not in part:
            continue

        header_body_split = part.find(b"\r\n\r\n")
        if header_body_split == -1:
            continue

        header_block = part[:header_body_split].decode("latin-1", errors="ignore")
        payload = part[header_body_split + 4 :]
        payload = payload.rstrip(b"\r\n")
        if payload.endswith(b"--"):
            payload = payload[:-2].rstrip(b"\r\n")

        filename_match = re.search(r'filename="([^"]+)"', header_block)
        raw_name = filename_match.group(1).strip() if filename_match else fallback_name
        safe_name = Path(raw_name).name.strip() or fallback_name
        return safe_name, payload

    return fallback_name, body


def create_agent_normal_router(
    config: APIConfig | None = None,
    *,
    pty_enabled: bool = True,
) -> APIRouter:
    """Create agent-normal router.

    Note: config is reserved for future policy/claims enforcement; this bead
    only migrates route family + delegation wiring.
    """
    _ = config
    router = APIRouter(tags=["agent-normal"])

    @router.get("/sessions")
    async def list_sessions() -> dict[str, Any]:
        """List active PTY + stream sessions.

        PTY listing is delegated to pty-service.
        """
        pty_sessions = list_pty_session_summaries() if pty_enabled else []
        stream_sessions = _list_stream_session_summaries()
        return {"sessions": pty_sessions + stream_sessions}

    @router.post("/sessions")
    async def create_session() -> dict[str, str]:
        """Create a new session ID (client will connect via WebSocket)."""
        return {"session_id": str(uuid.uuid4())}

    @router.post("/attachments")
    async def upload_attachment(request: Request) -> dict[str, Any]:
        """Upload an attachment into the agent-normal canonical route family."""
        body = await request.body()
        filename, payload = _extract_attachment_payload(request, body)
        if not filename:
            raise HTTPException(status_code=400, detail="Attachment filename is required")

        file_id = uuid.uuid4().hex
        storage_dir = _attachment_storage_root(config)
        storage_dir.mkdir(parents=True, exist_ok=True)
        stored_name = f"{file_id}-{filename}"
        destination = storage_dir / stored_name

        destination.write_bytes(payload)

        return {
            "file_id": file_id,
            "relative_path": str(Path(".attachments") / stored_name),
            "name": filename,
            "size": len(payload),
        }

    return router
