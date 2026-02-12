"""Test logging and artifact contract for CI and live runs.

Provides standardized test output formatting for:
  - Structured JSON log lines with request_id correlation
  - WebSocket event timelines
  - Metrics snapshots
  - Replay manifests for fixture-based tests
  - CI artifact naming and retention conventions

All test artifacts follow a consistent schema so CI pipelines
can reliably parse, archive, and display results.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Artifact naming conventions.
ARTIFACT_PREFIX = 'sandbox-test'
LOG_SUFFIX = '.jsonl'
METRICS_SUFFIX = '.metrics.json'
TIMELINE_SUFFIX = '.timeline.json'
MANIFEST_SUFFIX = '.manifest.json'


@dataclass
class StructuredLogEntry:
    """A single structured log line for test output."""
    timestamp: float
    level: str
    message: str
    request_id: str = ''
    test_name: str = ''
    extra: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)

    @classmethod
    def from_json(cls, line: str) -> StructuredLogEntry:
        data = json.loads(line)
        return cls(**data)


class StructuredTestLogger:
    """Writes structured JSON log lines to a file.

    Each line is a JSON object with timestamp, level, message,
    and optional request_id and test context.
    """

    def __init__(self, path: Path | None = None) -> None:
        self._entries: list[StructuredLogEntry] = []
        self._path = path

    def log(
        self,
        level: str,
        message: str,
        *,
        request_id: str = '',
        test_name: str = '',
        **extra: Any,
    ) -> None:
        entry = StructuredLogEntry(
            timestamp=time.time(),
            level=level,
            message=message,
            request_id=request_id,
            test_name=test_name,
            extra=extra,
        )
        self._entries.append(entry)

    def info(self, message: str, **kwargs: Any) -> None:
        self.log('INFO', message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        self.log('ERROR', message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        self.log('WARNING', message, **kwargs)

    def save(self, path: Path | None = None) -> Path:
        """Write all entries to a JSONL file."""
        target = path or self._path
        if target is None:
            raise ValueError('No path specified for log output')
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('w') as f:
            for entry in self._entries:
                f.write(entry.to_json() + '\n')
        return target

    @property
    def entries(self) -> list[StructuredLogEntry]:
        return list(self._entries)

    @property
    def count(self) -> int:
        return len(self._entries)

    def clear(self) -> None:
        self._entries.clear()


@dataclass
class TimelineEvent:
    """A single event in a WebSocket or request timeline."""
    timestamp: float
    event_type: str  # 'ws_connect', 'ws_message', 'ws_close', 'http_request', etc.
    direction: str  # 'inbound', 'outbound'
    data: dict[str, Any] = field(default_factory=dict)
    request_id: str = ''


class EventTimeline:
    """Captures ordered events for debugging request/WS flows."""

    def __init__(self) -> None:
        self._events: list[TimelineEvent] = []

    def record(
        self,
        event_type: str,
        direction: str,
        *,
        request_id: str = '',
        **data: Any,
    ) -> None:
        self._events.append(TimelineEvent(
            timestamp=time.time(),
            event_type=event_type,
            direction=direction,
            data=data,
            request_id=request_id,
        ))

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = [asdict(e) for e in self._events]
        path.write_text(json.dumps(data, indent=2))
        return path

    @classmethod
    def load(cls, path: Path) -> EventTimeline:
        timeline = cls()
        data = json.loads(path.read_text())
        timeline._events = [TimelineEvent(**e) for e in data]
        return timeline

    @property
    def events(self) -> list[TimelineEvent]:
        return list(self._events)

    @property
    def count(self) -> int:
        return len(self._events)

    def filter_by_request_id(self, request_id: str) -> list[TimelineEvent]:
        return [e for e in self._events if e.request_id == request_id]

    def filter_by_type(self, event_type: str) -> list[TimelineEvent]:
        return [e for e in self._events if e.event_type == event_type]


@dataclass
class TestArtifactManifest:
    """Manifest describing all artifacts produced by a test run."""
    test_suite: str
    run_id: str
    started_at: float
    finished_at: float = 0.0
    artifacts: list[dict[str, str]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def add_artifact(
        self, name: str, path: str, artifact_type: str,
    ) -> None:
        self.artifacts.append({
            'name': name,
            'path': path,
            'type': artifact_type,
        })

    def finish(self, summary: dict[str, Any] | None = None) -> None:
        self.finished_at = time.time()
        if summary:
            self.summary = summary

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2))
        return path

    @classmethod
    def load(cls, path: Path) -> TestArtifactManifest:
        data = json.loads(path.read_text())
        return cls(**data)

    @property
    def duration_seconds(self) -> float:
        if self.finished_at and self.started_at:
            return self.finished_at - self.started_at
        return 0.0


def artifact_path(
    base_dir: Path,
    suite_name: str,
    run_id: str,
    suffix: str,
) -> Path:
    """Generate a standardized artifact file path.

    Format: base_dir/sandbox-test/<suite_name>/<run_id><suffix>
    """
    return base_dir / ARTIFACT_PREFIX / suite_name / f'{run_id}{suffix}'
