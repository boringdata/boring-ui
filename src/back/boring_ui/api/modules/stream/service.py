"""
Stream session management service for Claude CLI bridging.

Provides a WebSocket handler that spawns Claude CLI with stream-json format
and bridges input/output through pipes (not PTY). This enables structured
JSON communication for chat interfaces.

Protocol:
- Input (client → server): {"type": "user", "message": "..."}
- Output (server → client): Forward Claude's JSON lines directly
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from collections import deque
from pathlib import Path
from typing import Any, Optional

from fastapi import WebSocket

# Configuration from environment
MAX_HISTORY_LINES = int(os.environ.get("KURT_STREAM_HISTORY_LINES", "1000"))
IDLE_TTL_SECONDS = int(os.environ.get("KURT_STREAM_IDLE_TTL", "60"))
MAX_SESSIONS = int(os.environ.get("KURT_STREAM_MAX_SESSIONS", "20"))

# Default slash commands to send to frontend on connect
# These match the frontend's DEFAULT_SLASH_COMMANDS
DEFAULT_SLASH_COMMANDS = [
    "clear", "model", "thinking", "memory", "permissions",
    "mcp", "hooks", "agents", "help", "compact", "cost",
    "init", "terminal", "restart"
]

# Global session registry
_SESSION_REGISTRY: dict[str, "StreamSession"] = {}
_SESSION_REGISTRY_LOCK = asyncio.Lock()


async def _persist_permission_suggestions(
    suggestions: list[dict[str, Any]], project_root: Optional[str] = None
) -> None:
    """
    Persist permission suggestions to settings files.

    The Claude CLI subprocess cannot reliably persist settings when running in
    stream-json mode, so we must handle it here. This is similar to how the
    VSCode extension handles it.

    Args:
        suggestions: List of permission suggestion objects with:
            - type: "addRules" | "setMode" | "addDirectories"
            - destination: "userSettings" | "projectSettings" | "localSettings" | "session"
            - rules/mode/directories: depends on type
        project_root: Project directory where CLI subprocess is running (if None, uses cwd)
    """
    if not suggestions:
        return

    if project_root:
        project_root_path = Path(project_root)
    else:
        project_root_path = Path.cwd()

    def _normalize_rule(rule_content: Optional[str], tool_name: Optional[str]) -> str:
        if rule_content is None and tool_name:
            return str(tool_name).strip()
        if rule_content is None:
            return ""

        normalized = str(rule_content).strip()
        if not normalized:
            return ""

        if "(" in normalized:
            return normalized

        tool = None
        pattern = normalized
        if ":" in normalized:
            candidate, rest = normalized.split(":", 1)
            candidate = candidate.strip()
            if candidate and candidate.replace("-", "").replace("_", "").isalnum():
                tool = candidate
                pattern = rest.strip()

        if not tool and tool_name:
            tool = str(tool_name).strip()

        if tool:
            pattern = _normalize_rule_pattern(pattern)
            return f"{tool}({pattern})" if pattern else tool

        return normalized

    def _normalize_rule_pattern(pattern: str) -> str:
        normalized = str(pattern or "").strip()
        if not normalized:
            return ""
        if ":" in normalized:
            return normalized
        if normalized.endswith("*"):
            star_index = normalized[:-1].rfind(" ")
            if star_index != -1:
                return f"{normalized[:star_index]}:{normalized[star_index + 1:]}"
            return f"{normalized[:-1]}:*"
        return normalized

    def _rule_bucket(rule: dict[str, Any]) -> str:
        mode = (
            rule.get("mode") or rule.get("ruleMode") or rule.get("behavior") or rule.get("decision")
        )
        if not isinstance(mode, str):
            return "allow"
        mode = mode.lower()
        if mode in ("deny", "reject", "block"):
            return "deny"
        if mode in ("ask", "prompt", "confirm"):
            return "ask"
        return "allow"

    for suggestion in suggestions:
        if not isinstance(suggestion, dict):
            continue

        suggestion_type = suggestion.get("type")
        destination = suggestion.get("destination", "session")

        # Skip session-only suggestions (not persisted to files)
        if destination == "session":
            continue

        # Map destination to file path
        settings_path = None
        if destination == "userSettings":
            settings_path = Path.home() / ".claude" / "settings.json"
        elif destination == "projectSettings":
            settings_path = project_root_path / ".claude" / "settings.json"
        elif destination == "localSettings":
            settings_path = project_root_path / ".claude" / "settings.local.json"
        else:
            print(f"[Stream] Unknown destination: {destination}")
            continue

        print(f"[Stream] Persisting {suggestion_type} to {settings_path}")

        # Ensure directory exists
        settings_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing settings
        if settings_path.exists():
            try:
                with open(settings_path) as f:
                    settings = json.load(f)
            except json.JSONDecodeError:
                settings = {}
        else:
            settings = {}

        # Apply the suggestion
        if suggestion_type == "addRules":
            rules = suggestion.get("rules", [])
            if not isinstance(rules, list):
                continue

            if "permissions" not in settings:
                settings["permissions"] = {}
            for key in ("allow", "deny", "ask"):
                if key not in settings["permissions"]:
                    settings["permissions"][key] = []

            # Add each rule
            for rule in rules:
                if isinstance(rule, str):
                    bucket = "allow"
                    rule_content = _normalize_rule(rule, None)
                elif isinstance(rule, dict):
                    bucket = _rule_bucket(rule)
                    rule_content = _normalize_rule(rule.get("ruleContent"), rule.get("toolName"))
                else:
                    continue

                if not rule_content:
                    continue

                target_list = settings["permissions"][bucket]
                if rule_content not in target_list:
                    target_list.append(rule_content)
                    print(f"[Stream] Added {bucket} rule: {rule_content}")

        elif suggestion_type == "setMode":
            # Set defaultMode in settings
            mode = suggestion.get("mode")
            if mode:
                if "permissions" not in settings:
                    settings["permissions"] = {}
                settings["permissions"]["defaultMode"] = mode
                print(f"[Stream] Set permissions.defaultMode: {mode}")

        elif suggestion_type == "addDirectories":
            directories = suggestion.get("directories", [])
            if not isinstance(directories, list):
                continue

            # Add directories to permissions.additionalDirectories
            if "permissions" not in settings:
                settings["permissions"] = {}
            if "additionalDirectories" not in settings["permissions"]:
                if isinstance(settings.get("allowedDirectories"), list):
                    settings["permissions"]["additionalDirectories"] = settings.pop(
                        "allowedDirectories"
                    )
                else:
                    settings["permissions"]["additionalDirectories"] = []

            for directory in directories:
                if directory and directory not in settings["permissions"]["additionalDirectories"]:
                    settings["permissions"]["additionalDirectories"].append(directory)
                    print(f"[Stream] Added directory: {directory}")

        # Write back to file
        try:
            with open(settings_path, "w") as f:
                json.dump(settings, f, indent=2)
                f.write("\n")
            print(f"[Stream] Saved settings to {settings_path}")
        except Exception as e:
            print(f"[Stream] Error saving settings: {e}")


def _split_permission_suggestions(
    suggestions: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split permission suggestions into session-only and persist-to-file lists."""
    session_suggestions: list[dict[str, Any]] = []
    persist_suggestions: list[dict[str, Any]] = []
    for suggestion in suggestions or []:
        if not isinstance(suggestion, dict):
            continue
        destination = suggestion.get("destination", "session")
        if destination == "session":
            session_suggestions.append(suggestion)
        else:
            persist_suggestions.append(suggestion)
    return session_suggestions, persist_suggestions


def _map_permission_mode(mode: Optional[str]) -> Optional[str]:
    """Map CLI permission modes to UI modes."""
    if not mode:
        return None
    mapping = {
        "default": "ask",
        "acceptEdits": "act",
        "plan": "plan",
        "bypassPermissions": "act",
        "dontAsk": "act",
        "delegate": "ask",
    }
    return mapping.get(mode, None)


class StreamSession:
    """Manages a Claude subprocess with pipe-based I/O for JSON streaming.

    Based on reverse engineering of Claude Code VSCode extension:
    - Process stays alive with stdin kept open for multiple messages
    - Uses stream-json format for bidirectional communication
    - Mode changes require restart with --resume to preserve history
    """

    def __init__(
        self,
        cmd: str,
        args: list[str],
        cwd: str,
        extra_env: Optional[dict[str, str]] = None,
    ):
        self.cmd = cmd
        self.args = args
        self.cwd = cwd
        self.extra_env = extra_env or {}
        self.proc: Optional[asyncio.subprocess.Process] = None
        self._read_task: Optional[asyncio.Task] = None
        self._stderr_task: Optional[asyncio.Task] = None
        self.clients: set[WebSocket] = set()
        self.history: deque[dict[str, Any]] = deque(maxlen=MAX_HISTORY_LINES)
        self.idle_task: Optional[asyncio.Task] = None
        self.idle_token = 0
        self.session_id: str = ""
        self._started = False
        self._terminated = False
        self._mode: Optional[str] = None  # Track current permission mode
        self._last_init_message: Optional[dict[str, Any]] = None  # Store init for resumed clients
        self._options: Optional[dict[str, Any]] = None  # Track startup options
        self._capabilities: Optional[dict[str, Any]] = None  # Frontend capabilities

    def is_alive(self) -> bool:
        return self.proc is not None and self.proc.returncode is None

    async def spawn(self) -> None:
        """Spawn the subprocess with pipe-based I/O."""
        if self._started:
            return

        env = os.environ.copy()
        env.update(
            {
                "NO_COLOR": "1",
                "FORCE_COLOR": "0",
            }
        )
        env.update(self.extra_env)

        cmd_path = shutil.which(self.cmd)
        if not cmd_path:
            cmd_path = self.cmd

        print(f"[Stream] Spawning: {cmd_path} {' '.join(self.args)}")

        self.proc = await asyncio.create_subprocess_exec(
            cmd_path,
            *self.args,
            cwd=self.cwd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        self._started = True

    async def write_message(self, message: str) -> None:
        """Write a user message to Claude's stdin.

        With --input-format stream-json, Claude expects JSON lines:
        {"type": "user", "session_id": "", "message": {"role": "user", "content": [{"type": "text", "text": "..."}]}}
        """
        if not self.proc or not self.proc.stdin:
            return

        payload = {
            "type": "user",
            "session_id": "",
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": message}],
            },
        }
        line = json.dumps(payload) + "\n"

        try:
            self.proc.stdin.write(line.encode("utf-8"))
            await self.proc.stdin.drain()
        except Exception as e:
            print(f"[Stream] Write error: {e}")

    async def write_message_content(self, content: list[dict[str, Any]]) -> None:
        """Write a user message with structured content blocks."""
        if not self.proc or not self.proc.stdin:
            return

        payload = {
            "type": "user",
            "session_id": "",
            "message": {
                "role": "user",
                "content": content,
            },
        }
        await self.write_json(payload)

    async def write_image(self, base64_data: str, mime_type: str, text: str = "") -> None:
        """Write a message with an image attachment."""
        content: list[dict[str, Any]] = []
        if text:
            content.append({"type": "text", "text": text})
        content.append(
            {
                "type": "image",
                "data": base64_data,
                "mimeType": mime_type,
            }
        )
        await self.write_message_content(content)

    async def interrupt(self) -> None:
        """Interrupt the current Claude operation (sends SIGINT)."""
        if self.proc and self.proc.returncode is None:
            try:
                import signal
                self.proc.send_signal(signal.SIGINT)
                print("[Stream] Sent interrupt signal to Claude")
            except Exception as e:
                print(f"[Stream] Interrupt error: {e}")

    async def write_json(self, payload: dict[str, Any]) -> None:
        """Write a raw JSON payload to Claude's stdin."""
        if not self.proc or not self.proc.stdin:
            print(
                f"[Stream] Cannot write - proc={self.proc is not None} stdin={self.proc.stdin if self.proc else None}"
            )
            return

        line = json.dumps(payload) + "\n"
        print(f"[Stream] Sending JSON type={payload.get('type')} length={len(line)}")
        print(f"[Stream] Payload: {line[:200]}...")

        try:
            self.proc.stdin.write(line.encode("utf-8"))
            await self.proc.stdin.drain()
        except Exception as e:
            print(f"[Stream] Write error: {e}")

    async def broadcast(self, payload: dict[str, Any]) -> None:
        """Broadcast a message to all connected clients."""
        dead: list[WebSocket] = []
        for client in self.clients:
            try:
                await client.send_json(payload)
            except Exception:
                dead.append(client)
        for client in dead:
            self.clients.discard(client)

    async def send_history(self, websocket: WebSocket) -> None:
        """Send accumulated history to a newly connected client."""
        for payload in self.history:
            try:
                await websocket.send_json(payload)
            except Exception:
                break

    async def add_client(self, websocket: WebSocket) -> None:
        """Add a client and cancel idle cleanup."""
        self.clients.add(websocket)
        if self.idle_task:
            self.idle_task.cancel()
            self.idle_task = None

    async def remove_client(self, websocket: WebSocket) -> None:
        """Remove a client and schedule cleanup if no clients remain."""
        self.clients.discard(websocket)
        if not self.clients:
            await self.schedule_idle_cleanup()

    async def schedule_idle_cleanup(self) -> None:
        """Schedule session termination after idle timeout."""
        if IDLE_TTL_SECONDS <= 0:
            await self.terminate()
            return

        self.idle_token += 1
        token = self.idle_token

        async def _cleanup():
            try:
                await asyncio.sleep(IDLE_TTL_SECONDS)
            except asyncio.CancelledError:
                return
            if self.clients:
                return
            if token != self.idle_token:
                return
            await self.terminate()

        self.idle_task = asyncio.create_task(_cleanup())

    async def start_read_loop(self) -> None:
        """Start reading stdout and stderr from the subprocess."""
        if not self.proc:
            return

        async def read_stdout():
            """Read JSON lines from stdout and broadcast."""
            if not self.proc or not self.proc.stdout:
                return

            try:
                async for line in self.proc.stdout:
                    if self._terminated:
                        break
                    text = line.decode("utf-8", errors="replace").strip()
                    if not text:
                        continue

                    try:
                        payload = json.loads(text)
                        msg_type = payload.get("type", "unknown")
                        subtype = payload.get("subtype", "")
                        print(f"[Stream] CLI>>> type={msg_type} subtype={subtype}")

                        if msg_type == "system" and subtype == "init":
                            slash_cmds = payload.get("slash_commands", [])
                            print(f"[Stream] INIT>>> slash_commands count={len(slash_cmds)}: {slash_cmds[:5]}...")
                            self._last_init_message = payload

                        if msg_type in ("control_request", "control_cancel_request"):
                            print(f"[Stream] CONTROL: {json.dumps(payload, indent=2)}")
                            await self.broadcast(payload)
                            continue

                        if msg_type in ("permission", "permission_request", "input_request", "user_input_request"):
                            print(f"[Stream] PERMISSION: {json.dumps(payload, indent=2)}")
                        elif subtype == "error_during_execution" or "error" in subtype.lower():
                            errors = payload.get("errors", [])
                            print(f"[Stream] ERROR: {errors}")
                            error_str = " ".join(str(e) for e in errors)
                            if "No conversation found with session ID" in error_str:
                                await self.broadcast({
                                    "type": "system",
                                    "subtype": "session_not_found",
                                    "message": "Session not found. Starting a new conversation.",
                                })
                        elif msg_type == "user":
                            msg_content = payload.get("message", {}).get("content", "")
                            if isinstance(msg_content, str) and "local-command" in msg_content:
                                print(f"[Stream] CMD OUTPUT: {msg_content[:200]}...")
                            else:
                                print(f"[Stream] USER MSG from CLI: {type(msg_content).__name__}")
                        elif msg_type == "assistant":
                            content = payload.get("message", {}).get("content", [])
                            for item in content:
                                if item.get("type") == "tool_use":
                                    print(f"[Stream] TOOL: {item.get('name')} input_keys={list(item.get('input', {}).keys())}")
                        else:
                            keys = list(payload.keys())
                            print(f"[Stream] OUT: type={msg_type} subtype={subtype} keys={keys}")

                        await self.broadcast(payload)
                    except json.JSONDecodeError:
                        await self.broadcast({"type": "raw", "data": text})
            except asyncio.CancelledError:
                pass
            except Exception as e:
                print(f"[Stream] stdout read error: {e}")

            if not self._terminated:
                exit_code = self.proc.returncode if self.proc else None
                await self.broadcast({
                    "type": "result",
                    "subtype": "exit",
                    "exit_code": exit_code,
                })
                await self.terminate()

        async def read_stderr():
            """Read stderr and log/broadcast errors."""
            if not self.proc or not self.proc.stderr:
                return

            try:
                async for line in self.proc.stderr:
                    if self._terminated:
                        break
                    text = line.decode("utf-8", errors="replace").strip()
                    if text:
                        print(f"[Stream] stderr: {text}")
                        await self.broadcast({
                            "type": "system",
                            "subtype": "stderr",
                            "message": text,
                        })
            except asyncio.CancelledError:
                pass
            except Exception as e:
                print(f"[Stream] stderr read error: {e}")

        self._read_task = asyncio.create_task(read_stdout())
        self._stderr_task = asyncio.create_task(read_stderr())

    async def terminate(self, force: bool = False) -> None:
        """Terminate the session and clean up."""
        if self._terminated:
            return
        self._terminated = True

        if self.idle_task:
            self.idle_task.cancel()
            self.idle_task = None

        if self._read_task:
            self._read_task.cancel()
            self._read_task = None

        if self._stderr_task:
            self._stderr_task.cancel()
            self._stderr_task = None

        if self.proc:
            if self.proc.stdin:
                try:
                    self.proc.stdin.close()
                except Exception:
                    pass
            if self.proc.stdout:
                try:
                    self.proc.stdout.feed_eof()
                except Exception:
                    pass
            if self.proc.stderr:
                try:
                    self.proc.stderr.feed_eof()
                except Exception:
                    pass

            if self.proc.returncode is None:
                try:
                    if force:
                        self.proc.kill()
                    else:
                        self.proc.terminate()
                        try:
                            await asyncio.wait_for(self.proc.wait(), timeout=1.0)
                        except asyncio.TimeoutError:
                            self.proc.kill()
                except Exception:
                    pass
            self.proc = None

        for client in list(self.clients):
            try:
                await client.close()
            except Exception:
                pass
        self.clients.clear()

        async with _SESSION_REGISTRY_LOCK:
            existing = _SESSION_REGISTRY.get(self.session_id)
            if existing is self:
                _SESSION_REGISTRY.pop(self.session_id, None)


def build_stream_args(
    base_args: list[str],
    session_id: Optional[str],
    resume: bool,
    cwd: Optional[str] = None,
    mode: Optional[str] = None,
    model: Optional[str] = None,
    allowed_tools: Optional[list[str]] = None,
    disallowed_tools: Optional[list[str]] = None,
    max_thinking_tokens: Optional[int] = None,
    max_turns: Optional[int] = None,
    max_budget_usd: Optional[float] = None,
    file_specs: Optional[list[str]] = None,
    include_partial: bool = True,
) -> list[str]:
    """Build Claude CLI arguments for stream-json mode."""
    args = list(base_args)

    if "--output-format" not in args:
        args.extend(["--output-format", "stream-json"])
    if "--input-format" not in args:
        args.extend(["--input-format", "stream-json"])
    if "--verbose" not in args:
        args.append("--verbose")

    if mode and "--permission-mode" not in " ".join(args):
        mode_map = {
            "ask": "default",
            "act": "acceptEdits",
            "plan": "plan",
        }
        permission_mode = mode_map.get(mode)
        if permission_mode:
            args.extend(["--permission-mode", permission_mode])

    if model:
        if "--model" in args:
            idx = args.index("--model")
            if idx + 1 < len(args):
                args[idx + 1] = model
        else:
            args.extend(["--model", model])

    if "--permission-prompt-tool" not in args:
        args.extend(["--permission-prompt-tool", "stdio"])

    if allowed_tools:
        if "--allowedTools" in args:
            idx = args.index("--allowedTools")
            if idx + 1 < len(args):
                args[idx + 1] = ",".join(allowed_tools)
        else:
            args.extend(["--allowedTools", ",".join(allowed_tools)])
    if disallowed_tools:
        if "--disallowedTools" in args:
            idx = args.index("--disallowedTools")
            if idx + 1 < len(args):
                args[idx + 1] = ",".join(disallowed_tools)
        else:
            args.extend(["--disallowedTools", ",".join(disallowed_tools)])

    if max_thinking_tokens:
        if "--max-thinking-tokens" in args:
            idx = args.index("--max-thinking-tokens")
            if idx + 1 < len(args):
                args[idx + 1] = str(max_thinking_tokens)
        else:
            args.extend(["--max-thinking-tokens", str(max_thinking_tokens)])

    if max_turns:
        if "--max-turns" in args:
            idx = args.index("--max-turns")
            if idx + 1 < len(args):
                args[idx + 1] = str(max_turns)
        else:
            args.extend(["--max-turns", str(max_turns)])

    if max_budget_usd:
        if "--max-budget-usd" in args:
            idx = args.index("--max-budget-usd")
            if idx + 1 < len(args):
                args[idx + 1] = str(max_budget_usd)
        else:
            args.extend(["--max-budget-usd", str(max_budget_usd)])

    if file_specs:
        existing_files = set()
        for idx, arg in enumerate(args):
            if arg == "--file" and idx + 1 < len(args):
                existing_files.add(args[idx + 1])
        for spec in file_specs:
            if spec and spec not in existing_files:
                args.extend(["--file", spec])

    if "--setting-sources" not in args:
        args.extend(["--setting-sources", "user,project,local"])

    session_flag = os.environ.get("KURT_CLAUDE_SESSION_FLAG", "--session-id")
    resume_flag = os.environ.get("KURT_CLAUDE_RESUME_FLAG", "--resume")

    if session_id:
        if resume:
            if resume_flag and resume_flag not in args:
                args.extend([resume_flag, session_id])
        else:
            if session_flag and session_flag not in args:
                args.extend([session_flag, session_id])

    return args


def get_session_registry() -> dict[str, StreamSession]:
    """Get the global session registry (for list_sessions endpoint)."""
    return _SESSION_REGISTRY
