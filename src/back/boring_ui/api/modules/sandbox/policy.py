"""Policy enforcement for sandbox operations (bd-1pwb.8.1, 8.2, 8.3).

Provides:
- Filesystem access controls
- Git operation policies
- Command execution guardrails
- Network egress controls
- Resource limits
"""

from typing import Optional, Set
from enum import Enum
import re


class FilePolicy(Enum):
    """Filesystem access policies."""
    ALLOW_ALL = "allow_all"  # No restrictions (local mode only)
    SANDBOXED = "sandboxed"  # Limited to workspace_root
    RESTRICTED = "restricted"  # Deny sensitive paths


class ExecPolicy(Enum):
    """Command execution policies."""
    ALLOW_ALL = "allow_all"  # No restrictions (local mode only)
    SAFE_LIST = "safe_list"  # Only whitelisted commands
    DENY_DANGEROUS = "deny_dangerous"  # Block dangerous commands


class NetworkEgressPolicy(Enum):
    """Network egress policies for sandbox child processes."""
    ALLOW_ALL = "allow_all"  # No restrictions (local mode only)
    WORKSPACE_ONLY = "workspace_only"  # Only local workspace services (default)
    DENY_ALL = "deny_all"  # No outbound network access


class SandboxPolicies:
    """Policy enforcement for all sandbox operations."""

    # Sensitive paths (always denied)
    BLOCKED_PATHS = {
        "/etc/passwd",
        "/etc/shadow",
        "/root",
        "/home",
        "~/.ssh",
        "~/.aws",
        "~/.credentials",
    }

    # Dangerous commands (always denied)
    DANGEROUS_COMMANDS = {
        "delete-all",  # recursive deletion
        "dd",
        "mkfs",
        "fdisk",
        ">/dev/null",
        ">/dev/sda",
        "chmod 777",
    }

    # Network-related commands that imply outbound connectivity
    NETWORK_COMMANDS = {
        "curl", "wget", "nc", "ncat", "netcat", "ssh", "scp", "sftp",
        "telnet", "ftp", "rsync", "nmap", "ping",
    }

    def __init__(
        self,
        file_policy: FilePolicy = FilePolicy.SANDBOXED,
        exec_policy: ExecPolicy = ExecPolicy.DENY_DANGEROUS,
        network_egress_policy: NetworkEgressPolicy = NetworkEgressPolicy.WORKSPACE_ONLY,
        egress_allowlist: set[str] | None = None,
    ):
        self.file_policy = file_policy
        self.exec_policy = exec_policy
        self.network_egress_policy = network_egress_policy
        self.egress_allowlist = egress_allowlist or set()

    def allow_file_access(self, path: str) -> bool:
        """Check if file access is allowed."""
        if self.file_policy == FilePolicy.ALLOW_ALL:
            return True

        # Both SANDBOXED and RESTRICTED modes require path validation
        # SANDBOXED: must be validated by caller (workspace_root bounds)
        # RESTRICTED: additionally block sensitive paths
        if self.file_policy == FilePolicy.RESTRICTED:
            # Block sensitive paths
            for blocked in self.BLOCKED_PATHS:
                if path.startswith(blocked):
                    return False

        # Allow access if within sandbox boundary (caller responsible for validation)
        return True

    def allow_command(self, command: str) -> bool:
        """Check if command execution is allowed."""
        if not command or not command.strip():
            return False  # Reject empty commands

        if self.exec_policy == ExecPolicy.ALLOW_ALL:
            return True

        # Always block dangerous commands
        for dangerous in self.DANGEROUS_COMMANDS:
            if dangerous in command:
                return False

        if self.exec_policy == ExecPolicy.SAFE_LIST:
            # Only allow specific commands
            safe_commands = {"ls", "cat", "grep", "echo", "pwd", "git", "npm", "python"}
            parts = command.strip().split()
            if not parts:
                return False
            cmd_name = parts[0]
            return cmd_name in safe_commands

        return True

    def get_resource_limits(self) -> dict:
        """Get resource limits for execution."""
        return {
            "timeout_seconds": 300,  # Max 5 minutes
            "max_memory_mb": 512,  # Max 512MB RAM
            "max_output_lines": 10000,  # Max 10k lines of output
            "max_processes": 10,  # Max 10 concurrent processes
        }

    def allow_network_command(self, command: str) -> bool:
        """Check if a command with network implications is allowed.

        Blocks network-oriented commands (curl, wget, ssh, etc.) when the
        egress policy restricts outbound access. Commands in egress_allowlist
        are always permitted regardless of policy.

        Args:
            command: Full command string to evaluate.

        Returns:
            True if the command is allowed, False if blocked by egress policy.
        """
        if self.network_egress_policy == NetworkEgressPolicy.ALLOW_ALL:
            return True

        parts = command.strip().split()
        if not parts:
            return True

        cmd_name = parts[0]

        # Check allowlist first — overrides policy
        if cmd_name in self.egress_allowlist:
            return True

        if self.network_egress_policy == NetworkEgressPolicy.DENY_ALL:
            return cmd_name not in self.NETWORK_COMMANDS

        # WORKSPACE_ONLY: block raw network tools but allow package managers
        # (npm, pip, git clone) since they need registry access
        if self.network_egress_policy == NetworkEgressPolicy.WORKSPACE_ONLY:
            blocked_in_workspace = {"curl", "wget", "nc", "ncat", "netcat",
                                     "ssh", "scp", "sftp", "telnet", "ftp",
                                     "nmap", "ping"}
            return cmd_name not in blocked_in_workspace

        return True

    def get_egress_posture(self) -> dict:
        """Return the current egress posture for operational visibility.

        Returns:
            Dict with policy name, allowlist, and blocked commands for
            dashboards and audit logs.
        """
        return {
            "policy": self.network_egress_policy.value,
            "allowlist": sorted(self.egress_allowlist),
            "blocked_commands": sorted(self.NETWORK_COMMANDS)
                if self.network_egress_policy != NetworkEgressPolicy.ALLOW_ALL
                else [],
        }


# --- Environment sanitization (bd-1pwb.8.2) ---

# Environment variables that must never leak to child processes.
# These are control-plane secrets that the sandbox exec plane must not inherit.
SENSITIVE_ENV_PREFIXES = (
    "ANTHROPIC_",
    "OPENAI_",
    "VAULT_",
    "SERVICE_AUTH_",
    "OIDC_",
    "HOSTED_API_",
    "SIGNING_KEY",
    "AWS_SECRET",
    "AWS_SESSION",
)

# Proxy env vars that could route sandbox traffic through unintended endpoints
PROXY_ENV_VARS = {
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
}

SENSITIVE_ENV_EXACT = {
    "VAULT_TOKEN",
    "VAULT_ADDR",
    "SERVICE_AUTH_SECRET",
    "HOSTED_API_TOKEN",
    "SIGNING_KEY_HEX",
    "DATABASE_URL",
    "SECRET_KEY",
}


def sanitize_exec_env(
    env: dict[str, str] | None = None,
    strip_proxy: bool = True,
) -> dict[str, str]:
    """Build a clean environment for child processes, stripping control-plane secrets.

    Starts from the provided env (or os.environ) and removes any variable whose
    name matches a sensitive prefix or is in the exact-match blocklist.
    When strip_proxy is True, also removes proxy variables to prevent
    unintended egress routing.

    Args:
        env: Base environment dict. If None, uses os.environ.
        strip_proxy: If True, remove HTTP_PROXY/HTTPS_PROXY/etc.

    Returns:
        Sanitized copy of the environment.
    """
    import os
    base = dict(env) if env is not None else dict(os.environ)
    cleaned = {}
    for key, value in base.items():
        upper_key = key.upper()
        if upper_key in SENSITIVE_ENV_EXACT:
            continue
        if any(upper_key.startswith(prefix) for prefix in SENSITIVE_ENV_PREFIXES):
            continue
        if strip_proxy and key in PROXY_ENV_VARS:
            continue
        cleaned[key] = value
    return cleaned


# --- Secret masking in output (bd-1pwb.8.2) ---

# Patterns that look like secrets in command output.
_SECRET_PATTERNS = [
    # API keys: sk-..., sk-ant-..., key-...
    re.compile(r'\b(sk-[a-zA-Z0-9_-]{20,})\b'),
    re.compile(r'\b(sk-ant-[a-zA-Z0-9_-]{20,})\b'),
    re.compile(r'\b(key-[a-zA-Z0-9_-]{20,})\b'),
    # Vault tokens
    re.compile(r'\b(hvs\.[a-zA-Z0-9_-]{20,})\b'),
    # Bearer/JWT tokens (long base64-ish strings after common prefixes)
    re.compile(r'(Bearer\s+[a-zA-Z0-9_\-\.]{40,})'),
    # Generic long hex secrets (64+ hex chars, likely SHA/key material)
    re.compile(r'\b([0-9a-fA-F]{64,})\b'),
    # AWS secret access keys (40 chars, base64)
    re.compile(r'\b([A-Za-z0-9/+=]{40})\b(?=.*(?:secret|aws|key))', re.IGNORECASE),
]


def mask_secrets(text: str) -> str:
    """Replace known secret patterns in text with redaction markers.

    Args:
        text: Raw command output text.

    Returns:
        Text with secrets replaced by [REDACTED].
    """
    if not text:
        return text
    result = text
    for pattern in _SECRET_PATTERNS:
        result = pattern.sub("[REDACTED]", result)
    return result


def truncate_output(text: str, max_lines: int) -> tuple[str, bool]:
    """Truncate text to max_lines, returning (truncated_text, was_truncated).

    Args:
        text: Output text to potentially truncate.
        max_lines: Maximum number of lines to keep.

    Returns:
        Tuple of (output text, whether truncation occurred).
    """
    if not text:
        return text, False
    lines = text.split("\n")
    if len(lines) <= max_lines:
        return text, False
    truncated = "\n".join(lines[:max_lines])
    return truncated + f"\n... [truncated: {len(lines) - max_lines} lines omitted]", True
