"""Companion module for running The Vibe Companion server.

Manages a Bun-based Companion server as a subprocess for
rich Claude Code chat UI with tool approvals, streaming,
and session management.
"""
from .provider import CompanionProvider, CompanionInfo
from .manager import CompanionManager, create_companion_provider
from .router import create_companion_router

__all__ = [
    "CompanionProvider",
    "CompanionInfo",
    "CompanionManager",
    "create_companion_provider",
    "create_companion_router",
]
