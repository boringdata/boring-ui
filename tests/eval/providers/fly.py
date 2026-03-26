"""Fly.io provider adapter.

Thin wrapper over the Fly CLI for app discovery, URL derivation, and cleanup.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any

from tests.eval.fly_cli import resolve_fly_cli


@dataclass
class AppInfo:
    """Basic Fly app metadata."""
    name: str
    status: str = ""
    hostname: str = ""


class FlyAdapter:
    """Fly.io provider adapter using the fly/flyctl CLI."""

    def __init__(self, fly_cmd: str | None = None) -> None:
        if fly_cmd:
            self._cmd = resolve_fly_cli(fly_cmd) or fly_cmd
            return
        self._cmd = resolve_fly_cli() or "fly"

    def _run(self, args: list[str], timeout: int = 30) -> tuple[int, str, str]:
        try:
            r = subprocess.run(
                [self._cmd, *args],
                capture_output=True, text=True, timeout=timeout,
            )
            return r.returncode, r.stdout.strip(), r.stderr.strip()
        except FileNotFoundError:
            return -1, "", f"fly CLI not found: {self._cmd}"
        except subprocess.TimeoutExpired:
            return -2, "", "timeout"

    def list_apps(self, prefix: str | None = None) -> list[AppInfo]:
        """List Fly apps, optionally filtered by name prefix."""
        rc, out, _ = self._run(["apps", "list", "--json"])
        if rc != 0:
            return []
        try:
            apps = json.loads(out)
            result = [
                AppInfo(
                    name=a.get("Name", a.get("name", "")),
                    status=a.get("Status", a.get("status", "")),
                    hostname=a.get("Hostname", a.get("hostname", "")),
                )
                for a in apps
                if isinstance(a, dict)
            ]
            if prefix:
                result = [a for a in result if a.name.startswith(prefix)]
            return result
        except (json.JSONDecodeError, TypeError):
            return []

    def app_exists(self, app_name: str) -> bool:
        """Check if a Fly app exists."""
        rc, _, _ = self._run(["apps", "show", app_name, "--json"])
        return rc == 0

    def app_url(self, app_name: str) -> str | None:
        """Derive the public URL for a Fly app."""
        if self.app_exists(app_name):
            return f"https://{app_name}.fly.dev"
        return None

    def stop_app(self, app_name: str) -> bool:
        """Stop a Fly app's machines."""
        rc, _, _ = self._run(["apps", "suspend", app_name])
        return rc == 0

    def delete_app(self, app_name: str) -> bool:
        """Delete a Fly app permanently."""
        rc, _, err = self._run(["apps", "destroy", app_name, "--yes"])
        if rc == 0:
            return True

        # Treat an already-missing app as a no-op for idempotent cleanup.
        err_lower = err.lower()
        return "not found" in err_lower or "could not find" in err_lower
