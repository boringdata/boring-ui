"""Bootstrap configuration for internal sandbox API service (bd-1pwb.4.1).

The internal service:
- Runs on a private port (default 2469, separate from public 2468)
- Only accessible from control plane with capability tokens
- NOT advertised in /api/capabilities in HOSTED mode
- Used for privileged operations (direct file/git/exec access)
"""

import os
from dataclasses import dataclass


@dataclass
class InternalSandboxConfig:
    """Configuration for internal sandbox service."""

    port: int = 2469  # Private port, different from public 2468
    host: str = "127.0.0.1"  # Local only by default
    enabled: bool = True
    run_mode: str = "local"

    def bind_address(self) -> str:
        """Get bind address based on run mode."""
        if self.run_mode == "hosted":
            # In hosted mode, bind to all interfaces for internal control-plane access
            return "0.0.0.0"
        return self.host

    @classmethod
    def from_env(cls) -> "InternalSandboxConfig":
        """Create config from environment variables."""
        return cls(
            port=int(os.environ.get("INTERNAL_SANDBOX_PORT", "2469")),
            host=os.environ.get("INTERNAL_SANDBOX_HOST", "127.0.0.1"),
            enabled=os.environ.get("INTERNAL_SANDBOX_ENABLED", "true").lower() == "true",
            run_mode=os.environ.get("BORING_UI_RUN_MODE", "local"),
        )

    def is_private(self) -> bool:
        """Check if this is a private binding (localhost only)."""
        return self.bind_address() == "127.0.0.1"
