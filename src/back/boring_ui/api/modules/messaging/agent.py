"""Messaging agent — runs Claude with workspace tools in an agentic loop.

Stateless: each message starts a fresh conversation. The agent loops
until Claude produces a final text response (no more tool calls).
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

from ...config import APIConfig
from ...storage import Storage
from ...git_backend import GitBackend
from .tools import WORKSPACE_TOOLS
from .tool_executor import execute_tool

logger = logging.getLogger(__name__)

_MAX_TURNS = 15
_MODEL = "claude-sonnet-4-20250514"

SYSTEM_PROMPT = """\
You are a workspace assistant connected via messaging (Telegram/Slack/etc).
You have access to a development workspace with files, git, and a shell.
Be concise — messaging users prefer short, actionable responses.
When you run commands or read files, summarize the key information.
"""


async def run_agent(
    user_message: str,
    *,
    api_key: str,
    config: APIConfig,
    storage: Storage,
    git_backend: GitBackend | None = None,
    model: str = _MODEL,
    max_turns: int = _MAX_TURNS,
) -> str:
    """Run a single-turn agentic conversation and return the final text.

    Loops: user message → Claude → tool calls → tool results → Claude → ...
    until Claude returns a text response without tool calls.
    """
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": user_message},
    ]

    async with httpx.AsyncClient(timeout=120.0) as http:
        for turn in range(max_turns):
            resp = await http.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 4096,
                    "system": SYSTEM_PROMPT,
                    "tools": WORKSPACE_TOOLS,
                    "messages": messages,
                },
            )

            if resp.status_code != 200:
                logger.error("Anthropic API error: %s %s", resp.status_code, resp.text[:300])
                return f"API error: {resp.status_code}"

            data = resp.json()
            stop_reason = data.get("stop_reason", "")
            content_blocks = data.get("content", [])

            # Collect text and tool_use blocks
            text_parts: list[str] = []
            tool_uses: list[dict[str, Any]] = []

            for block in content_blocks:
                if block.get("type") == "text":
                    text_parts.append(block["text"])
                elif block.get("type") == "tool_use":
                    tool_uses.append(block)

            # If no tool calls, return the final text
            if not tool_uses or stop_reason == "end_turn":
                return "\n".join(text_parts) or "(no response)"

            # Append assistant message with all content blocks
            messages.append({"role": "assistant", "content": content_blocks})

            # Execute tools and build tool_result blocks
            tool_results: list[dict[str, Any]] = []
            for tool_use in tool_uses:
                result_text = await execute_tool(
                    tool_use["name"],
                    tool_use.get("input", {}),
                    config=config,
                    storage=storage,
                    git_backend=git_backend,
                )
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use["id"],
                    "content": result_text,
                })

            messages.append({"role": "user", "content": tool_results})

        return "(max turns reached)"
