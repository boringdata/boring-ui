"""WebSocket backpressure, fairness, and lifecycle GC policy.

Provides bounded per-session outbound queues, round-robin fairness
across sessions, detach/reattach window enforcement, and deterministic
stale session reaping.

Components:
  - BoundedOutboundQueue: Per-session message queue with backpressure
  - FairScheduler: Round-robin dispatcher across active sessions
  - DetachWindow: Time-bounded detach/reattach enforcement
  - SessionReaper: Deterministic stale session cleanup
  - WSLifecyclePolicy: Unified policy combining all components
"""
from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

DEFAULT_QUEUE_MAX_SIZE = 256
DEFAULT_QUEUE_HIGH_WATER = 192  # 75% of max
DEFAULT_QUEUE_LOW_WATER = 64   # 25% of max
DEFAULT_DETACH_WINDOW = 30.0   # seconds to allow reattach
DEFAULT_REAP_INTERVAL = 10.0   # seconds between reap cycles
DEFAULT_IDLE_TIMEOUT = 60.0    # seconds before idle session is reaped
DEFAULT_MAX_SESSIONS = 50
DEFAULT_FAIRNESS_QUANTUM = 8   # messages per session per round


class QueueState(Enum):
    """Backpressure state for an outbound queue."""
    NORMAL = 'normal'
    HIGH_WATER = 'high_water'
    FULL = 'full'


class DropReason(Enum):
    """Reason a message was dropped from the queue."""
    QUEUE_FULL = 'queue_full'
    SESSION_CLOSED = 'session_closed'


@dataclass
class QueueStats:
    """Statistics for a bounded outbound queue."""
    enqueued: int = 0
    dequeued: int = 0
    dropped: int = 0
    high_water_events: int = 0

    @property
    def pending(self) -> int:
        return self.enqueued - self.dequeued - self.dropped


@dataclass
class BoundedOutboundQueue:
    """Per-session outbound message queue with backpressure signals.

    Messages are enqueued from exec output and dequeued for WebSocket send.
    When the queue reaches high_water, a backpressure signal is raised.
    When full, messages are dropped (oldest first).
    """
    max_size: int = DEFAULT_QUEUE_MAX_SIZE
    high_water: int = DEFAULT_QUEUE_HIGH_WATER
    low_water: int = DEFAULT_QUEUE_LOW_WATER
    _queue: deque = field(default_factory=deque)
    stats: QueueStats = field(default_factory=QueueStats)

    def __post_init__(self) -> None:
        if self.high_water >= self.max_size:
            self.high_water = int(self.max_size * 0.75)
        if self.low_water >= self.high_water:
            self.low_water = int(self.max_size * 0.25)

    @property
    def state(self) -> QueueState:
        size = len(self._queue)
        if size >= self.max_size:
            return QueueState.FULL
        if size >= self.high_water:
            return QueueState.HIGH_WATER
        return QueueState.NORMAL

    @property
    def size(self) -> int:
        return len(self._queue)

    @property
    def is_backpressured(self) -> bool:
        return self.state != QueueState.NORMAL

    def enqueue(self, message: dict) -> bool:
        """Add a message to the queue.

        Returns True if enqueued, False if dropped.
        """
        if len(self._queue) >= self.max_size:
            # Drop oldest to make room
            self._queue.popleft()
            self.stats.dropped += 1

        self._queue.append(message)
        self.stats.enqueued += 1

        if len(self._queue) == self.high_water:
            self.stats.high_water_events += 1

        return True

    def dequeue(self, count: int = 1) -> list[dict]:
        """Remove up to count messages from the queue.

        Returns a list of messages (may be shorter than count).
        """
        result = []
        for _ in range(min(count, len(self._queue))):
            result.append(self._queue.popleft())
            self.stats.dequeued += 1
        return result

    def peek(self) -> dict | None:
        """Look at the next message without removing it."""
        if self._queue:
            return self._queue[0]
        return None

    def clear(self) -> int:
        """Clear all pending messages. Returns count cleared."""
        count = len(self._queue)
        self._queue.clear()
        return count

    @property
    def is_empty(self) -> bool:
        return len(self._queue) == 0


@dataclass
class FairScheduler:
    """Round-robin scheduler for dispatching across sessions.

    Ensures no single session starves others by limiting messages
    per session per scheduling round (quantum).
    """
    quantum: int = DEFAULT_FAIRNESS_QUANTUM
    _round_robin: deque = field(default_factory=deque)
    _active_set: set = field(default_factory=set)

    def register(self, session_id: str) -> None:
        """Add a session to the scheduling rotation."""
        if session_id not in self._active_set:
            self._active_set.add(session_id)
            self._round_robin.append(session_id)

    def unregister(self, session_id: str) -> None:
        """Remove a session from scheduling."""
        self._active_set.discard(session_id)
        # Lazy removal from deque - will be skipped on next round

    def next_batch(self) -> list[tuple[str, int]]:
        """Get the next round of (session_id, quantum) pairs.

        Returns a list of (session_id, max_messages) tuples for
        one complete scheduling round.
        """
        result = []
        seen = set()
        cleaned = deque()

        for sid in self._round_robin:
            if sid in self._active_set and sid not in seen:
                result.append((sid, self.quantum))
                seen.add(sid)
                cleaned.append(sid)

        self._round_robin = cleaned
        return result

    @property
    def session_count(self) -> int:
        return len(self._active_set)

    @property
    def registered_sessions(self) -> frozenset[str]:
        return frozenset(self._active_set)


class DetachState(Enum):
    """State of a detach window."""
    ATTACHED = 'attached'
    DETACHED = 'detached'
    EXPIRED = 'expired'


@dataclass
class DetachWindow:
    """Enforces time-bounded detach/reattach for a session.

    When a client detaches, a window opens for reattach. If the window
    expires, the session should be cleaned up.
    """
    window_seconds: float = DEFAULT_DETACH_WINDOW
    _state: DetachState = DetachState.ATTACHED
    _detach_time: float | None = None

    @property
    def state(self) -> DetachState:
        if self._state == DetachState.DETACHED and self._detach_time is not None:
            elapsed = time.time() - self._detach_time
            if elapsed > self.window_seconds:
                return DetachState.EXPIRED
        return self._state

    def detach(self) -> None:
        """Start the detach window."""
        self._state = DetachState.DETACHED
        self._detach_time = time.time()

    def reattach(self) -> bool:
        """Attempt to reattach within the window.

        Returns True if reattach succeeded, False if window expired.
        """
        current = self.state
        if current == DetachState.EXPIRED:
            return False
        self._state = DetachState.ATTACHED
        self._detach_time = None
        return True

    @property
    def time_remaining(self) -> float:
        """Seconds remaining in the detach window. 0 if attached or expired."""
        if self._state != DetachState.DETACHED or self._detach_time is None:
            return 0.0
        remaining = self.window_seconds - (time.time() - self._detach_time)
        return max(0.0, remaining)

    @property
    def is_attached(self) -> bool:
        return self.state == DetachState.ATTACHED

    @property
    def is_expired(self) -> bool:
        return self.state == DetachState.EXPIRED


@dataclass
class SessionEntry:
    """Lifecycle entry for a managed WebSocket session."""
    session_id: str
    queue: BoundedOutboundQueue = field(default_factory=BoundedOutboundQueue)
    detach: DetachWindow = field(default_factory=DetachWindow)
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    client_count: int = 0
    closed: bool = False

    def touch(self) -> None:
        self.last_activity = time.time()

    @property
    def is_idle(self) -> bool:
        return self.client_count == 0 and not self.closed

    @property
    def idle_duration(self) -> float:
        if not self.is_idle:
            return 0.0
        return time.time() - self.last_activity


@dataclass
class ReapResult:
    """Result of a reap cycle."""
    reaped_ids: list[str] = field(default_factory=list)
    expired_detach_ids: list[str] = field(default_factory=list)

    @property
    def total_reaped(self) -> int:
        return len(self.reaped_ids) + len(self.expired_detach_ids)


class SessionReaper:
    """Deterministic stale session reaper.

    Identifies sessions that should be cleaned up based on:
      - Idle timeout exceeded
      - Detach window expired
      - Session explicitly closed
    """

    def __init__(self, idle_timeout: float = DEFAULT_IDLE_TIMEOUT) -> None:
        self._idle_timeout = idle_timeout

    def identify_reapable(self, sessions: dict[str, SessionEntry]) -> ReapResult:
        """Identify sessions that should be reaped.

        Returns a ReapResult with session IDs to clean up.
        Does NOT modify the sessions dict.
        """
        result = ReapResult()

        for sid, entry in sessions.items():
            if entry.closed:
                result.reaped_ids.append(sid)
                continue

            if entry.detach.is_expired:
                result.expired_detach_ids.append(sid)
                continue

            if entry.is_idle and entry.idle_duration > self._idle_timeout:
                result.reaped_ids.append(sid)

        return result


@dataclass
class WSLifecycleConfig:
    """Configuration for the unified WS lifecycle policy."""
    queue_max_size: int = DEFAULT_QUEUE_MAX_SIZE
    queue_high_water: int = DEFAULT_QUEUE_HIGH_WATER
    queue_low_water: int = DEFAULT_QUEUE_LOW_WATER
    detach_window: float = DEFAULT_DETACH_WINDOW
    idle_timeout: float = DEFAULT_IDLE_TIMEOUT
    max_sessions: int = DEFAULT_MAX_SESSIONS
    fairness_quantum: int = DEFAULT_FAIRNESS_QUANTUM


class WSLifecyclePolicy:
    """Unified WebSocket lifecycle policy.

    Combines bounded queues, fair scheduling, detach windows,
    and session reaping into a single coherent policy.
    """

    def __init__(self, config: WSLifecycleConfig | None = None) -> None:
        self._config = config or WSLifecycleConfig()
        self._sessions: dict[str, SessionEntry] = {}
        self._scheduler = FairScheduler(quantum=self._config.fairness_quantum)
        self._reaper = SessionReaper(idle_timeout=self._config.idle_timeout)

    def register_session(self, session_id: str) -> SessionEntry:
        """Register a new session with lifecycle management."""
        entry = SessionEntry(
            session_id=session_id,
            queue=BoundedOutboundQueue(
                max_size=self._config.queue_max_size,
                high_water=self._config.queue_high_water,
                low_water=self._config.queue_low_water,
            ),
            detach=DetachWindow(window_seconds=self._config.detach_window),
        )
        self._sessions[session_id] = entry
        self._scheduler.register(session_id)
        return entry

    def unregister_session(self, session_id: str) -> None:
        """Remove a session from lifecycle management."""
        entry = self._sessions.pop(session_id, None)
        if entry:
            entry.closed = True
            entry.queue.clear()
        self._scheduler.unregister(session_id)

    def get_session(self, session_id: str) -> SessionEntry | None:
        return self._sessions.get(session_id)

    def enqueue_message(self, session_id: str, message: dict) -> bool:
        """Enqueue a message for a session. Returns False if session not found."""
        entry = self._sessions.get(session_id)
        if entry is None or entry.closed:
            return False
        entry.queue.enqueue(message)
        entry.touch()
        return True

    def dispatch_round(self) -> dict[str, list[dict]]:
        """Run one fair scheduling round.

        Returns a dict mapping session_id -> list of messages to send.
        """
        batch = self._scheduler.next_batch()
        result: dict[str, list[dict]] = {}

        for session_id, quantum in batch:
            entry = self._sessions.get(session_id)
            if entry is None or entry.closed:
                continue
            messages = entry.queue.dequeue(quantum)
            if messages:
                result[session_id] = messages

        return result

    def client_attach(self, session_id: str) -> bool:
        """Record a client attaching to a session.

        Returns False if session not found or detach window expired.
        """
        entry = self._sessions.get(session_id)
        if entry is None:
            return False

        current_state = entry.detach.state
        if current_state == DetachState.EXPIRED:
            return False
        if current_state == DetachState.DETACHED:
            if not entry.detach.reattach():
                return False

        entry.client_count += 1
        entry.touch()
        return True

    def client_detach(self, session_id: str) -> None:
        """Record a client detaching from a session."""
        entry = self._sessions.get(session_id)
        if entry is None:
            return

        entry.client_count = max(0, entry.client_count - 1)
        entry.touch()

        if entry.client_count == 0:
            entry.detach.detach()

    def run_reap_cycle(self) -> ReapResult:
        """Run a reap cycle and remove stale sessions.

        Returns details of what was reaped.
        """
        result = self._reaper.identify_reapable(self._sessions)

        for sid in result.reaped_ids + result.expired_detach_ids:
            self.unregister_session(sid)

        return result

    def should_reject_new(self) -> bool:
        """Check if new sessions should be rejected (at capacity)."""
        return len(self._sessions) >= self._config.max_sessions

    @property
    def session_count(self) -> int:
        return len(self._sessions)

    @property
    def active_session_ids(self) -> list[str]:
        return [sid for sid, e in self._sessions.items() if not e.closed]

    @property
    def total_queued_messages(self) -> int:
        return sum(e.queue.size for e in self._sessions.values())
