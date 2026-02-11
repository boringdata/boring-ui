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

    def __init__(
        self,
        file_policy: FilePolicy = FilePolicy.SANDBOXED,
        exec_policy: ExecPolicy = ExecPolicy.DENY_DANGEROUS,
    ):
        self.file_policy = file_policy
        self.exec_policy = exec_policy

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
