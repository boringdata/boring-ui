"""Observability pipeline end-to-end tests.

Bead: bd-6xvu (P4.1)

Validates:
  - Log format: JSON structure, required fields, request_id correlation.
  - Metric schema: Prometheus format, correct labels, counter increments.
  - Request-ID middleware: generation, validation, spoofing rejection.
  - Alert rule catalog: Prometheus rules match SLO contracts.
  - /metrics endpoint: exposition format and content.
  - Middleware integration: metrics + logging + request-ID on workspace API.
"""

from __future__ import annotations

import io
import json
import logging
import re
import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from boring_ui.observability.logging import (
    configure_logging,
    get_logger,
    request_id_ctx,
)
from boring_ui.observability.metrics import (
    AUDIT_EVENTS_EMITTED,
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_IN_FLIGHT,
    HTTP_REQUESTS_TOTAL,
    PROVISION_JOBS_TOTAL,
    REGISTRY,
    TENANT_BOUNDARY_INCIDENTS,
    metrics_text,
)
from boring_ui.observability.middleware import (
    MetricsMiddleware,
    RequestIdMiddleware,
    RequestLoggingMiddleware,
    _VALID_REQUEST_ID,
    _normalize_path,
)


# =====================================================================
# 1. Log format validation
# =====================================================================


class TestLogFormat:
    """Structured log output has correct JSON shape and required fields."""

    def test_json_log_has_required_fields(self):
        """JSON log entry includes event, level, timestamp, and logger."""
        import structlog

        # Capture log output via a string stream.
        buf = io.StringIO()
        handler = logging.StreamHandler(buf)
        handler.setFormatter(
            structlog.stdlib.ProcessorFormatter(
                processors=[
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                    structlog.processors.JSONRenderer(),
                ],
            )
        )
        test_logger = logging.getLogger("test_json_format")
        test_logger.handlers = [handler]
        test_logger.setLevel(logging.INFO)

        sl = structlog.wrap_logger(
            test_logger,
            processors=[
                structlog.stdlib.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
        )
        sl.info("test_event", key="value")
        handler.flush()

        line = buf.getvalue().strip()
        entry = json.loads(line)
        assert entry["event"] == "test_event"
        assert entry["level"] == "info"
        assert "timestamp" in entry
        assert entry["key"] == "value"

    def test_request_id_injected_into_log(self):
        """When request_id_ctx is set, logs include request_id."""
        import structlog

        buf = io.StringIO()
        handler = logging.StreamHandler(buf)
        handler.setFormatter(
            structlog.stdlib.ProcessorFormatter(
                processors=[
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                    structlog.processors.JSONRenderer(),
                ],
            )
        )

        from boring_ui.observability.logging import _add_request_id

        test_logger = logging.getLogger("test_rid_inject")
        test_logger.handlers = [handler]
        test_logger.setLevel(logging.INFO)

        sl = structlog.wrap_logger(
            test_logger,
            processors=[
                _add_request_id,
                structlog.stdlib.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
        )

        token = request_id_ctx.set("test-rid-abc")
        try:
            sl.info("with_rid")
            handler.flush()
        finally:
            request_id_ctx.reset(token)

        entry = json.loads(buf.getvalue().strip())
        assert entry["request_id"] == "test-rid-abc"

    def test_no_request_id_when_not_set(self):
        """When request_id_ctx is unset, logs omit request_id."""
        import structlog

        buf = io.StringIO()
        handler = logging.StreamHandler(buf)
        handler.setFormatter(
            structlog.stdlib.ProcessorFormatter(
                processors=[
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                    structlog.processors.JSONRenderer(),
                ],
            )
        )

        from boring_ui.observability.logging import _add_request_id

        test_logger = logging.getLogger("test_no_rid")
        test_logger.handlers = [handler]
        test_logger.setLevel(logging.INFO)

        sl = structlog.wrap_logger(
            test_logger,
            processors=[
                _add_request_id,
                structlog.stdlib.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
        )
        sl.info("without_rid")
        handler.flush()

        entry = json.loads(buf.getvalue().strip())
        assert "request_id" not in entry


# =====================================================================
# 2. Metric schema validation
# =====================================================================


class TestMetricSchema:
    """Prometheus metrics have expected names, labels, and types."""

    def test_http_requests_total_labels(self):
        """http_server_requests_total has method, path, status labels."""
        HTTP_REQUESTS_TOTAL.labels(method="GET", path="/test", status="200").inc()
        body, _ = metrics_text()
        text = body.decode()
        assert "http_server_requests_total" in text
        assert 'method="GET"' in text

    def test_http_request_duration_is_histogram(self):
        """http_server_request_duration_seconds is a histogram with buckets."""
        HTTP_REQUEST_DURATION_SECONDS.labels(method="GET", path="/test").observe(0.05)
        body, _ = metrics_text()
        text = body.decode()
        assert "http_server_request_duration_seconds_bucket" in text

    def test_provision_jobs_total_labels(self):
        """control_plane_provision_jobs_total has required labels."""
        PROVISION_JOBS_TOTAL.labels(
            state="ready", last_error_code="", release_valid="true"
        ).inc()
        body, _ = metrics_text()
        text = body.decode()
        assert "control_plane_provision_jobs_total" in text
        assert 'state="ready"' in text
        assert 'release_valid="true"' in text

    def test_tenant_boundary_incidents_counter(self):
        """control_plane_tenant_boundary_incidents_total is a counter."""
        TENANT_BOUNDARY_INCIDENTS.inc()
        body, _ = metrics_text()
        text = body.decode()
        assert "control_plane_tenant_boundary_incidents_total" in text

    def test_audit_events_emitted_labels(self):
        """control_plane_audit_events_total has action label."""
        AUDIT_EVENTS_EMITTED.labels(action="workspace.create").inc()
        body, _ = metrics_text()
        text = body.decode()
        assert "control_plane_audit_events_total" in text
        assert 'action="workspace.create"' in text

    def test_metrics_text_content_type(self):
        """metrics_text returns correct Prometheus content type."""
        _, ct = metrics_text()
        assert "text/plain" in ct

    def test_in_flight_gauge(self):
        """http_server_requests_in_flight is a gauge (can go up and down)."""
        HTTP_REQUESTS_IN_FLIGHT.inc()
        HTTP_REQUESTS_IN_FLIGHT.dec()
        body, _ = metrics_text()
        assert b"http_server_requests_in_flight" in body


# =====================================================================
# 3. Request-ID middleware
# =====================================================================


def _create_observability_app() -> FastAPI:
    """Build a FastAPI app with observability middleware."""
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(RequestIdMiddleware)

    @app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}

    @app.get("/error")
    async def error_endpoint():
        raise ValueError("test error")

    return app


@pytest.fixture
def obs_app():
    return _create_observability_app()


class TestRequestIdMiddleware:
    """Request-ID generation, validation, and spoofing rejection."""

    @pytest.mark.asyncio
    async def test_auto_generates_uuid(self, obs_app):
        """When no X-Request-ID is provided, generates a valid UUID."""
        async with AsyncClient(
            transport=ASGITransport(app=obs_app), base_url="http://test"
        ) as c:
            r = await c.get("/test")
            rid = r.headers["x-request-id"]
            uuid.UUID(rid)  # Valid UUID

    @pytest.mark.asyncio
    async def test_accepts_valid_caller_id(self, obs_app):
        """Valid caller-provided X-Request-ID is preserved."""
        async with AsyncClient(
            transport=ASGITransport(app=obs_app), base_url="http://test"
        ) as c:
            r = await c.get("/test", headers={"X-Request-ID": "valid-abc-123"})
            assert r.headers["x-request-id"] == "valid-abc-123"

    @pytest.mark.asyncio
    async def test_rejects_malformed_id(self, obs_app):
        """Malformed X-Request-ID is replaced with a fresh UUID."""
        async with AsyncClient(
            transport=ASGITransport(app=obs_app), base_url="http://test"
        ) as c:
            r = await c.get(
                "/test", headers={"X-Request-ID": "<script>alert(1)</script>"}
            )
            rid = r.headers["x-request-id"]
            assert rid != "<script>alert(1)</script>"
            uuid.UUID(rid)  # Should be a valid UUID

    @pytest.mark.asyncio
    async def test_rejects_too_short_id(self, obs_app):
        """IDs shorter than 8 chars are rejected."""
        async with AsyncClient(
            transport=ASGITransport(app=obs_app), base_url="http://test"
        ) as c:
            r = await c.get("/test", headers={"X-Request-ID": "short"})
            rid = r.headers["x-request-id"]
            assert rid != "short"
            uuid.UUID(rid)

    @pytest.mark.asyncio
    async def test_rejects_too_long_id(self, obs_app):
        """IDs longer than 128 chars are rejected."""
        long_id = "a" * 200
        async with AsyncClient(
            transport=ASGITransport(app=obs_app), base_url="http://test"
        ) as c:
            r = await c.get("/test", headers={"X-Request-ID": long_id})
            rid = r.headers["x-request-id"]
            assert rid != long_id
            uuid.UUID(rid)

    @pytest.mark.asyncio
    async def test_empty_header_generates_uuid(self, obs_app):
        async with AsyncClient(
            transport=ASGITransport(app=obs_app), base_url="http://test"
        ) as c:
            r = await c.get("/test", headers={"X-Request-ID": ""})
            uuid.UUID(r.headers["x-request-id"])

    @pytest.mark.asyncio
    async def test_sequential_requests_unique_ids(self, obs_app):
        """Each request gets a distinct auto-generated ID."""
        async with AsyncClient(
            transport=ASGITransport(app=obs_app), base_url="http://test"
        ) as c:
            ids = set()
            for _ in range(10):
                r = await c.get("/test")
                ids.add(r.headers["x-request-id"])
            assert len(ids) == 10

    @pytest.mark.asyncio
    async def test_caller_id_no_cross_request_leak(self, obs_app):
        """Caller ID on request 1 does not leak to request 2."""
        async with AsyncClient(
            transport=ASGITransport(app=obs_app), base_url="http://test"
        ) as c:
            r1 = await c.get("/test", headers={"X-Request-ID": "sticky-id-001"})
            assert r1.headers["x-request-id"] == "sticky-id-001"
            r2 = await c.get("/test")
            assert r2.headers["x-request-id"] != "sticky-id-001"


class TestRequestIdValidation:
    """Regex validation for request-ID format."""

    def test_valid_uuid(self):
        assert _VALID_REQUEST_ID.match("550e8400-e29b-41d4-a716-446655440000")

    def test_valid_alphanumeric(self):
        assert _VALID_REQUEST_ID.match("trace-abc-123-def")

    def test_invalid_special_chars(self):
        assert not _VALID_REQUEST_ID.match("<script>alert(1)</script>")

    def test_too_short(self):
        assert not _VALID_REQUEST_ID.match("abc")

    def test_max_length(self):
        assert _VALID_REQUEST_ID.match("a" * 128)
        assert not _VALID_REQUEST_ID.match("a" * 129)


# =====================================================================
# 4. Path normalization
# =====================================================================


class TestPathNormalization:
    """High-cardinality path segments are collapsed for metric labels."""

    def test_pty_session_normalized(self):
        assert _normalize_path("/ws/pty/abc-123") == "/ws/pty/{session}"

    def test_stream_session_normalized(self):
        assert _normalize_path("/ws/stream/def-456") == "/ws/stream/{session}"

    def test_workspace_id_normalized(self):
        assert (
            _normalize_path("/api/v1/workspaces/ws-123")
            == "/api/v1/workspaces/{id}"
        )

    def test_static_paths_unchanged(self):
        assert _normalize_path("/api/capabilities") == "/api/capabilities"
        assert _normalize_path("/health") == "/health"
        assert _normalize_path("/metrics") == "/metrics"


# =====================================================================
# 5. Metrics middleware integration
# =====================================================================


class TestMetricsMiddleware:
    """MetricsMiddleware records counters and histograms correctly."""

    @pytest.mark.asyncio
    async def test_successful_request_increments_counter(self, obs_app):
        """200 response increments http_server_requests_total."""
        async with AsyncClient(
            transport=ASGITransport(app=obs_app), base_url="http://test"
        ) as c:
            await c.get("/test")
            body, _ = metrics_text()
            text = body.decode()
            assert 'http_server_requests_total{method="GET",path="/test",status="200"}' in text

    @pytest.mark.asyncio
    async def test_request_duration_recorded(self, obs_app):
        """Request duration is observed in the histogram."""
        async with AsyncClient(
            transport=ASGITransport(app=obs_app), base_url="http://test"
        ) as c:
            await c.get("/test")
            body, _ = metrics_text()
            text = body.decode()
            assert 'http_server_request_duration_seconds_bucket{' in text


# =====================================================================
# 6. Alert rule catalog validation
# =====================================================================


class TestAlertRuleCatalog:
    """Prometheus rules exported from slo_alerts.py match SLO contracts."""

    def test_catalog_validates(self):
        from control_plane.app.operations.slo_alerts import (
            DEFAULT_OPERATIONAL_CATALOG,
            validate_operational_catalog,
        )
        validate_operational_catalog(DEFAULT_OPERATIONAL_CATALOG)

    def test_prometheus_rules_generated(self):
        from control_plane.app.operations.slo_alerts import (
            build_prometheus_rule_groups,
        )
        groups = build_prometheus_rule_groups()
        assert len(groups) == 1
        assert groups[0]["name"] == "feature3-control-plane-operations"
        assert len(groups[0]["rules"]) == 3

    def test_alert_keys_match_required_set(self):
        from control_plane.app.operations.slo_alerts import (
            REQUIRED_ALERT_KEYS,
            build_prometheus_rule_groups,
        )
        groups = build_prometheus_rule_groups()
        rule_keys = {r["alert"] for r in groups[0]["rules"]}
        assert REQUIRED_ALERT_KEYS == rule_keys

    def test_metric_names_in_alert_exprs_match_defined_metrics(self):
        """Alert PromQL expressions reference metrics that we actually define."""
        from control_plane.app.operations.slo_alerts import (
            build_prometheus_rule_groups,
        )
        groups = build_prometheus_rule_groups()
        defined_metric_names = {
            "http_server_requests_total",
            "control_plane_provision_jobs_total",
            "control_plane_tenant_boundary_incidents_total",
        }
        for rule in groups[0]["rules"]:
            expr = rule["expr"]
            for name in defined_metric_names:
                if name in expr:
                    break
            else:
                # At least one defined metric should appear in each rule.
                pytest.fail(
                    f"Alert {rule['alert']} expr references no defined metrics"
                )

    def test_tenant_isolation_alert_is_immediate_sev1(self):
        from control_plane.app.operations.slo_alerts import (
            build_prometheus_rule_groups,
        )
        groups = build_prometheus_rule_groups()
        tenant_rule = next(
            r for r in groups[0]["rules"]
            if r["alert"] == "tenant_isolation_violation"
        )
        assert tenant_rule["labels"]["severity"] == "sev1"
        assert tenant_rule["labels"]["page"] == "immediate"


# =====================================================================
# 7. /metrics endpoint via app factory
# =====================================================================


class TestMetricsEndpoint:
    """The /metrics endpoint on create_app() returns Prometheus data."""

    @pytest.mark.asyncio
    async def test_metrics_endpoint_returns_200(self):
        from boring_ui.api.app import create_app

        app = create_app()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/metrics")
            assert r.status_code == 200
            assert "text/plain" in r.headers["content-type"]

    @pytest.mark.asyncio
    async def test_metrics_endpoint_has_http_counter(self):
        from boring_ui.api.app import create_app

        app = create_app()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            # Make a request first to generate metrics.
            await c.get("/health")
            r = await c.get("/metrics")
            assert "http_server_requests_total" in r.text

    @pytest.mark.asyncio
    async def test_app_echoes_request_id(self):
        from boring_ui.api.app import create_app

        app = create_app()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/health", headers={"X-Request-ID": "e2e-test-001"})
            assert r.headers["x-request-id"] == "e2e-test-001"

    @pytest.mark.asyncio
    async def test_app_generates_request_id_when_absent(self):
        from boring_ui.api.app import create_app

        app = create_app()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/health")
            rid = r.headers.get("x-request-id", "")
            assert len(rid) == 36  # UUID format


# =====================================================================
# 8. Configure logging idempotency
# =====================================================================


class TestConfigureLogging:
    """configure_logging() is safe to call multiple times."""

    def test_idempotent_call(self):
        """Second call is a no-op (no duplicate handlers)."""
        import boring_ui.observability.logging as obs_log

        obs_log._configured = False
        configure_logging(json_output=False)
        handler_count = len(logging.getLogger().handlers)
        configure_logging(json_output=False)
        assert len(logging.getLogger().handlers) == handler_count
        obs_log._configured = False  # Reset for other tests.

    def test_get_logger_returns_bound_logger(self):
        """get_logger returns a structlog BoundLogger."""
        import structlog

        logger = get_logger("test")
        assert hasattr(logger, "info")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")
