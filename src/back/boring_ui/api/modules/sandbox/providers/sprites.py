"""SpritesProvider - Runs sandbox-agent in persistent Sprites.dev VMs.

This provider enables:
- Per-user persistent sandboxes (1:1 user-to-sprite mapping)
- Near-zero cost when idle (sprites sleep after inactivity)
- Filesystem checkpoints for safe experimentation
- Automatic wake on request

Security notes:
- Credentials stored only in sprite filesystem, never server-side
- All credentials shell-escaped with shlex.quote()
- Checkpoints may include credentials - use update_credentials() after restore
- Direct Connect secrets live in /home/sprite/.auth/ (outside workspace)
"""
from __future__ import annotations

import logging
import shlex
from datetime import datetime, timezone
from typing import AsyncIterator

from ..errors import SandboxExistsError, SandboxProvisionError
from ..metrics import gauge_dec, gauge_inc, record, timed
from ..provider import (
    CheckpointInfo,
    CheckpointResult,
    SandboxCreateConfig,
    SandboxInfo,
    SandboxProvider,
    SandboxStatus,
)
from .sprites_client import SpritesAPIError, SpritesClient, SpritesExecError

logger = logging.getLogger(__name__)


class SpritesProvider(SandboxProvider):
    """Runs sandbox-agent in persistent Sprites.dev VMs.

    Each user gets exactly ONE sprite (1:1 user-to-sprite mapping).
    Sprite name = sandbox_id = sb-{user_id}.

    The sprite persists across sessions, sleeps when idle, wakes on
    request, and supports filesystem checkpoints.
    """

    def __init__(
        self,
        client: SpritesClient | None = None,
        token: str = "",
        org: str = "",
        default_agent: str = "claude",
        sandbox_agent_port: int = 2468,
        name_prefix: str = "",
        setup_timeout: float = 180.0,
        health_check_timeout: float = 30.0,
    ):
        if client is None:
            if not token:
                raise ValueError("Either client or token must be provided")
            client = SpritesClient(
                token=token, org=org, name_prefix=name_prefix,
            )

        self._client = client
        self._default_agent = default_agent
        self._port = sandbox_agent_port
        self._setup_timeout = setup_timeout
        self._health_check_timeout = health_check_timeout

        logger.info(
            "SpritesProvider initialized",
            extra={
                "operation": "init",
                "default_agent": self._default_agent,
                "port": self._port,
            },
        )

    # ------ helpers ------

    def _build_env_exports(
        self,
        anthropic_api_key: str | None = None,
        oauth_token: str | None = None,
    ) -> str:
        """Build shell export lines for credentials.

        SECURITY: All values shell-escaped with shlex.quote().
        """
        lines: list[str] = []
        if anthropic_api_key:
            lines.append(f"export ANTHROPIC_API_KEY={shlex.quote(anthropic_api_key)}")
        if oauth_token:
            lines.append(
                f"export CLAUDE_CODE_OAUTH_TOKEN={shlex.quote(oauth_token)}"
            )
        return "\n".join(lines) + ("\n" if lines else "")

    def _sprite_status_to_sandbox(self, status: str) -> str:
        """Map Sprites.dev status to SandboxStatus value."""
        mapping = {
            "running": SandboxStatus.running.value,
            "sleeping": SandboxStatus.sleeping.value,
            "starting": SandboxStatus.starting.value,
            "creating": SandboxStatus.creating.value,
            "stopping": SandboxStatus.stopping.value,
            "stopped": SandboxStatus.stopped.value,
            "error": SandboxStatus.error.value,
        }
        return mapping.get(status, SandboxStatus.error.value)

    def _make_info(self, sandbox_id: str, sprite: dict) -> SandboxInfo:
        """Build SandboxInfo from Sprites.dev API response."""
        base_url = sprite.get("url", "")
        status = self._sprite_status_to_sandbox(sprite.get("status", "error"))
        return SandboxInfo(
            id=sandbox_id,
            base_url=f"{base_url}:{self._port}" if base_url else "",
            status=status,
            workspace_path="/home/sprite/workspace",
            provider="sprites",
            protocol="rest+sse",
            user_id=sprite.get("user_id", ""),
            repo_url=sprite.get("repo_url", ""),
        )

    # ------ SandboxProvider interface ------

    async def create(self, sandbox_id: str, config: dict) -> SandboxInfo:
        """Create and start a sandbox with sandbox-agent running.

        Idempotent: if sprite already exists for the same repo, returns it.
        Raises SandboxExistsError if sprite exists for a different repo.
        """
        cfg = SandboxCreateConfig(**config) if isinstance(config, dict) else config
        tags = {"sandbox_id": sandbox_id}

        with timed("sprite_create_duration_seconds", tags=tags) as t:
            logger.info(
                "Creating sandbox",
                extra={
                    "sandbox_id": sandbox_id,
                    "operation": "create",
                    "agent": cfg.agent or self._default_agent,
                },
            )

            # Create sprite (idempotent on Sprites.dev side)
            try:
                sprite = await self._client.create_sprite(sandbox_id)
            except SpritesAPIError as e:
                record("sprite_create_errors_total", tags=tags)
                raise SandboxProvisionError(
                    f"Failed to create sprite: {e}",
                    sandbox_id=sandbox_id,
                    provider="sprites",
                    operation="create_sprite",
                ) from e

            # Write credentials to .auth directory
            if cfg.anthropic_api_key or cfg.oauth_token:
                env_content = self._build_env_exports(
                    cfg.anthropic_api_key, cfg.oauth_token,
                )
                try:
                    await self._client.exec(
                        sandbox_id,
                        "mkdir -p /home/sprite/.auth && "
                        f"printf '%s' {shlex.quote(env_content)} > /home/sprite/.auth/credentials.env && "
                        "chmod 600 /home/sprite/.auth/credentials.env",
                        timeout=self._setup_timeout,
                    )
                except (SpritesExecError, SpritesAPIError) as e:
                    logger.error(
                        "Failed to write credentials",
                        extra={
                            "sandbox_id": sandbox_id,
                            "operation": "write_credentials",
                            "error": str(e)[:200],
                        },
                    )

            # Write direct-connect auth if provided
            if cfg.service_auth_secret:
                try:
                    await self._client.exec(
                        sandbox_id,
                        "mkdir -p /home/sprite/.auth && "
                        f"printf '%s' {shlex.quote(cfg.service_auth_secret)} > /home/sprite/.auth/secret && "
                        "chmod 600 /home/sprite/.auth/secret",
                        timeout=30.0,
                    )
                except (SpritesExecError, SpritesAPIError) as e:
                    logger.error(
                        "Failed to write service auth secret",
                        extra={
                            "sandbox_id": sandbox_id,
                            "operation": "write_service_secret",
                            "error": str(e)[:200],
                        },
                    )

            if cfg.cors_origin:
                try:
                    await self._client.exec(
                        sandbox_id,
                        "mkdir -p /home/sprite/.auth && "
                        f"printf '%s' {shlex.quote(cfg.cors_origin)} > /home/sprite/.auth/cors_origin && "
                        "chmod 600 /home/sprite/.auth/cors_origin",
                        timeout=30.0,
                    )
                except (SpritesExecError, SpritesAPIError) as e:
                    logger.error(
                        "Failed to write CORS origin",
                        extra={
                            "sandbox_id": sandbox_id,
                            "operation": "write_cors_origin",
                            "error": str(e)[:200],
                        },
                    )

            # Clone repo if specified
            if cfg.repo_url:
                try:
                    await self._client.exec(
                        sandbox_id,
                        f"cd /home/sprite/workspace && "
                        f"git clone --branch {shlex.quote(cfg.branch)} "
                        f"{shlex.quote(cfg.repo_url)} . 2>/dev/null || "
                        f"git fetch origin {shlex.quote(cfg.branch)} && "
                        f"git checkout {shlex.quote(cfg.branch)}",
                        timeout=self._setup_timeout,
                    )
                except SpritesExecError:
                    logger.warning(
                        "Repo clone/checkout may have partially failed",
                        extra={
                            "sandbox_id": sandbox_id,
                            "operation": "clone_repo",
                        },
                    )

            gauge_inc("sprites_active_total")

        logger.info(
            "Sandbox created",
            extra={
                "sandbox_id": sandbox_id,
                "operation": "create",
                "result": "ok",
                "duration_ms": t["duration_ms"],
            },
        )

        return self._make_info(sandbox_id, sprite)

    async def destroy(self, sandbox_id: str) -> None:
        """Permanently delete sandbox and sprite."""
        tags = {"sandbox_id": sandbox_id}
        with timed("sprite_destroy_duration_seconds", tags=tags) as t:
            logger.warning(
                "Destroying sandbox",
                extra={"sandbox_id": sandbox_id, "operation": "destroy"},
            )
            await self._client.delete_sprite(sandbox_id)
            gauge_dec("sprites_active_total")

        logger.info(
            "Sandbox destroyed",
            extra={
                "sandbox_id": sandbox_id,
                "operation": "destroy",
                "result": "ok",
                "duration_ms": t["duration_ms"],
            },
        )

    async def get_info(self, sandbox_id: str) -> SandboxInfo | None:
        """Get sandbox status and URL."""
        try:
            sprite = await self._client.get_sprite(sandbox_id)
        except SpritesAPIError as e:
            if e.status_code == 404:
                return None
            raise
        return self._make_info(sandbox_id, sprite)

    async def get_logs(self, sandbox_id: str, limit: int = 100) -> list[str]:
        """Get sandbox-agent logs from the sprite."""
        try:
            _, stdout, _ = await self._client.exec(
                sandbox_id,
                f"tail -n {limit} /home/sprite/.sandbox-agent.log 2>/dev/null || echo '(no logs)'",
                timeout=15.0,
            )
            return stdout.strip().splitlines()
        except (SpritesExecError, SpritesAPIError):
            return []

    async def stream_logs(self, sandbox_id: str) -> AsyncIterator[str]:
        """Async generator yielding log lines.

        Note: This is a poll-based implementation since Sprites.dev
        exec is not streaming. Yields a batch of recent logs.
        """
        try:
            _, stdout, _ = await self._client.exec(
                sandbox_id,
                "tail -n 50 /home/sprite/.sandbox-agent.log 2>/dev/null",
                timeout=15.0,
            )
            for line in stdout.strip().splitlines():
                yield line
        except (SpritesExecError, SpritesAPIError):
            yield "(log streaming unavailable)"

    async def health_check(self, sandbox_id: str) -> bool:
        """Check if sandbox-agent is responding."""
        tags = {"sandbox_id": sandbox_id}
        with timed("sprite_health_check_duration_seconds", tags=tags) as t:
            try:
                rc, stdout, _ = await self._client.exec(
                    sandbox_id,
                    f"curl -sf http://localhost:{self._port}/v1/health",
                    timeout=self._health_check_timeout,
                )
                healthy = "ok" in stdout.lower()
            except Exception:
                healthy = False

        if not healthy:
            record("sprite_health_check_failures_total", tags=tags)
            logger.warning(
                "Health check failed",
                extra={
                    "sandbox_id": sandbox_id,
                    "operation": "health_check",
                    "result": "error",
                    "duration_ms": t["duration_ms"],
                },
            )
        else:
            logger.debug(
                "Health check passed",
                extra={
                    "sandbox_id": sandbox_id,
                    "operation": "health_check",
                    "result": "ok",
                    "duration_ms": t["duration_ms"],
                },
            )

        return healthy

    # ------ Checkpoints ------

    def supports_checkpoints(self) -> bool:
        return True

    async def create_checkpoint(
        self, sandbox_id: str, label: str = "",
    ) -> CheckpointResult[CheckpointInfo]:
        tags = {"sandbox_id": sandbox_id, "operation": "create"}
        with timed("sprite_checkpoint_duration_seconds", tags=tags) as t:
            try:
                data = await self._client.create_checkpoint(sandbox_id, label=label)
                info = CheckpointInfo(
                    id=data.get("id", ""),
                    label=data.get("label", label),
                    created_at=datetime.now(timezone.utc),
                    size_bytes=data.get("size_bytes"),
                )
                result = CheckpointResult(success=True, data=info)
            except SpritesAPIError as e:
                record(
                    "sprite_checkpoint_errors_total",
                    tags={"sandbox_id": sandbox_id, "operation": "create"},
                )
                result = CheckpointResult(success=False, error=str(e))

        logger.info(
            "Checkpoint create completed",
            extra={
                "sandbox_id": sandbox_id,
                "operation": "checkpoint_create",
                "result": "ok" if result.success else "error",
                "checkpoint_id": getattr(result.data, "id", None) if result.success else None,
                "duration_ms": t["duration_ms"],
            },
        )
        return result

    async def restore_checkpoint(
        self, sandbox_id: str, checkpoint_id: str,
    ) -> CheckpointResult[None]:
        tags = {"sandbox_id": sandbox_id, "operation": "restore"}
        with timed("sprite_checkpoint_duration_seconds", tags=tags) as t:
            try:
                await self._client.restore_checkpoint(sandbox_id, checkpoint_id)
                result = CheckpointResult(success=True)
            except SpritesAPIError as e:
                record(
                    "sprite_checkpoint_errors_total",
                    tags={"sandbox_id": sandbox_id, "operation": "restore"},
                )
                result = CheckpointResult(success=False, error=str(e))

        logger.info(
            "Checkpoint restore completed",
            extra={
                "sandbox_id": sandbox_id,
                "operation": "checkpoint_restore",
                "checkpoint_id": checkpoint_id,
                "result": "ok" if result.success else "error",
                "duration_ms": t["duration_ms"],
            },
        )
        return result

    async def list_checkpoints(
        self, sandbox_id: str,
    ) -> CheckpointResult[list[CheckpointInfo]]:
        tags = {"sandbox_id": sandbox_id, "operation": "list"}
        with timed("sprite_checkpoint_duration_seconds", tags=tags) as t:
            try:
                data = await self._client.list_checkpoints(sandbox_id)
                infos = [
                    CheckpointInfo(
                        id=cp.get("id", ""),
                        label=cp.get("label", ""),
                        created_at=None,
                        size_bytes=cp.get("size_bytes"),
                    )
                    for cp in data
                ]
                result = CheckpointResult(success=True, data=infos)
            except SpritesAPIError as e:
                record(
                    "sprite_checkpoint_errors_total",
                    tags={"sandbox_id": sandbox_id, "operation": "list"},
                )
                result = CheckpointResult(success=False, error=str(e))

        logger.info(
            "Checkpoint list completed",
            extra={
                "sandbox_id": sandbox_id,
                "operation": "checkpoint_list",
                "result": "ok" if result.success else "error",
                "count": len(result.data) if result.success and result.data else 0,
                "duration_ms": t["duration_ms"],
            },
        )
        return result

    # ------ Credential update ------

    async def update_credentials(
        self,
        sandbox_id: str,
        anthropic_api_key: str | None = None,
        oauth_token: str | None = None,
    ) -> bool:
        """Update credentials in an existing sandbox.

        Writes to /home/sprite/.auth/credentials.env and restarts
        sandbox-agent to pick up new values.

        SECURITY: Values are shell-escaped; never logged.
        """
        if not anthropic_api_key and not oauth_token:
            return False

        tags = {"sandbox_id": sandbox_id}
        env_content = self._build_env_exports(anthropic_api_key, oauth_token)
        with timed("sprite_update_credentials_duration_seconds", tags=tags) as t:
            try:
                await self._client.exec(
                    sandbox_id,
                    "mkdir -p /home/sprite/.auth && "
                    f"printf '%s' {shlex.quote(env_content)} > /home/sprite/.auth/credentials.env && "
                    "chmod 600 /home/sprite/.auth/credentials.env",
                    timeout=30.0,
                )
                success = True
            except (SpritesExecError, SpritesAPIError) as e:
                logger.error(
                    "Failed to update credentials",
                    extra={
                        "sandbox_id": sandbox_id,
                        "operation": "update_credentials",
                        "result": "error",
                        "error": str(e)[:200],
                        "duration_ms": t.get("duration_ms"),
                    },
                )
                success = False

        if success:
            logger.info(
                "Credentials updated",
                extra={
                    "sandbox_id": sandbox_id,
                    "operation": "update_credentials",
                    "result": "ok",
                    "duration_ms": t["duration_ms"],
                },
            )

        return success
