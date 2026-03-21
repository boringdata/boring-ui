"""Messaging gateway module — OpenClaw-style channel integrations.

Connects external messaging channels (Telegram, Slack, etc.) to
workspace AI agents, using boring-ui's file/git/exec APIs as tools.
"""
from .router import create_messaging_router

__all__ = ['create_messaging_router']
