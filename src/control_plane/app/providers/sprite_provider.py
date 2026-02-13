"""SpriteSandboxProvider — real SandboxProvider backed by Sprites.dev.

Bead: bd-1joj.14 (SPR0)

Implements the SandboxProvider protocol using SpritesClient for actual
Sprite sandbox creation, inspection, and deletion. Sandbox names follow
the deterministic pattern: sbx-{app_id}-{workspace_id}-{env}.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from .sprites_client import SpritesClient, SpritesNotFoundError

logger = logging.getLogger(__name__)

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(value: str) -> str:
    """Convert a string to a lowercase, hyphen-separated slug safe for DNS names."""
    return _SLUG_RE.sub("-", value.lower()).strip("-")


def build_sandbox_name(app_id: str, workspace_id: str, env: str = "dev") -> str:
    """Deterministic sandbox name: sbx-{app_id}-{workspace_id}-{env}.

    All components are normalized to lowercase slug-safe tokens.
    """
    return f"sbx-{_slugify(app_id)}-{_slugify(workspace_id)}-{_slugify(env)}"


class SpriteSandboxProvider:
    """SandboxProvider backed by Sprites.dev API.

    Conforms to the SandboxProvider protocol defined in protocols.py:
    - create_sandbox(name, **kwargs) -> dict
    - get_sandbox(name) -> dict | None
    - health_check(name) -> bool
    """

    def __init__(
        self,
        client: SpritesClient,
        *,
        default_env: str = "dev",
        default_profile: str = "default",
    ) -> None:
        self._client = client
        self._default_env = default_env
        self._default_profile = default_profile

    async def create_sandbox(self, name: str, **kwargs: Any) -> dict[str, Any]:
        """Create a Sprite sandbox.

        Args:
            name: The sandbox name (typically from build_sandbox_name).
            **kwargs: Optional overrides:
                - sandbox_profile: Sprite VM profile (default: "default")
                - env: Environment variables to pass to the sandbox
                - workspace_id: For structured logging
                - app_id: For structured logging

        Returns:
            Sprite metadata dict from the API.
        """
        workspace_id = kwargs.get("workspace_id", "")
        sandbox_profile = kwargs.get("sandbox_profile", self._default_profile)
        env_vars = kwargs.get("env")

        logger.info(
            "Creating sandbox: name=%s workspace=%s",
            name,
            workspace_id,
            extra={
                "sandbox_name": name,
                "workspace_id": workspace_id,
            },
        )

        result = await self._client.create_sprite(
            name,
            sandbox_profile=sandbox_profile,
            env=env_vars,
        )

        return {
            **result,
            "name": name,
            "state": "running",
            "runtime_url": f"https://{name}.sprites.dev",
        }

    async def get_sandbox(self, name: str) -> dict[str, Any] | None:
        """Get sandbox metadata by name.

        Returns None if the sandbox doesn't exist.
        """
        try:
            result = await self._client.get_sprite(name)
            return {
                **result,
                "name": name,
                "state": result.get("state", "unknown"),
                "runtime_url": f"https://{name}.sprites.dev",
            }
        except SpritesNotFoundError:
            return None

    async def health_check(self, name: str) -> bool:
        """Check if a sandbox exists and is healthy."""
        try:
            result = await self._client.get_sprite(name)
            return result.get("state") in ("running", "ready")
        except SpritesNotFoundError:
            return False
        except Exception:
            logger.warning(
                "Health check failed for sandbox %s",
                name,
                extra={"sandbox_name": name},
                exc_info=True,
            )
            return False

    async def delete_sandbox(self, name: str) -> None:
        """Delete a sandbox by name.

        Silently succeeds if the sandbox doesn't exist (idempotent).
        """
        try:
            await self._client.delete_sprite(name)
        except SpritesNotFoundError:
            logger.info(
                "Sandbox already deleted: name=%s",
                name,
                extra={"sandbox_name": name},
            )

    async def get_runtime_url(self, name: str) -> str | None:
        """Get the runtime URL for a sandbox.

        Returns None if the sandbox doesn't exist.
        """
        sandbox = await self.get_sandbox(name)
        if sandbox is None:
            return None
        return sandbox.get("runtime_url")
