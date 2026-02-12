"""Bounded /api/tree traversal with predictable degradation.

Enforces max nodes, max depth, and time limits for directory tree
traversal to prevent memory blowups and request timeouts on large
repositories. Returns schema-compatible partial results when limits
are hit.

Degradation modes:
  - COMPLETE: Full tree within all bounds
  - DEPTH_LIMITED: Max depth reached, deeper entries omitted
  - NODE_LIMITED: Max nodes reached, remaining entries omitted
  - TIME_LIMITED: Time budget exhausted, remaining entries omitted
  - ERROR: Traversal failed
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

DEFAULT_MAX_NODES = 10_000
DEFAULT_MAX_DEPTH = 20
DEFAULT_TIME_BUDGET = 5.0  # seconds
DEFAULT_MAX_ENTRY_NAME_LENGTH = 255


class TraversalStatus(Enum):
    """Status of a tree traversal."""
    COMPLETE = 'complete'
    DEPTH_LIMITED = 'depth_limited'
    NODE_LIMITED = 'node_limited'
    TIME_LIMITED = 'time_limited'
    ERROR = 'error'


@dataclass(frozen=True)
class TreeEntry:
    """A single entry in the directory tree."""
    name: str
    path: str
    is_dir: bool
    depth: int
    size: int = 0

    def to_dict(self) -> dict:
        d: dict = {
            'name': self.name,
            'path': self.path,
            'is_dir': self.is_dir,
        }
        if not self.is_dir:
            d['size'] = self.size
        return d


@dataclass
class TraversalResult:
    """Result of a bounded tree traversal."""
    entries: list[TreeEntry] = field(default_factory=list)
    status: TraversalStatus = TraversalStatus.COMPLETE
    root_path: str = '.'
    total_visited: int = 0
    max_depth_reached: int = 0
    elapsed_seconds: float = 0.0
    error_message: str | None = None

    @property
    def is_complete(self) -> bool:
        return self.status == TraversalStatus.COMPLETE

    @property
    def is_truncated(self) -> bool:
        return self.status in (
            TraversalStatus.DEPTH_LIMITED,
            TraversalStatus.NODE_LIMITED,
            TraversalStatus.TIME_LIMITED,
        )

    def to_response(self) -> dict:
        """Build schema-compatible response body."""
        body: dict = {
            'entries': [e.to_dict() for e in self.entries],
            'path': self.root_path,
        }
        if not self.is_complete:
            body['truncated'] = True
            body['truncation_reason'] = self.status.value
            body['total_visited'] = self.total_visited
        return body


@dataclass
class TraversalConfig:
    """Configuration for bounded tree traversal."""
    max_nodes: int = DEFAULT_MAX_NODES
    max_depth: int = DEFAULT_MAX_DEPTH
    time_budget: float = DEFAULT_TIME_BUDGET
    max_entry_name_length: int = DEFAULT_MAX_ENTRY_NAME_LENGTH


class TraversalBudget:
    """Tracks resource consumption during tree traversal.

    Provides check methods that return False when any limit is exceeded.
    """

    def __init__(self, config: TraversalConfig | None = None) -> None:
        self._config = config or TraversalConfig()
        self._start_time = time.monotonic()
        self._node_count = 0
        self._max_depth_seen = 0
        self._exhausted_reason: TraversalStatus | None = None

    @property
    def config(self) -> TraversalConfig:
        return self._config

    @property
    def node_count(self) -> int:
        return self._node_count

    @property
    def max_depth_seen(self) -> int:
        return self._max_depth_seen

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self._start_time

    @property
    def is_exhausted(self) -> bool:
        return self._exhausted_reason is not None

    @property
    def exhaustion_reason(self) -> TraversalStatus | None:
        return self._exhausted_reason

    def check_depth(self, depth: int) -> bool:
        """Check if depth is within budget. Returns False if exceeded."""
        if depth > self._max_depth_seen:
            self._max_depth_seen = depth
        if depth > self._config.max_depth:
            self._exhausted_reason = TraversalStatus.DEPTH_LIMITED
            return False
        return True

    def check_node(self) -> bool:
        """Record a node visit. Returns False if node limit exceeded."""
        self._node_count += 1
        if self._node_count > self._config.max_nodes:
            self._exhausted_reason = TraversalStatus.NODE_LIMITED
            return False
        return True

    def check_time(self) -> bool:
        """Check if time budget is still available. Returns False if exceeded."""
        if self.elapsed > self._config.time_budget:
            self._exhausted_reason = TraversalStatus.TIME_LIMITED
            return False
        return True

    def check_all(self, depth: int) -> bool:
        """Check all limits. Returns False if any exceeded."""
        return self.check_time() and self.check_node() and self.check_depth(depth)

    def sanitize_name(self, name: str) -> str:
        """Sanitize an entry name to safe length."""
        if len(name) > self._config.max_entry_name_length:
            return name[:self._config.max_entry_name_length]
        return name

    def build_result(
        self,
        entries: list[TreeEntry],
        root_path: str,
    ) -> TraversalResult:
        """Build the final traversal result."""
        status = self._exhausted_reason or TraversalStatus.COMPLETE
        return TraversalResult(
            entries=entries,
            status=status,
            root_path=root_path,
            total_visited=self._node_count,
            max_depth_reached=self._max_depth_seen,
            elapsed_seconds=self.elapsed,
        )


def validate_tree_path(path: str) -> str | None:
    """Validate a tree traversal path.

    Returns None if valid, or an error message if invalid.
    Prevents path traversal attacks.
    """
    if '..' in path.split('/'):
        return 'Path traversal not allowed'
    if path.startswith('/'):
        return 'Absolute paths not allowed'
    if '\x00' in path:
        return 'Null bytes not allowed in path'
    return None
