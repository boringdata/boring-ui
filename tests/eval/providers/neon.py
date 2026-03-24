"""Neon provider adapter.

Delegates to bui neon commands or direct Neon API for project
discovery, JWKS validation, and cleanup.
"""

from __future__ import annotations

import subprocess
from typing import Any

try:
    import httpx
    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False


class NeonAdapter:
    """Neon provider adapter."""

    def __init__(self, bui_cmd: str = "bui") -> None:
        self._bui = bui_cmd

    def _run(self, args: list[str], timeout: int = 30) -> tuple[int, str, str]:
        try:
            r = subprocess.run(
                args, capture_output=True, text=True, timeout=timeout,
            )
            return r.returncode, r.stdout.strip(), r.stderr.strip()
        except FileNotFoundError:
            return -1, "", f"command not found: {args[0]}"
        except subprocess.TimeoutExpired:
            return -2, "", "timeout"

    def project_exists(self, project_id: str) -> bool:
        """Check if a Neon project exists via bui neon status."""
        rc, out, _ = self._run([self._bui, "neon", "status"])
        if rc != 0:
            return False
        return project_id in out

    def jwks_reachable(self, jwks_url: str) -> bool:
        """Check if a JWKS endpoint is reachable.

        Tries httpx first, falls back to curl.
        """
        if _HAS_HTTPX:
            try:
                resp = httpx.get(jwks_url, timeout=10, follow_redirects=True)
                return resp.status_code == 200
            except Exception:
                pass

        # Fallback: curl
        rc, _, _ = self._run(
            ["curl", "-sSf", "-o", "/dev/null", "-w", "%{http_code}", jwks_url],
            timeout=15,
        )
        return rc == 0

    def destroy_project(self, project_id: str) -> bool:
        """Delete a Neon project via bui neon destroy."""
        rc, _, _ = self._run(
            [self._bui, "neon", "destroy", "--force", "--project-id", project_id],
            timeout=60,
        )
        return rc == 0
