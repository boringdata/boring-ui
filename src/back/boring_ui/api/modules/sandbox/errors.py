"""Typed error hierarchy for sandbox/provider operations.

All errors carry structured context (sandbox_id, provider, operation)
for logging. Messages are safe to surface to the API layer — they
never leak secrets or internal paths.
"""


class SandboxError(Exception):
    """Base error for all sandbox operations."""

    def __init__(
        self,
        message: str,
        *,
        sandbox_id: str | None = None,
        provider: str | None = None,
        operation: str | None = None,
    ):
        self.sandbox_id = sandbox_id
        self.provider = provider
        self.operation = operation
        super().__init__(message)

    def __repr__(self) -> str:
        parts = [f"{type(self).__name__}({self.args[0]!r}"]
        if self.sandbox_id:
            parts.append(f"sandbox_id={self.sandbox_id!r}")
        if self.provider:
            parts.append(f"provider={self.provider!r}")
        if self.operation:
            parts.append(f"operation={self.operation!r}")
        return ", ".join(parts) + ")"


class SandboxNotFoundError(SandboxError):
    """Requested sandbox does not exist."""

    pass


class SandboxExistsError(SandboxError):
    """A sandbox already exists with incompatible configuration."""

    pass


class SandboxProvisionError(SandboxError):
    """Sandbox setup or provisioning failed."""

    pass


class SandboxTimeoutError(SandboxError):
    """Operation timed out waiting for sandbox response."""

    pass


class SandboxAuthError(SandboxError):
    """Authorization or identity mismatch."""

    pass


class CheckpointError(SandboxError):
    """Checkpoint create/restore/list operation failed."""

    pass


class CheckpointNotSupportedError(CheckpointError):
    """Provider does not support checkpoint operations."""

    pass
