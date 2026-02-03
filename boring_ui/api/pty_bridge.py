"""PTY bridge for terminal WebSocket connections."""
import asyncio
import json
import os
import uuid
from collections import deque
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from starlette.websockets import WebSocketState

from .config import APIConfig

# Configuration from environment
PTY_HISTORY_BYTES = int(os.environ.get('PTY_HISTORY_BYTES', 200000))
PTY_IDLE_TTL = int(os.environ.get('PTY_IDLE_TTL', 30))
PTY_MAX_SESSIONS = int(os.environ.get('PTY_MAX_SESSIONS', 20))

# Global session registry
_SESSION_REGISTRY: dict[str, 'SharedSession'] = {}
_REGISTRY_LOCK = asyncio.Lock()


@dataclass
class PTYSession:
    """Wrapper around ptyprocess for pseudo-terminal management."""

    process: Any = None
    _read_task: asyncio.Task | None = None
    _output_callback: Any = None

    async def spawn(self, command: list[str], cwd: Path, env: dict[str, str] | None = None):
        """Start PTY process.

        Args:
            command: Command and arguments to run
            cwd: Working directory
            env: Environment variables (merged with os.environ)
        """
        try:
            import ptyprocess
        except ImportError as e:
            raise RuntimeError(
                'ptyprocess is required for PTY support: pip install ptyprocess'
            ) from e

        # Merge environment
        process_env = os.environ.copy()
        if env:
            process_env.update(env)
        process_env['TERM'] = 'xterm-256color'

        # Spawn process
        self.process = ptyprocess.PtyProcessUnicode.spawn(
            command,
            cwd=str(cwd),
            env=process_env,
            dimensions=(24, 80),
        )

    def write(self, data: str):
        """Send input to PTY."""
        if self.process and self.process.isalive():
            self.process.write(data)

    def resize(self, rows: int, cols: int):
        """Resize terminal."""
        if self.process and self.process.isalive():
            self.process.setwinsize(rows, cols)

    async def read_loop(self, callback):
        """Async output reading loop.

        Args:
            callback: async function(data: str) called for each output chunk
        """
        self._output_callback = callback
        loop = asyncio.get_event_loop()

        while self.process and self.process.isalive():
            try:
                # Read in thread pool to avoid blocking
                data = await loop.run_in_executor(
                    None, lambda: self.process.read(4096)
                )
                if data:
                    await callback(data)
            except EOFError:
                break
            except Exception:
                break

    def kill(self):
        """Terminate process."""
        if self.process:
            try:
                if self.process.isalive():
                    self.process.terminate(force=True)
            except Exception:
                pass
            self.process = None

    @property
    def exit_code(self) -> int | None:
        """Get exit code if process has terminated."""
        if self.process and not self.process.isalive():
            return self.process.exitstatus
        return None


@dataclass
class SharedSession:
    """Multi-client PTY session with history buffer."""

    session_id: str
    command: list[str]
    cwd: Path
    pty: PTYSession = field(default_factory=PTYSession)
    clients: set[WebSocket] = field(default_factory=set)
    history: deque = field(default_factory=lambda: deque(maxlen=PTY_HISTORY_BYTES))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    _started: bool = False
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _read_task: asyncio.Task | None = None

    async def start(self):
        """Start the PTY process."""
        if self._started:
            return

        await self.pty.spawn(self.command, self.cwd)
        self._started = True

        # Start reading output
        self._read_task = asyncio.create_task(self._read_output())

    async def _read_output(self):
        """Read output and broadcast to clients."""
        await self.pty.read_loop(self._on_output)

        # Process exited - notify clients
        exit_code = self.pty.exit_code
        await self._broadcast({
            'type': 'exit',
            'code': exit_code,
            'session_id': self.session_id,
        })

    async def _on_output(self, data: str):
        """Handle PTY output."""
        self.last_activity = datetime.now(timezone.utc)

        # Add to history (store as bytes for size tracking)
        encoded = data.encode('utf-8', errors='replace')
        for byte in encoded:
            self.history.append(byte)

        # Broadcast to clients
        await self._broadcast({
            'type': 'output',
            'data': data,
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

        # Remove disconnected clients
        for client in disconnected:
            self.clients.discard(client)

    async def add_client(self, websocket: WebSocket):
        """Add client and send history."""
        async with self._lock:
            # Start PTY if not running
            if not self._started:
                await self.start()

            self.clients.add(websocket)

            # Send session info
            await websocket.send_json({
                'type': 'session',
                'session_id': self.session_id,
            })

            # Send history
            if self.history:
                history_bytes = bytes(self.history)
                history_text = history_bytes.decode('utf-8', errors='replace')
                await websocket.send_json({
                    'type': 'history',
                    'data': history_text,
                })

    async def remove_client(self, websocket: WebSocket):
        """Remove client from session."""
        self.clients.discard(websocket)

    def write(self, data: str):
        """Send input to PTY."""
        self.last_activity = datetime.now(timezone.utc)
        self.pty.write(data)

    def resize(self, rows: int, cols: int):
        """Resize terminal."""
        self.pty.resize(rows, cols)

    def kill(self):
        """Terminate session."""
        if self._read_task:
            self._read_task.cancel()
        self.pty.kill()

    @property
    def is_alive(self) -> bool:
        """Check if PTY is still running."""
        return self.pty.process is not None and self.pty.process.isalive()

    @property
    def idle_seconds(self) -> float:
        """Seconds since last activity."""
        return (datetime.now(timezone.utc) - self.last_activity).total_seconds()


async def _cleanup_idle_sessions():
    """Background task to clean up idle sessions."""
    while True:
        await asyncio.sleep(10)  # Check every 10 seconds

        async with _REGISTRY_LOCK:
            to_remove = []
            for session_id, session in _SESSION_REGISTRY.items():
                # Remove if idle too long and no clients
                if not session.clients and session.idle_seconds > PTY_IDLE_TTL:
                    to_remove.append(session_id)
                # Remove if process died
                elif not session.is_alive:
                    to_remove.append(session_id)

            for session_id in to_remove:
                session = _SESSION_REGISTRY.pop(session_id, None)
                if session:
                    session.kill()


def create_pty_router(config: APIConfig) -> APIRouter:
    """Create PTY WebSocket router.

    Args:
        config: API configuration with pty_providers

    Returns:
        FastAPI router with /pty WebSocket endpoint
    """
    router = APIRouter(tags=['pty'])

    # Start cleanup task on first request
    _cleanup_task: asyncio.Task | None = None

    @router.websocket('/pty')
    async def pty_websocket(
        websocket: WebSocket,
        session_id: str | None = Query(None),
        provider: str = Query('shell'),
    ):
        """WebSocket endpoint for PTY connections.

        Args:
            session_id: Optional session ID to reconnect to existing session
            provider: Provider name (must be in config.pty_providers)
        """
        nonlocal _cleanup_task

        # Start cleanup task if not running
        if _cleanup_task is None or _cleanup_task.done():
            _cleanup_task = asyncio.create_task(_cleanup_idle_sessions())

        # Validate provider
        if provider not in config.pty_providers:
            await websocket.close(
                code=4003,
                reason=f'Unknown provider: {provider}. Available: {list(config.pty_providers.keys())}'
            )
            return

        command = config.pty_providers[provider]

        # Check session limit
        async with _REGISTRY_LOCK:
            if len(_SESSION_REGISTRY) >= PTY_MAX_SESSIONS:
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
                session = SharedSession(
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

                    if msg_type == 'input':
                        session.write(message.get('data', ''))
                    elif msg_type == 'resize':
                        rows = message.get('rows', 24)
                        cols = message.get('cols', 80)
                        session.resize(rows, cols)
                    elif msg_type == 'ping':
                        await websocket.send_json({'type': 'pong'})

                except json.JSONDecodeError:
                    # Treat raw text as input
                    session.write(data)

        except WebSocketDisconnect:
            pass
        except Exception:
            pass
        finally:
            await session.remove_client(websocket)

    return router
