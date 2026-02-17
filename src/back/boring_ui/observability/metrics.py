"""Prometheus metrics for boring-ui.

Bead: bd-223o.4 (P4)

Defines counters, histograms, and gauges referenced by the SLO/alert
catalog in ``control_plane.app.operations.slo_alerts``.

Metric naming follows Prometheus conventions and matches the PromQL
expressions in the alert rules so that dashboards and alerts work
without query translation.

Usage::

    from boring_ui.observability.metrics import (
        HTTP_REQUESTS_TOTAL,
        HTTP_REQUEST_DURATION_SECONDS,
    )

    HTTP_REQUESTS_TOTAL.labels(method="GET", path="/api/tree", status="200").inc()
"""

from __future__ import annotations

from prometheus_client import (
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

# Use the default global registry so prometheus_client's built-in
# process/platform collectors (CPU, memory, GC) are included
# automatically alongside application metrics.

# ---------------------------------------------------------------------------
# HTTP request metrics (workspace API + control plane)
# ---------------------------------------------------------------------------

HTTP_REQUESTS_TOTAL = Counter(
    "http_server_requests_total",
    "Total HTTP requests by method, path pattern, and status code.",
    labelnames=["method", "path", "status"],
    registry=REGISTRY,
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_server_request_duration_seconds",
    "HTTP request latency in seconds.",
    labelnames=["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=REGISTRY,
)

HTTP_REQUESTS_IN_FLIGHT = Gauge(
    "http_server_requests_in_flight",
    "Number of HTTP requests currently being processed.",
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Provisioning metrics (control plane)
# ---------------------------------------------------------------------------

PROVISION_JOBS_TOTAL = Counter(
    "control_plane_provision_jobs_total",
    "Provisioning job state transitions.",
    labelnames=["state", "last_error_code", "release_valid"],
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Tenant safety metrics (control plane)
# ---------------------------------------------------------------------------

TENANT_BOUNDARY_INCIDENTS = Counter(
    "control_plane_tenant_boundary_incidents_total",
    "Cross-workspace access incidents (SEV-1 trigger).",
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Audit event metrics
# ---------------------------------------------------------------------------

AUDIT_EVENTS_EMITTED = Counter(
    "control_plane_audit_events_total",
    "Audit events emitted by action type.",
    labelnames=["action"],
    registry=REGISTRY,
)


def metrics_text() -> tuple[bytes, str]:
    """Generate Prometheus exposition text and content-type header."""
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
