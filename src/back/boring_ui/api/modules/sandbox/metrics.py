"""Minimal metrics module for SpritesProvider observability.

Provides in-memory counters, gauges, and histograms that can be
queried via the ``/sandbox/metrics`` endpoint.  No external
dependencies (Prometheus, StatsD, …); just a thin dict-based store
that is safe for single-process asyncio usage.

Usage inside SpritesProvider / SpritesClient::

    from .metrics import record, timed, get_snapshot

    # Increment a counter
    record("sprite_health_check_failures_total", tags={"sandbox_id": sid})

    # Record a duration
    with timed("sprite_create_duration_seconds", tags={"sandbox_id": sid}):
        await do_work()

    # Set a gauge
    record("sprites_active_total", value=5, kind="gauge")

    # Get all metrics
    snapshot = get_snapshot()
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Generator


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

@dataclass
class _Counter:
    value: float = 0.0

    def inc(self, n: float = 1.0) -> None:
        self.value += n


@dataclass
class _Gauge:
    value: float = 0.0

    def set(self, n: float) -> None:
        self.value = n

    def inc(self, n: float = 1.0) -> None:
        self.value += n

    def dec(self, n: float = 1.0) -> None:
        self.value -= n


@dataclass
class _Histogram:
    """Simple histogram that tracks count, sum, min, max, and last value."""
    count: int = 0
    total: float = 0.0
    min_val: float = float("inf")
    max_val: float = float("-inf")
    last: float = 0.0

    def observe(self, value: float) -> None:
        self.count += 1
        self.total += value
        self.last = value
        if value < self.min_val:
            self.min_val = value
        if value > self.max_val:
            self.max_val = value

    def to_dict(self) -> dict[str, Any]:
        if self.count == 0:
            return {"count": 0}
        return {
            "count": self.count,
            "sum": round(self.total, 4),
            "min": round(self.min_val, 4),
            "max": round(self.max_val, 4),
            "avg": round(self.total / self.count, 4),
            "last": round(self.last, 4),
        }


@dataclass
class _MetricsStore:
    counters: dict[str, _Counter] = field(default_factory=dict)
    gauges: dict[str, _Gauge] = field(default_factory=dict)
    histograms: dict[str, _Histogram] = field(default_factory=dict)


_store = _MetricsStore()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _metric_key(name: str, tags: dict[str, str] | None = None) -> str:
    """Build a flat key from name + sorted tags."""
    if not tags:
        return name
    suffix = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
    return f"{name}{{{suffix}}}"


def record(
    name: str,
    *,
    value: float = 1.0,
    kind: str = "counter",
    tags: dict[str, str] | None = None,
) -> None:
    """Record a metric value.

    Args:
        name: Metric name.
        value: Numeric value (default 1 for counters).
        kind: ``"counter"`` | ``"gauge"`` | ``"histogram"``.
        tags: Optional key-value labels.
    """
    key = _metric_key(name, tags)

    if kind == "counter":
        if key not in _store.counters:
            _store.counters[key] = _Counter()
        _store.counters[key].inc(value)

    elif kind == "gauge":
        if key not in _store.gauges:
            _store.gauges[key] = _Gauge()
        _store.gauges[key].set(value)

    elif kind == "histogram":
        if key not in _store.histograms:
            _store.histograms[key] = _Histogram()
        _store.histograms[key].observe(value)


@contextmanager
def timed(
    name: str,
    *,
    tags: dict[str, str] | None = None,
) -> Generator[dict[str, Any], None, None]:
    """Context manager that records elapsed time as a histogram value.

    Yields a dict where ``duration_ms`` is set on exit (useful for
    including in structured log records).

    Example::

        with timed("sprite_create_duration_seconds", tags={"sandbox_id": sid}) as t:
            await work()
        logger.info("done", extra={"duration_ms": t["duration_ms"]})
    """
    ctx: dict[str, Any] = {}
    start = time.monotonic()
    try:
        yield ctx
    finally:
        elapsed = time.monotonic() - start
        ctx["duration_ms"] = round(elapsed * 1000, 1)
        record(name, value=elapsed, kind="histogram", tags=tags)


def gauge_inc(name: str, n: float = 1.0) -> None:
    """Increment a gauge (e.g. active sprite count)."""
    key = _metric_key(name)
    if key not in _store.gauges:
        _store.gauges[key] = _Gauge()
    _store.gauges[key].inc(n)


def gauge_dec(name: str, n: float = 1.0) -> None:
    """Decrement a gauge."""
    key = _metric_key(name)
    if key not in _store.gauges:
        _store.gauges[key] = _Gauge()
    _store.gauges[key].dec(n)


def get_snapshot() -> dict[str, Any]:
    """Return a JSON-serializable snapshot of all metrics."""
    result: dict[str, Any] = {}

    if _store.counters:
        result["counters"] = {k: v.value for k, v in sorted(_store.counters.items())}
    if _store.gauges:
        result["gauges"] = {k: v.value for k, v in sorted(_store.gauges.items())}
    if _store.histograms:
        result["histograms"] = {
            k: v.to_dict() for k, v in sorted(_store.histograms.items())
        }

    return result


def reset() -> None:
    """Reset all metrics (for testing)."""
    _store.counters.clear()
    _store.gauges.clear()
    _store.histograms.clear()
