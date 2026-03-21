"""Execute tool calls against workspace services.

Bridges Claude tool_use blocks to boring-ui's internal services
without HTTP round-trips — direct Python calls.
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from ...config import APIConfig
from ...storage import Storage
from ...git_backend import GitBackend
from ..exec.service import execute_command


async def execute_tool(
    tool_name: str,
    tool_input: dict[str, Any],
    *,
    config: APIConfig,
    storage: Storage,
    git_backend: GitBackend | None = None,
) -> str:
    """Execute a tool call and return the result as a string.

    Calls boring-ui services directly (no HTTP). The config.workspace_root
    must already be set to the target workspace.
    """
    try:
        if tool_name == "read_file":
            from ..files.service import FileService
            svc = FileService(config, storage)
            result = svc.read_file(tool_input["path"])
            return result.get("content", "")

        elif tool_name == "write_file":
            from ..files.service import FileService
            svc = FileService(config, storage)
            svc.write_file(tool_input["path"], tool_input["content"])
            return f"Written to {tool_input['path']}"

        elif tool_name == "list_files":
            from ..files.service import FileService
            svc = FileService(config, storage)
            result = svc.list_directory(tool_input.get("path", "."))
            entries = result.get("entries", [])
            lines = []
            for e in entries:
                marker = "/" if e.get("is_dir") else ""
                lines.append(f"{e['name']}{marker}")
            return "\n".join(lines) or "(empty directory)"

        elif tool_name == "exec_bash":
            result = await execute_command(
                tool_input["command"],
                tool_input.get("cwd"),
                config.workspace_root,
            )
            parts = []
            if result["stdout"]:
                parts.append(result["stdout"])
            if result["stderr"]:
                parts.append(f"[stderr]\n{result['stderr']}")
            if result["exit_code"] != 0:
                parts.append(f"[exit_code] {result['exit_code']}")
            return "\n".join(parts) or "(no output)"

        elif tool_name == "git_status":
            if git_backend:
                result = await git_backend.status(config.workspace_root)
                return json.dumps(result, indent=2)
            # Fallback to exec
            result = await execute_command(
                "git status",
                None,
                config.workspace_root,
            )
            return result["stdout"] or result["stderr"] or "(no output)"

        elif tool_name == "search_files":
            from ..files.service import FileService
            svc = FileService(config, storage)
            result = svc.search_files(tool_input["pattern"], tool_input.get("path", "."))
            matches = result.get("results", [])
            if not matches:
                return "No files found."
            return "\n".join(m["path"] for m in matches)

        else:
            return f"Unknown tool: {tool_name}"

    except Exception as e:
        return f"Error: {e}"
