"""Compatibility shim for capability authorization decorators.

Canonical implementation lives in `sandbox_auth` so capability guard logic,
wildcard matching, and decorator plumbing stay single-sourced.
"""

from .sandbox_auth import require_capability, get_capability_context

__all__ = ["require_capability", "get_capability_context"]
