"""Stub HTTP server emulating the Sprites.dev REST API.

Supports sprite CRUD, checkpoints, and configurable error injection.
Runs as an asyncio HTTP server on a free port.

Usage as a pytest fixture::

    @pytest.fixture
    async def sprites_api():
        async with StubSpritesAPI() as api:
            yield api
"""
from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any


@dataclass
class SpriteState:
    """In-memory state for a single sprite."""

    name: str
    status: str = "running"
    url: str = ""
    checkpoints: list[dict] = field(default_factory=list)
    user_id: str = ""
    repo_url: str = ""


class StubSpritesAPI:
    """Minimal Sprites.dev REST API stub.

    Endpoints:
        POST   /orgs/{org}/sprites                         - create sprite
        GET    /orgs/{org}/sprites                         - list sprites
        GET    /orgs/{org}/sprites/{name}                  - get sprite
        DELETE /orgs/{org}/sprites/{name}                  - delete sprite
        POST   /orgs/{org}/sprites/{name}/checkpoints      - create checkpoint
        GET    /orgs/{org}/sprites/{name}/checkpoints      - list checkpoints
        POST   /orgs/{org}/sprites/{name}/checkpoints/{id}/restore - restore

    Error injection:
        Set ``inject_error`` to a dict ``{status_code: int, message: str}``
        to make the next request fail with that error. Clears after use.
        Set ``inject_error_count`` to make N consecutive requests fail.
    """

    def __init__(self, org: str = "test-org") -> None:
        self.org = org
        self.sprites: dict[str, SpriteState] = {}
        self.inject_error: dict[str, Any] | None = None
        self.inject_error_count: int = 1
        self._inject_remaining: int = 0
        self.request_log: list[dict] = []
        self._server: asyncio.Server | None = None
        self._host = "127.0.0.1"
        self._port = 0

    @property
    def base_url(self) -> str:
        return f"http://{self._host}:{self._port}"

    async def __aenter__(self) -> StubSpritesAPI:
        await self.start()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.stop()

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self._handle_connection, self._host, 0,
        )
        addrs = self._server.sockets[0].getsockname()
        self._port = addrs[1]

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    def set_error(
        self, status_code: int, message: str = "injected error", count: int = 1,
    ) -> None:
        """Inject an error for the next N requests."""
        self.inject_error = {"status_code": status_code, "message": message}
        self.inject_error_count = count
        self._inject_remaining = count

    def clear_error(self) -> None:
        self.inject_error = None
        self._inject_remaining = 0

    # ---- HTTP handling ----

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
    ) -> None:
        try:
            data = await reader.read(65536)
            if not data:
                return

            request_line, _, rest = data.partition(b"\r\n")
            method, path, _ = request_line.decode().split(" ", 2)
            headers_raw, _, body_raw = rest.partition(b"\r\n\r\n")

            body: dict = {}
            if body_raw:
                try:
                    body = json.loads(body_raw)
                except (json.JSONDecodeError, ValueError):
                    pass

            self.request_log.append({"method": method, "path": path, "body": body})

            # Check injected error
            if self.inject_error and self._inject_remaining > 0:
                self._inject_remaining -= 1
                if self._inject_remaining <= 0:
                    err = self.inject_error
                    self.inject_error = None
                else:
                    err = self.inject_error
                status = err["status_code"]
                resp_body = json.dumps({"error": err["message"]})
                self._write_response(writer, status, resp_body)
                return

            status, resp_body = self._route(method, path, body)
            self._write_response(writer, status, resp_body)
        except Exception:
            self._write_response(writer, 500, '{"error":"internal stub error"}')
        finally:
            writer.close()
            await writer.wait_closed()

    def _write_response(
        self, writer: asyncio.StreamWriter, status: int, body: str,
    ) -> None:
        reason = HTTPStatus(status).phrase
        resp = (
            f"HTTP/1.1 {status} {reason}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"\r\n"
            f"{body}"
        )
        writer.write(resp.encode())

    def _route(self, method: str, path: str, body: dict) -> tuple[int, str]:
        """Route request to handler, return (status_code, json_body_str)."""
        parts = [p for p in path.split("/") if p]

        # /orgs/{org}/sprites
        if len(parts) == 3 and parts[0] == "orgs" and parts[2] == "sprites":
            org = parts[1]
            if org != self.org:
                return 404, json.dumps({"error": f"org {org} not found"})
            if method == "GET":
                return self._list_sprites()
            if method == "POST":
                return self._create_sprite(body)

        # /orgs/{org}/sprites/{name}
        if len(parts) == 4 and parts[0] == "orgs" and parts[2] == "sprites":
            name = parts[3]
            if method == "GET":
                return self._get_sprite(name)
            if method == "DELETE":
                return self._delete_sprite(name)

        # /orgs/{org}/sprites/{name}/checkpoints
        if (
            len(parts) == 5
            and parts[0] == "orgs"
            and parts[2] == "sprites"
            and parts[4] == "checkpoints"
        ):
            name = parts[3]
            if method == "GET":
                return self._list_checkpoints(name)
            if method == "POST":
                return self._create_checkpoint(name, body)

        # /orgs/{org}/sprites/{name}/checkpoints/{id}/restore
        if (
            len(parts) == 7
            and parts[0] == "orgs"
            and parts[2] == "sprites"
            and parts[4] == "checkpoints"
            and parts[6] == "restore"
        ):
            name = parts[3]
            checkpoint_id = parts[5]
            if method == "POST":
                return self._restore_checkpoint(name, checkpoint_id)

        return 404, json.dumps({"error": "not found"})

    # ---- handlers ----

    def _list_sprites(self) -> tuple[int, str]:
        sprites = [
            {"name": s.name, "status": s.status, "url": s.url}
            for s in self.sprites.values()
        ]
        return 200, json.dumps(sprites)

    def _create_sprite(self, body: dict) -> tuple[int, str]:
        name = body.get("name", "")
        if not name:
            return 400, json.dumps({"error": "name required"})
        if name in self.sprites:
            # Idempotent: return existing
            s = self.sprites[name]
            return 200, json.dumps({"name": s.name, "status": s.status, "url": s.url})
        sprite = SpriteState(
            name=name,
            url=f"https://{name}.sprites.app",
        )
        self.sprites[name] = sprite
        return 200, json.dumps({"name": sprite.name, "status": sprite.status, "url": sprite.url})

    def _get_sprite(self, name: str) -> tuple[int, str]:
        sprite = self.sprites.get(name)
        if not sprite:
            return 404, json.dumps({"error": f"sprite {name} not found"})
        return 200, json.dumps({
            "name": sprite.name, "status": sprite.status, "url": sprite.url,
        })

    def _delete_sprite(self, name: str) -> tuple[int, str]:
        if name in self.sprites:
            del self.sprites[name]
        return 204, ""

    def _create_checkpoint(self, name: str, body: dict) -> tuple[int, str]:
        sprite = self.sprites.get(name)
        if not sprite:
            return 404, json.dumps({"error": "sprite not found"})
        cp = {
            "id": f"chk-{uuid.uuid4().hex[:8]}",
            "label": body.get("label", ""),
            "size_bytes": 1024,
        }
        sprite.checkpoints.append(cp)
        return 200, json.dumps(cp)

    def _list_checkpoints(self, name: str) -> tuple[int, str]:
        sprite = self.sprites.get(name)
        if not sprite:
            return 404, json.dumps({"error": "sprite not found"})
        return 200, json.dumps(sprite.checkpoints)

    def _restore_checkpoint(
        self, name: str, checkpoint_id: str,
    ) -> tuple[int, str]:
        sprite = self.sprites.get(name)
        if not sprite:
            return 404, json.dumps({"error": "sprite not found"})
        found = any(cp["id"] == checkpoint_id for cp in sprite.checkpoints)
        if not found:
            return 404, json.dumps({"error": f"checkpoint {checkpoint_id} not found"})
        return 200, json.dumps({"status": "restored"})
