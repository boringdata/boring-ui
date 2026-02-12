"""Rate limiting and abuse controls for sandbox mode.

Provides token-bucket and sliding-window rate limiters for:
  - Per-IP request rate limiting
  - Per-route limits for expensive endpoints
  - Concurrent session caps per workspace
  - Session idle and absolute timeouts
  - Exec lifecycle policy (detach window, reattach, terminate)
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RateLimitConfig:
    """Configuration for a single rate limit."""
    max_requests: int
    window_seconds: float
    description: str = ''


@dataclass(frozen=True)
class SessionLimitConfig:
    """Configuration for session concurrency and lifecycle limits."""
    max_concurrent_sessions: int = 5
    idle_timeout_seconds: int = 1800  # 30 min
    absolute_timeout_seconds: int = 86400  # 24 hours
    reattach_window_seconds: int = 300  # 5 min after WS close


class RateLimitExceeded(Exception):
    """Raised when a rate limit is exceeded."""

    def __init__(self, key: str, config: RateLimitConfig, retry_after: float):
        self.key = key
        self.config = config
        self.retry_after = retry_after
        super().__init__(
            f'Rate limit exceeded for {key}: '
            f'{config.max_requests}/{config.window_seconds}s. '
            f'Retry after {retry_after:.1f}s'
        )


class ConcurrencyLimitExceeded(Exception):
    """Raised when max concurrent sessions are reached."""

    def __init__(self, key: str, current: int, limit: int):
        self.key = key
        self.current = current
        self.limit = limit
        super().__init__(
            f'Concurrency limit exceeded for {key}: '
            f'{current}/{limit} sessions'
        )


class SlidingWindowCounter:
    """Thread-safe sliding window rate limiter.

    Tracks request timestamps per key and rejects requests that
    exceed the configured rate within the window.
    """

    def __init__(self, config: RateLimitConfig):
        self.config = config
        self._windows: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def check(self, key: str, now: float | None = None) -> None:
        """Check if a request is allowed. Raises RateLimitExceeded if not."""
        now = now if now is not None else time.time()
        cutoff = now - self.config.window_seconds

        with self._lock:
            timestamps = self._windows[key]
            # Remove expired entries
            timestamps[:] = [t for t in timestamps if t > cutoff]

            if len(timestamps) >= self.config.max_requests:
                oldest = timestamps[0] if timestamps else cutoff
                retry_after = oldest + self.config.window_seconds - now
                raise RateLimitExceeded(key, self.config, max(retry_after, 0.1))

            timestamps.append(now)

    def current_count(self, key: str, now: float | None = None) -> int:
        """Return current request count in window for a key."""
        now = now if now is not None else time.time()
        cutoff = now - self.config.window_seconds
        with self._lock:
            timestamps = self._windows.get(key, [])
            return sum(1 for t in timestamps if t > cutoff)

    def reset(self, key: str) -> None:
        """Clear rate limit state for a key."""
        with self._lock:
            self._windows.pop(key, None)

    def reset_all(self) -> None:
        """Clear all rate limit state."""
        with self._lock:
            self._windows.clear()


class ConcurrencyTracker:
    """Thread-safe concurrent session tracker.

    Tracks active sessions per key (workspace/user) and enforces
    max concurrency limits.
    """

    def __init__(self, config: SessionLimitConfig):
        self.config = config
        self._sessions: dict[str, set[str]] = defaultdict(set)
        self._lock = Lock()

    def acquire(self, key: str, session_id: str) -> None:
        """Register a session. Raises ConcurrencyLimitExceeded if at cap."""
        with self._lock:
            sessions = self._sessions[key]
            if session_id in sessions:
                return  # Idempotent
            if len(sessions) >= self.config.max_concurrent_sessions:
                raise ConcurrencyLimitExceeded(
                    key, len(sessions), self.config.max_concurrent_sessions,
                )
            sessions.add(session_id)

    def release(self, key: str, session_id: str) -> None:
        """Unregister a session."""
        with self._lock:
            sessions = self._sessions.get(key)
            if sessions:
                sessions.discard(session_id)
                if not sessions:
                    del self._sessions[key]

    def active_count(self, key: str) -> int:
        """Return number of active sessions for a key."""
        with self._lock:
            return len(self._sessions.get(key, set()))

    def active_sessions(self, key: str) -> list[str]:
        """Return list of active session IDs for a key."""
        with self._lock:
            return sorted(self._sessions.get(key, set()))


@dataclass
class SessionLifecycle:
    """Tracks session lifecycle timestamps for timeout enforcement."""
    session_id: str
    created_at: float = field(default_factory=time.time)
    last_activity_at: float = field(default_factory=time.time)
    ws_disconnected_at: float | None = None

    def touch(self, now: float | None = None) -> None:
        """Update last activity timestamp."""
        self.last_activity_at = now if now is not None else time.time()

    def mark_disconnected(self, now: float | None = None) -> None:
        """Mark WebSocket as disconnected (starts reattach window)."""
        self.ws_disconnected_at = now if now is not None else time.time()

    def mark_reconnected(self) -> None:
        """Clear disconnected state on reattach."""
        self.ws_disconnected_at = None

    def is_idle_expired(
        self, config: SessionLimitConfig, now: float | None = None,
    ) -> bool:
        """Check if session has exceeded idle timeout."""
        now = now if now is not None else time.time()
        return (now - self.last_activity_at) > config.idle_timeout_seconds

    def is_absolute_expired(
        self, config: SessionLimitConfig, now: float | None = None,
    ) -> bool:
        """Check if session has exceeded absolute timeout."""
        now = now if now is not None else time.time()
        return (now - self.created_at) > config.absolute_timeout_seconds

    def is_reattach_expired(
        self, config: SessionLimitConfig, now: float | None = None,
    ) -> bool:
        """Check if reattach window has expired after WS disconnect."""
        if self.ws_disconnected_at is None:
            return False
        now = now if now is not None else time.time()
        return (now - self.ws_disconnected_at) > config.reattach_window_seconds

    def should_terminate(
        self, config: SessionLimitConfig, now: float | None = None,
    ) -> tuple[bool, str]:
        """Check if session should be terminated and return reason.

        Returns:
            (should_terminate, reason) tuple.
        """
        now = now if now is not None else time.time()
        if self.is_absolute_expired(config, now):
            return True, 'absolute timeout'
        if self.is_idle_expired(config, now):
            return True, 'idle timeout'
        if self.is_reattach_expired(config, now):
            return True, 'reattach window expired'
        return False, ''


# ── Default route-specific rate limits ──

DEFAULT_ROUTE_LIMITS: dict[str, RateLimitConfig] = {
    '/api/tree': RateLimitConfig(
        max_requests=60, window_seconds=60,
        description='Directory listing',
    ),
    '/api/search': RateLimitConfig(
        max_requests=30, window_seconds=60,
        description='File search',
    ),
    '/api/file': RateLimitConfig(
        max_requests=120, window_seconds=60,
        description='File read/write',
    ),
    'ws_connect': RateLimitConfig(
        max_requests=10, window_seconds=60,
        description='WebSocket connection attempts',
    ),
}
