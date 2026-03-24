"""Messaging gateway module — routes external channels through PI agent service.

Connects external messaging channels (Telegram, Slack, etc.) to the
PI agent service for multi-turn conversations with workspace tools.
"""
from .router import create_messaging_router

__all__ = ['create_messaging_router']
