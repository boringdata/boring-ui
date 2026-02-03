"""Stream bridge for Claude chat WebSocket connections."""
import asyncio
import json
import os
import subprocess
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from starlette.websockets import WebSocketState

from .config import APIConfig

# Configuration from environment
STREAM_HISTORY_MESSAGES = int(os.environ.get('STREAM_HISTORY_MESSAGES', 100))
STREAM_IDLE_TTL = int(os.environ.get('STREAM_IDLE_TTL', 300))  # 5 minutes
STREAM_MAX_SESSIONS = int(os.environ.get('STREAM_MAX_SESSIONS', 10))

# Global session registry
_SESSION_REGISTRY: dict[str, 'StreamSession'] = {}
_REGISTRY_LOCK = asyncio.Lock()


def build_stream_args(
    model: str | None = None,
    mode: str = 'ask',
    allowed_tools: list[str] | None = None,
    disallowed_tools: list[str] | None = None,
    max_turns: int | None = None,
    print_cost: bool = False,
) -> list[str]:
    """Build Claude CLI arguments for stream-json mode.

    Args:
        model: Model name (e.g., 'opus', 'sonnet')
        mode: Mode ('ask', 'edit', 'agent')
        allowed_tools: List of allowed tool names
        disallowed_tools: List of disallowed tool names
        max_turns: Maximum conversation turns
        print_cost: Print cost information

    Returns:
        List of CLI arguments
    """
    args = ['claude', '--output-format', 'stream-json', '--input-format', 'stream-json']

    if model:
        args.extend(['-m', model])
    if mode:
        args.extend(['--mode', mode])
    if allowed_tools:
        for tool in allowed_tools:
            args.extend(['--allowed-tool', tool])
    if disallowed_tools:
        for tool in disallowed_tools:
            args.extend(['--disallowed-tool', tool])
    if max_turns:
        args.extend(['--max-turns', str(max_turns)])
    if print_cost:
        args.append('--print-cost')

    return args


@dataclass
class StreamSession:
    """Claude CLI stream session with WebSocket broadcast."""

    session_id: str
    command: list[str]
    cwd: Path
    process: subprocess.Popen | None = None
    clients: set[WebSocket] = field(default_factory=set)
    history: deque = field(default_factory=lambda: deque(maxlen=STREAM_HISTORY_MESSAGES))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    _started: bool = False
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _read_task: asyncio.Task | None = None
    _write_queue: asyncio.Queue = field(default_factory=asyncio.Queue)

    async def start(self):
        """Start the Claude CLI process."""
        if self._started:
            return

        # Start process with pipes
        self.process = subprocess.Popen(
            self.command,
            cwd=str(self.cwd),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line buffered
        )
        self._started = True

        # Start reading output
        self._read_task = asyncio.create_task(self._read_output())

    async def _read_output(self):
        """Read output from Claude CLI and broadcast."""
        loop = asyncio.get_event_loop()

        while self.process and self.process.poll() is None:
            try:
                # Read line in thread pool
                line = await loop.run_in_executor(
                    None, self.process.stdout.readline
                )
                if not line:
                    break

                line = line.strip()
                if not line:
                    continue

                # Parse JSON message
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    message = {'type': 'raw', 'data': line}

                # Add to history
                self.history.append(message)
                self.last_activity = datetime.now(timezone.utc)

                # Broadcast to clients
                await self._broadcast(message)

            except Exception:
                break

        # Process exited
        exit_code = self.process.returncode if self.process else -1
        await self._broadcast({
            'type': 'exit',
            'code': exit_code,
            'session_id': self.session_id,
        })

    async def _broadcast(self, message: dict):
        """Send message to all connected clients."""
        data = json.dumps(message)
        disconnected = []

        for client in self.clients.copy():
            try:
                if client.client_state == WebSocketState.CONNECTED:
                    await client.send_text(data)
            except Exception:
                disconnected.append(client)

        for client in disconnected:
            self.clients.discard(client)

    async def add_client(self, websocket: WebSocket):
        """Add client and send history."""
        async with self._lock:
            # Start Claude if not running
            if not self._started:
                await self.start()

            self.clients.add(websocket)

            # Send session info
            await websocket.send_json({
                'type': 'session',
                'session_id': self.session_id,
            })

            # Send history
            for message in self.history:
                await websocket.send_json(message)

    async def remove_client(self, websocket: WebSocket):
        """Remove client from session."""
        self.clients.discard(websocket)

    async def write_message(self, message: dict):
        """Send message to Claude CLI.

        Args:
            message: Message dict to send (will be JSON-encoded)
        """
        if not self.process or self.process.poll() is not None:
            return

        self.last_activity = datetime.now(timezone.utc)

        # Write to stdin
        try:
            line = json.dumps(message) + '\n'
            self.process.stdin.write(line)
            self.process.stdin.flush()
        except Exception:
            pass

    async def send_user_message(self, text: str):
        """Send a user message to Claude.

        Args:
            text: User message text
        """
        await self.write_message({
            'type': 'user',
            'message': text,
        })

    async def send_permission_response(self, request_id: str, allow: bool):
        """Send permission response to Claude.

        Args:
            request_id: ID of the permission request
            allow: Whether to allow the action
        """
        await self.write_message({
            'type': 'permission_response',
            'request_id': request_id,
            'allow': allow,
        })

    async def send_interrupt(self):
        """Send interrupt signal to Claude."""
        await self.write_message({'type': 'interrupt'})

    def terminate(self):
        """Terminate the session."""
        if self._read_task:
            self._read_task.cancel()
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                if self.process:
                    self.process.kill()
            self.process = None

    @property
    def is_alive(self) -> bool:
        """Check if Claude CLI is still running."""
        return self.process is not None and self.process.poll() is None

    @property
    def idle_seconds(self) -> float:
        """Seconds since last activity."""
        return (datetime.now(timezone.utc) - self.last_activity).total_seconds()


async def _cleanup_idle_sessions():
    """Background task to clean up idle sessions."""
    while True:
        await asyncio.sleep(30)  # Check every 30 seconds

        async with _REGISTRY_LOCK:
            to_remove = []
            for session_id, session in _SESSION_REGISTRY.items():
                # Remove if idle too long and no clients
                if not session.clients and session.idle_seconds > STREAM_IDLE_TTL:
                    to_remove.append(session_id)
                # Remove if process died
                elif not session.is_alive:
                    to_remove.append(session_id)

            for session_id in to_remove:
                session = _SESSION_REGISTRY.pop(session_id, None)
                if session:
                    session.terminate()


def create_stream_router(config: APIConfig) -> APIRouter:
    """Create Claude stream WebSocket router.

    Args:
        config: API configuration

    Returns:
        FastAPI router with /stream WebSocket endpoint
    """
    router = APIRouter(tags=['stream'])

    # Start cleanup task on first request
    _cleanup_task: asyncio.Task | None = None

    @router.websocket('/stream')
    async def stream_websocket(
        websocket: WebSocket,
        session_id: str | None = Query(None),
        model: str | None = Query(None),
        mode: str = Query('ask'),
    ):
        """WebSocket endpoint for Claude chat streams.

        Args:
            session_id: Optional session ID to reconnect to existing session
            model: Claude model to use (opus, sonnet, etc.)
            mode: Conversation mode (ask, edit, agent)
        """
        nonlocal _cleanup_task

        # Start cleanup task if not running
        if _cleanup_task is None or _cleanup_task.done():
            _cleanup_task = asyncio.create_task(_cleanup_idle_sessions())

        # Check session limit
        async with _REGISTRY_LOCK:
            if len(_SESSION_REGISTRY) >= STREAM_MAX_SESSIONS:
                await websocket.close(
                    code=4004,
                    reason='Maximum sessions reached'
                )
                return

            # Get or create session
            if session_id and session_id in _SESSION_REGISTRY:
                session = _SESSION_REGISTRY[session_id]
            else:
                session_id = str(uuid.uuid4())
                command = build_stream_args(model=model, mode=mode)
                session = StreamSession(
                    session_id=session_id,
                    command=command,
                    cwd=config.workspace_root,
                )
                _SESSION_REGISTRY[session_id] = session

        # Accept WebSocket
        await websocket.accept()
        await session.add_client(websocket)

        try:
            # Message loop
            while True:
                try:
                    data = await websocket.receive_text()
                    message = json.loads(data)

                    msg_type = message.get('type')

                    if msg_type == 'user':
                        # User message to Claude
                        await session.send_user_message(message.get('message', ''))
                    elif msg_type == 'permission_response':
                        # Permission response
                        await session.send_permission_response(
                            message.get('request_id', ''),
                            message.get('allow', False),
                        )
                    elif msg_type == 'interrupt':
                        # Interrupt current operation
                        await session.send_interrupt()
                    elif msg_type == 'command':
                        # Slash command
                        await session.write_message(message)
                    elif msg_type == 'ping':
                        await websocket.send_json({'type': 'pong'})
                    else:
                        # Pass through other messages
                        await session.write_message(message)

                except json.JSONDecodeError:
                    # Treat raw text as user message
                    await session.send_user_message(data)

        except WebSocketDisconnect:
            pass
        except Exception:
            pass
        finally:
            await session.remove_client(websocket)

    @router.get('/sessions')
    async def list_sessions():
        """List active Claude sessions.

        Returns:
            dict with sessions list
        """
        sessions = []
        async with _REGISTRY_LOCK:
            for session_id, session in _SESSION_REGISTRY.items():
                sessions.append({
                    'session_id': session_id,
                    'clients': len(session.clients),
                    'is_alive': session.is_alive,
                    'idle_seconds': session.idle_seconds,
                    'history_count': len(session.history),
                })
        return {'sessions': sessions}

    return router
