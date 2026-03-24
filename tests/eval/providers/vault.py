"""Vault provider adapter.

Wraps the vault CLI for secret reads, existence checks, and cleanup.
CRITICAL: read_secret() auto-registers returned values with the
SecretRegistry so they get redacted from all artifacts.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any

from tests.eval.redaction import SecretRegistry


class VaultAdapter:
    """Vault provider adapter using the vault CLI.

    The agent token is typically READ-ONLY for ``secret/agent/*``.
    Write/delete operations may fail with permission denied.
    """

    def __init__(
        self,
        registry: SecretRegistry | None = None,
        vault_cmd: str = "vault",
    ) -> None:
        self._registry = registry or SecretRegistry()
        self._cmd = vault_cmd

    @property
    def registry(self) -> SecretRegistry:
        return self._registry

    def _run(self, args: list[str], timeout: int = 15) -> tuple[int, str, str]:
        try:
            r = subprocess.run(
                [self._cmd, *args],
                capture_output=True, text=True, timeout=timeout,
            )
            return r.returncode, r.stdout.strip(), r.stderr.strip()
        except FileNotFoundError:
            return -1, "", f"vault CLI not found: {self._cmd}"
        except subprocess.TimeoutExpired:
            return -2, "", "timeout"

    def read_secret(self, path: str, field: str) -> str | None:
        """Read a secret from Vault and auto-register it for redaction.

        Returns the secret value or None on failure.
        """
        rc, out, _ = self._run(["kv", "get", f"-field={field}", path])
        if rc != 0 or not out:
            return None
        # Auto-register for redaction
        self._registry.register(f"{path}:{field}", out)
        return out

    def secret_exists(self, path: str) -> bool:
        """Check if a Vault secret path exists."""
        rc, _, _ = self._run(["kv", "get", path])
        return rc == 0

    def delete_secret(self, path: str) -> bool:
        """Delete a Vault secret (requires write access)."""
        rc, _, err = self._run(["kv", "delete", path])
        if rc != 0:
            return False
        return True

    def list_secrets(self, prefix: str) -> list[str]:
        """List secret paths under a prefix."""
        rc, out, _ = self._run(["kv", "list", "-format=json", prefix])
        if rc != 0:
            return []
        try:
            return json.loads(out)
        except (json.JSONDecodeError, TypeError):
            return []

    def read_and_register_eval_secrets(self) -> int:
        """Read common eval secrets and register them for redaction.

        Returns the number of secrets successfully registered.
        """
        secrets_to_read = [
            ("secret/agent/anthropic", "api_key"),
            ("secret/agent/boringdata-agent", "token"),
            ("secret/agent/openai", "api_key"),
        ]
        count = 0
        for path, field in secrets_to_read:
            if self.read_secret(path, field) is not None:
                count += 1
        return count
