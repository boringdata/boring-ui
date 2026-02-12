"""Sandbox module for running sandbox-agent instances.

This module provides a provider abstraction for running sandbox-agent
in different environments (local subprocess, Modal, etc.) with a
unified API for lifecycle management and request proxying.
"""
from .provider import (
    CheckpointInfo,
    CheckpointResult,
    SandboxCreateConfig,
    SandboxInfo,
    SandboxProvider,
    SandboxStatus,
)
from .manager import SandboxManager, create_provider
from .router import create_sandbox_router
from .providers.local import LocalProvider

__all__ = [
    "CheckpointInfo",
    "CheckpointResult",
    "SandboxCreateConfig",
    "SandboxInfo",
    "SandboxProvider",
    "SandboxStatus",
    "SandboxManager",
    "create_provider",
    "create_sandbox_router",
    "LocalProvider",
]
