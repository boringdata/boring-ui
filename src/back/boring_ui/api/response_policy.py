"""Response streaming, size caps, and idempotent retry policy.

Prevents memory blowups from oversized upstream responses and provides
safe retry semantics for delegated requests.

Components:
  - ResponseSizeCap: Enforces maximum response body size
  - StreamingBuffer: Bounded streaming buffer for large responses
  - IdempotentRetryPolicy: Safe retry logic for read-only requests
  - ResponsePolicy: Unified policy combining all components
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

DEFAULT_MAX_RESPONSE_SIZE = 10 * 1024 * 1024  # 10 MB
DEFAULT_STREAMING_CHUNK_SIZE = 64 * 1024  # 64 KB
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BASE_DELAY = 0.5
DEFAULT_RETRY_MAX_DELAY = 5.0
DEFAULT_RETRY_BACKOFF_FACTOR = 2.0


class SizeExceededAction(Enum):
    """Action to take when response exceeds size cap."""
    TRUNCATE = 'truncate'
    REJECT = 'reject'


class RetryDecision(Enum):
    """Decision from retry policy evaluation."""
    RETRY = 'retry'
    STOP = 'stop'
    SKIP = 'skip'  # Not retryable (e.g. POST)


# ── Idempotency ──


# Methods that are safe to retry (idempotent)
IDEMPOTENT_METHODS = frozenset({'GET', 'HEAD', 'OPTIONS', 'PUT', 'DELETE'})

# Status codes that warrant a retry
RETRYABLE_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})


def is_idempotent(method: str) -> bool:
    """Check if an HTTP method is idempotent (safe to retry)."""
    return method.upper() in IDEMPOTENT_METHODS


def is_retryable_status(status_code: int) -> bool:
    """Check if a status code warrants retry."""
    return status_code in RETRYABLE_STATUS_CODES


# ── Size cap ──


@dataclass(frozen=True)
class SizeCapResult:
    """Result of applying a size cap to response data."""
    data: bytes
    original_size: int
    was_truncated: bool
    was_rejected: bool

    @property
    def is_ok(self) -> bool:
        return not self.was_truncated and not self.was_rejected


class ResponseSizeCap:
    """Enforces maximum response body size."""

    def __init__(
        self,
        max_size: int = DEFAULT_MAX_RESPONSE_SIZE,
        action: SizeExceededAction = SizeExceededAction.TRUNCATE,
    ) -> None:
        self._max_size = max_size
        self._action = action

    @property
    def max_size(self) -> int:
        return self._max_size

    def apply(self, data: bytes) -> SizeCapResult:
        """Apply size cap to response data."""
        if len(data) <= self._max_size:
            return SizeCapResult(
                data=data,
                original_size=len(data),
                was_truncated=False,
                was_rejected=False,
            )

        if self._action == SizeExceededAction.REJECT:
            return SizeCapResult(
                data=b'',
                original_size=len(data),
                was_truncated=False,
                was_rejected=True,
            )

        # Truncate
        return SizeCapResult(
            data=data[:self._max_size],
            original_size=len(data),
            was_truncated=True,
            was_rejected=False,
        )


# ── Streaming buffer ──


@dataclass
class StreamingChunk:
    """A chunk from a streaming response."""
    data: bytes
    index: int
    is_last: bool = False


class StreamingBuffer:
    """Bounded streaming buffer for processing large responses in chunks.

    Accumulates data up to a size cap, yielding chunks as they fill.
    """

    def __init__(
        self,
        chunk_size: int = DEFAULT_STREAMING_CHUNK_SIZE,
        max_total: int = DEFAULT_MAX_RESPONSE_SIZE,
    ) -> None:
        self._chunk_size = chunk_size
        self._max_total = max_total
        self._buffer = bytearray()
        self._total_received = 0
        self._chunk_index = 0
        self._finished = False

    @property
    def chunk_size(self) -> int:
        return self._chunk_size

    @property
    def total_received(self) -> int:
        return self._total_received

    @property
    def is_exceeded(self) -> bool:
        return self._total_received > self._max_total

    @property
    def is_finished(self) -> bool:
        return self._finished

    def feed(self, data: bytes) -> list[StreamingChunk]:
        """Feed data into the buffer and return any complete chunks."""
        if self._finished:
            return []

        # Check total size limit
        remaining_capacity = self._max_total - self._total_received
        if remaining_capacity <= 0:
            self._finished = True
            return []

        # Trim to capacity
        if len(data) > remaining_capacity:
            data = data[:remaining_capacity]

        self._total_received += len(data)
        self._buffer.extend(data)

        chunks = []
        while len(self._buffer) >= self._chunk_size:
            chunk_data = bytes(self._buffer[:self._chunk_size])
            self._buffer = self._buffer[self._chunk_size:]
            chunks.append(StreamingChunk(
                data=chunk_data,
                index=self._chunk_index,
            ))
            self._chunk_index += 1

        return chunks

    def flush(self) -> StreamingChunk | None:
        """Flush remaining data as a final chunk."""
        if self._finished or not self._buffer:
            self._finished = True
            return None

        chunk = StreamingChunk(
            data=bytes(self._buffer),
            index=self._chunk_index,
            is_last=True,
        )
        self._buffer.clear()
        self._chunk_index += 1
        self._finished = True
        return chunk


# ── Retry policy ──


@dataclass
class RetryAttempt:
    """Details of a retry attempt."""
    attempt: int
    delay: float
    reason: str


class IdempotentRetryPolicy:
    """Safe retry logic for delegated requests.

    Only retries idempotent methods on retryable status codes.
    Uses exponential backoff with jitter-free delays.
    """

    def __init__(
        self,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_delay: float = DEFAULT_RETRY_BASE_DELAY,
        max_delay: float = DEFAULT_RETRY_MAX_DELAY,
        backoff_factor: float = DEFAULT_RETRY_BACKOFF_FACTOR,
    ) -> None:
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._backoff_factor = backoff_factor

    @property
    def max_retries(self) -> int:
        return self._max_retries

    def evaluate(
        self, method: str, status_code: int, attempt: int,
    ) -> tuple[RetryDecision, RetryAttempt | None]:
        """Evaluate whether to retry a request.

        Args:
            method: HTTP method
            status_code: Response status code
            attempt: Current attempt number (0-based)

        Returns:
            (decision, attempt_details) where attempt_details is None if STOP/SKIP
        """
        if not is_idempotent(method):
            return (RetryDecision.SKIP, None)

        if not is_retryable_status(status_code):
            return (RetryDecision.STOP, None)

        if attempt >= self._max_retries:
            return (RetryDecision.STOP, None)

        delay = min(
            self._base_delay * (self._backoff_factor ** attempt),
            self._max_delay,
        )

        return (
            RetryDecision.RETRY,
            RetryAttempt(
                attempt=attempt + 1,
                delay=delay,
                reason=f'Retryable status {status_code}',
            ),
        )

    def compute_delays(self, count: int) -> list[float]:
        """Compute delay schedule for up to count retries."""
        delays = []
        for i in range(min(count, self._max_retries)):
            delay = min(
                self._base_delay * (self._backoff_factor ** i),
                self._max_delay,
            )
            delays.append(delay)
        return delays


# ── Unified policy ──


@dataclass
class ResponsePolicyConfig:
    """Configuration for the unified response policy."""
    max_response_size: int = DEFAULT_MAX_RESPONSE_SIZE
    size_exceeded_action: SizeExceededAction = SizeExceededAction.TRUNCATE
    streaming_chunk_size: int = DEFAULT_STREAMING_CHUNK_SIZE
    max_retries: int = DEFAULT_MAX_RETRIES
    retry_base_delay: float = DEFAULT_RETRY_BASE_DELAY
    retry_max_delay: float = DEFAULT_RETRY_MAX_DELAY
    retry_backoff_factor: float = DEFAULT_RETRY_BACKOFF_FACTOR


class ResponsePolicy:
    """Unified response handling policy.

    Combines size caps, streaming, and retry into a coherent policy
    for delegated request handling.
    """

    def __init__(self, config: ResponsePolicyConfig | None = None) -> None:
        self._config = config or ResponsePolicyConfig()
        self._size_cap = ResponseSizeCap(
            max_size=self._config.max_response_size,
            action=self._config.size_exceeded_action,
        )
        self._retry = IdempotentRetryPolicy(
            max_retries=self._config.max_retries,
            base_delay=self._config.retry_base_delay,
            max_delay=self._config.retry_max_delay,
            backoff_factor=self._config.retry_backoff_factor,
        )

    @property
    def size_cap(self) -> ResponseSizeCap:
        return self._size_cap

    @property
    def retry_policy(self) -> IdempotentRetryPolicy:
        return self._retry

    def create_streaming_buffer(self) -> StreamingBuffer:
        """Create a new streaming buffer with policy settings."""
        return StreamingBuffer(
            chunk_size=self._config.streaming_chunk_size,
            max_total=self._config.max_response_size,
        )

    def apply_size_cap(self, data: bytes) -> SizeCapResult:
        """Apply response size cap."""
        return self._size_cap.apply(data)

    def should_retry(
        self, method: str, status_code: int, attempt: int,
    ) -> tuple[RetryDecision, RetryAttempt | None]:
        """Evaluate retry decision."""
        return self._retry.evaluate(method, status_code, attempt)
