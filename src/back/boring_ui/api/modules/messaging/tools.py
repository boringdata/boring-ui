"""Claude tool definitions that map to boring-ui workspace APIs.

These are the Anthropic API tool schemas the agent can call.
Each tool executes against a workspace's file/git/exec services.
"""
from __future__ import annotations

WORKSPACE_TOOLS = [
    {
        "name": "read_file",
        "description": "Read the contents of a file in the workspace.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to workspace root"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file in the workspace. Creates the file if it doesn't exist.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to workspace root"},
                "content": {"type": "string", "description": "Content to write"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_files",
        "description": "List files and directories at a path in the workspace.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path (default: '.')", "default": "."},
            },
        },
    },
    {
        "name": "exec_bash",
        "description": "Execute a shell command in the workspace. Use for installing packages, running scripts, git operations, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
                "cwd": {"type": "string", "description": "Working directory relative to workspace root"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "git_status",
        "description": "Get the current git status of the workspace.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "search_files",
        "description": "Search for files by name pattern (glob-style) in the workspace.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Search pattern (e.g. '*.py', 'test_*')"},
                "path": {"type": "string", "description": "Directory to search in (default: '.')", "default": "."},
            },
            "required": ["pattern"],
        },
    },
]
