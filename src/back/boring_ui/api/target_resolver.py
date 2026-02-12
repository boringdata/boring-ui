"""Target resolver interface for determining workspace endpoint location (bd-1adh.3.2).

This module defines the seam for workspace-to-provider resolution, allowing easy
replacement from hardcoded (StaticTargetResolver) to DB-backed (DbTargetResolver)
without control-plane call-site changes.

In Sprites mode: Returns sprite_name and local_api_port for proxy transport.
In non-Sprites hosted: Returns internal_base_url for direct HTTP transport.
In local mode: No resolution needed (in-process mounting).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import os


@dataclass
class WorkspaceTarget:
    """Resolved target location for workspace operations.

    Exactly one of sprite_name or internal_base_url will be set,
    depending on the provider.

    Attributes:
        provider: Provider type ('sprites', 'sandbox', 'local')
        sprite_name: Target sprite name (for Sprites provider only)
        local_api_port: Port where local-api listens in the sprite (for Sprites)
        internal_base_url: Base URL for non-Sprites hosted providers
    """
    provider: str
    sprite_name: str | None = None
    local_api_port: int | None = None
    internal_base_url: str | None = None

    def __post_init__(self):
        """Validate that exactly the right fields are set for the provider."""
        if self.provider == "sprites":
            if not self.sprite_name or self.local_api_port is None:
                raise ValueError(
                    f"Sprites provider requires sprite_name and local_api_port, "
                    f"got sprite_name={self.sprite_name}, port={self.local_api_port}"
                )
            if self.internal_base_url is not None:
                raise ValueError(
                    "Sprites provider should not have internal_base_url set"
                )
        else:
            # Non-Sprites hosted
            if not self.internal_base_url:
                raise ValueError(
                    f"Non-Sprites provider ({self.provider}) requires internal_base_url"
                )
            if self.sprite_name is not None or self.local_api_port is not None:
                raise ValueError(
                    f"Non-Sprites provider should not have sprite_name or local_api_port set"
                )


class TargetResolver(ABC):
    """Abstract interface for resolving workspace targets.

    Implementations determine where file/git/exec endpoints are located
    based on workspace and user context, enabling migration from static
    (hardcoded) to dynamic (database-backed) resolution.
    """

    @abstractmethod
    async def resolve(
        self,
        workspace_id: str,
        user_id: str | None = None,
    ) -> WorkspaceTarget:
        """Resolve the target for a workspace.

        Args:
            workspace_id: Workspace identifier
            user_id: User identifier (optional, may be needed for policy later)

        Returns:
            WorkspaceTarget with provider and location details

        Raises:
            ValueError: If workspace not found or resolution fails
        """
        ...


class StaticTargetResolver(TargetResolver):
    """Static resolver with hardcoded values from environment (bd-1adh.3.2).

    Used during move-fast phase for single-sprite mapping.
    Preserves interface for future DB-backed replacement.

    For Sprites: Reads SPRITES_TARGET_SPRITE and SPRITES_LOCAL_API_PORT from env.
    For non-Sprites hosted: Reads INTERNAL_SANDBOX_URL from env.
    """

    def __init__(self, provider: str):
        """Initialize resolver with provider type.

        Args:
            provider: Provider type ('sprites', 'sandbox', 'local', etc.)

        Raises:
            ValueError: If required env vars are missing for the provider
        """
        self.provider = provider

        if provider == "sprites":
            self.sprite_name = os.environ.get("SPRITES_TARGET_SPRITE")
            port_str = os.environ.get("SPRITES_LOCAL_API_PORT", "8001")

            if not self.sprite_name:
                raise ValueError(
                    "StaticTargetResolver with provider='sprites' requires "
                    "SPRITES_TARGET_SPRITE env var"
                )

            try:
                self.local_api_port = int(port_str)
            except ValueError:
                raise ValueError(
                    f"SPRITES_LOCAL_API_PORT must be an integer, got '{port_str}'"
                )

            self.internal_base_url = None
        else:
            # Non-Sprites hosted
            self.internal_base_url = os.environ.get("INTERNAL_SANDBOX_URL")

            if not self.internal_base_url:
                raise ValueError(
                    f"StaticTargetResolver with provider='{provider}' requires "
                    "INTERNAL_SANDBOX_URL env var"
                )

            self.sprite_name = None
            self.local_api_port = None

    async def resolve(
        self,
        workspace_id: str,
        user_id: str | None = None,
    ) -> WorkspaceTarget:
        """Resolve using static hardcoded values.

        Args:
            workspace_id: Ignored (static mapping)
            user_id: Ignored (static mapping)

        Returns:
            WorkspaceTarget with provider and configured location
        """
        if self.provider == "sprites":
            return WorkspaceTarget(
                provider="sprites",
                sprite_name=self.sprite_name,
                local_api_port=self.local_api_port,
            )
        else:
            return WorkspaceTarget(
                provider=self.provider,
                internal_base_url=self.internal_base_url,
            )
