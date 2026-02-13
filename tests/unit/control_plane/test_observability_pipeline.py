"""End-to-end observability pipeline tests.

Bead: bd-6xvu (P4.1)

Validates that logs, metrics, alerts, and request-ID correlation work
as a cohesive pipeline across the workspace API and control plane.

Test coverage:
- Unit: JSON log format (structlog output structure and required fields)
- Integration: metric emission via /metrics endpoint
- Integration: structured log correlation (request_id in log entries)
- E2E: alert rule expressions match emitted metric names
- Correlation: request-ID searchable across workspace and control plane
"""

from __future__ import annotations

import io
import json
import logging
import re

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from prometheus_client import CollectorRegistry

from boring_ui.observability.logging import (
    configure_logging,
    get_logger,
    request_id_ctx,
)
from boring_ui.observability.metrics import (
    CONTENT_TYPE_LATEST,
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_IN_FLIGHT,
    HTTP_REQUESTS_TOTAL,
)
from boring_ui.observability.middleware import (
    MetricsMiddleware,
    RequestIdMiddleware,
    RequestLoggingMiddleware,
    _VALID_REQUEST_ID,
    _normalize_path,
)
from control_plane.app.operations.slo_alerts import (
    DEFAULT_OPERATIONAL_CATALOG,
    REQUIRED_ALERT_KEYS,
    REQUIRED_DASHBOARD_PANEL_KEYS,
    build_prometheus_rule_groups,
    validate_operational_catalog,
)


# =====================================================================
# Fixtures
# =====================================================================


def _create_workspace_app() -> FastAPI:
    """Build a minimal workspace API app with full observability middleware."""
    from boring_ui.api.config import APIConfig
    from pathlib import Path
    import tempfile

    tmp = tempfile.mkdtemp()
    config = APIConfig(workspace_root=Path(tmp))
    app = FastAPI()

    # Apply middleware in production order.
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(RequestIdMiddleware)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/v1/workspaces/{wid}/files")
    async def files(wid: str):
        return {"workspace": wid, "files": []}

    @app.get("/metrics")
    async def metrics():
        from boring_ui.observability.metrics import metrics_text
        from starlette.responses import Response

        body, ct = metrics_text()
        return Response(content=body, media_type=ct)

    return app


@pytest.fixture
def ws_app():
    return _create_workspace_app()


# =====================================================================
# 1. Unit: JSON log format validation
# =====================================================================


class TestLogFormatValidation:
    """Structured log output has required fields for searchability."""

    def test_json_output_contains_timestamp(self):
        """JSON log entries include ISO timestamp."""
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
        test_logger = logging.getLogger("test.json_format")
        test_logger.handlers = [handler]
        test_logger.setLevel(logging.DEBUG)

        # Use structlog processors to add timestamp.
        bound = structlog.wrap_logger(
            test_logger,
            processors=[
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.stdlib.add_log_level,
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
        )
        bound.info("test_event", key="value")

        output = buf.getvalue().strip()
        entry = json.loads(output)
        assert "timestamp" in entry
        assert "level" in entry
        assert entry["level"] == "info"
        assert entry["key"] == "value"

    def test_request_id_injected_into_log_entry(self):
        """When request_id_ctx is set, it appears in log output."""
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
        test_logger = logging.getLogger("test.request_id_inject")
        test_logger.handlers = [handler]
        test_logger.setLevel(logging.DEBUG)

        from boring_ui.observability.logging import _add_request_id

        bound = structlog.wrap_logger(
            test_logger,
            processors=[
                _add_request_id,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.stdlib.add_log_level,
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
        )

        token = request_id_ctx.set("test-rid-12345678")
        try:
            bound.info("logged_with_rid")
        finally:
            request_id_ctx.reset(token)

        output = buf.getvalue().strip()
        entry = json.loads(output)
        assert entry["request_id"] == "test-rid-12345678"

    def test_no_request_id_when_context_unset(self):
        """Without request_id_ctx, no request_id field in log entry."""
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
        test_logger = logging.getLogger("test.no_rid")
        test_logger.handlers = [handler]
        test_logger.setLevel(logging.DEBUG)

        from boring_ui.observability.logging import _add_request_id

        bound = structlog.wrap_logger(
            test_logger,
            processors=[
                _add_request_id,
                structlog.stdlib.add_log_level,
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
        )
        bound.info("no_context")

        output = buf.getvalue().strip()
        entry = json.loads(output)
        assert "request_id" not in entry


# =====================================================================
# 2. Integration: metric emission via /metrics endpoint
# =====================================================================


class TestMetricEmission:
    """Metrics endpoint emits expected Prometheus metric families."""

    @pytest.mark.asyncio
    async def test_metrics_endpoint_returns_200(self, ws_app):
        async with AsyncClient(
            transport=ASGITransport(app=ws_app), base_url="http://test"
        ) as c:
            r = await c.get("/metrics")
            assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_metrics_contain_http_requests_total(self, ws_app):
        async with AsyncClient(
            transport=ASGITransport(app=ws_app), base_url="http://test"
        ) as c:
            # Make a request first to generate metrics.
            await c.get("/health")
            r = await c.get("/metrics")
            assert "http_server_requests_total" in r.text

    @pytest.mark.asyncio
    async def test_metrics_contain_request_duration(self, ws_app):
        async with AsyncClient(
            transport=ASGITransport(app=ws_app), base_url="http://test"
        ) as c:
            await c.get("/health")
            r = await c.get("/metrics")
            assert "http_server_request_duration_seconds" in r.text

    @pytest.mark.asyncio
    async def test_metrics_contain_in_flight_gauge(self, ws_app):
        async with AsyncClient(
            transport=ASGITransport(app=ws_app), base_url="http://test"
        ) as c:
            r = await c.get("/metrics")
            assert "http_server_requests_in_flight" in r.text

    @pytest.mark.asyncio
    async def test_metrics_contain_control_plane_counters(self, ws_app):
        """Control plane metrics are registered even if not yet incremented."""
        async with AsyncClient(
            transport=ASGITransport(app=ws_app), base_url="http://test"
        ) as c:
            r = await c.get("/metrics")
            body = r.text
            # These are registered at import time but may have no samples yet.
            # The HELP/TYPE lines should still appear.
            assert "control_plane_provision_jobs_total" in body
            assert "control_plane_tenant_boundary_incidents_total" in body
            assert "control_plane_audit_events_total" in body

    @pytest.mark.asyncio
    async def test_metrics_path_normalization(self, ws_app):
        """High-cardinality paths are normalized in metric labels."""
        async with AsyncClient(
            transport=ASGITransport(app=ws_app), base_url="http://test"
        ) as c:
            await c.get("/api/v1/workspaces/abc123/files")
            r = await c.get("/metrics")
            body = r.text
            # The workspace ID should be normalized to {id}.
            assert "/api/v1/workspaces/{id}" in body
            # The raw workspace ID should NOT appear as a metric label.
            assert 'path="/api/v1/workspaces/abc123/files"' not in body


# =====================================================================
# 3. Integration: structured log correlation with request-ID
# =====================================================================


class TestLogCorrelation:
    """Request-ID flows from middleware into structured log entries."""

    @pytest.mark.asyncio
    async def test_request_id_set_during_request(self, ws_app):
        """Middleware sets request_id_ctx during request processing."""
        captured_rid = None

        @ws_app.get("/capture-rid")
        async def capture():
            nonlocal captured_rid
            captured_rid = request_id_ctx.get()
            return {"ok": True}

        async with AsyncClient(
            transport=ASGITransport(app=ws_app), base_url="http://test"
        ) as c:
            r = await c.get(
                "/capture-rid",
                headers={"X-Request-ID": "log-corr-test-001"},
            )
            assert r.status_code == 200
            assert captured_rid == "log-corr-test-001"

    @pytest.mark.asyncio
    async def test_auto_generated_rid_available_in_context(self, ws_app):
        """Auto-generated request ID is available via request_id_ctx."""
        captured_rid = None

        @ws_app.get("/capture-auto-rid")
        async def capture():
            nonlocal captured_rid
            captured_rid = request_id_ctx.get()
            return {"ok": True}

        async with AsyncClient(
            transport=ASGITransport(app=ws_app), base_url="http://test"
        ) as c:
            await c.get("/capture-auto-rid")
            assert captured_rid is not None
            assert len(captured_rid) >= 8

    @pytest.mark.asyncio
    async def test_rid_reset_after_request(self, ws_app):
        """Request-ID context is cleaned up after request completes."""

        @ws_app.get("/rid-reset-test")
        async def handler():
            return {"ok": True}

        async with AsyncClient(
            transport=ASGITransport(app=ws_app), base_url="http://test"
        ) as c:
            await c.get(
                "/rid-reset-test",
                headers={"X-Request-ID": "should-not-persist"},
            )
            # After the request, the context should be reset.
            assert request_id_ctx.get() is None


# =====================================================================
# 4. E2E: alert rule expressions match emitted metric names
# =====================================================================


class TestAlertRuleConsistency:
    """Alert rule PromQL references metrics that actually exist."""

    def test_catalog_validates_successfully(self):
        """The default operational catalog passes all validation checks."""
        validate_operational_catalog(DEFAULT_OPERATIONAL_CATALOG)

    def test_all_required_alerts_present(self):
        """All required alert keys are present in the catalog."""
        alert_keys = {a.key for a in DEFAULT_OPERATIONAL_CATALOG.alerts}
        assert REQUIRED_ALERT_KEYS.issubset(alert_keys)

    def test_alert_exprs_reference_registered_metrics(self):
        """Alert PromQL expressions reference metrics defined in metrics.py."""
        # Metric names registered in our Prometheus registry.
        registered_metrics = {
            "http_server_requests_total",
            "http_server_request_duration_seconds",
            "http_server_requests_in_flight",
            "control_plane_provision_jobs_total",
            "control_plane_tenant_boundary_incidents_total",
            "control_plane_audit_events_total",
        }

        for alert in DEFAULT_OPERATIONAL_CATALOG.alerts:
            # Extract metric names from PromQL expr.
            # Metric names match pattern: word chars before { or [
            referenced = set(re.findall(r"([a-z_]+_total|[a-z_]+_seconds)", alert.expr))
            for metric in referenced:
                assert metric in registered_metrics, (
                    f"Alert {alert.key!r} references metric {metric!r} "
                    f"not found in registered metrics"
                )

    def test_prometheus_rule_groups_produce_valid_yaml_shape(self):
        """Exported rule groups have required structure for Prometheus."""
        groups = build_prometheus_rule_groups()
        assert len(groups) >= 1
        for group in groups:
            assert "name" in group
            assert "rules" in group
            for rule in group["rules"]:
                assert "alert" in rule
                assert "expr" in rule
                assert "for" in rule
                assert "labels" in rule
                assert "annotations" in rule
                assert "severity" in rule["labels"]
                assert "summary" in rule["annotations"]

    def test_sev1_alert_has_page_label(self):
        """SEV-1 alert includes page=immediate label for routing."""
        groups = build_prometheus_rule_groups()
        sev1_rules = [
            r
            for g in groups
            for r in g["rules"]
            if r["labels"].get("severity") == "sev1"
        ]
        assert len(sev1_rules) >= 1
        for rule in sev1_rules:
            assert rule["labels"].get("page") == "immediate"


# =====================================================================
# 5. Correlation: request-ID searchable across workspace API
# =====================================================================


class TestRequestIdSearchability:
    """Request-ID is present and consistent across all observability surfaces."""

    @pytest.mark.asyncio
    async def test_response_header_contains_request_id(self, ws_app):
        async with AsyncClient(
            transport=ASGITransport(app=ws_app), base_url="http://test"
        ) as c:
            r = await c.get("/health")
            assert "X-Request-ID" in r.headers
            assert len(r.headers["X-Request-ID"]) >= 8

    @pytest.mark.asyncio
    async def test_caller_provided_id_echoed(self, ws_app):
        async with AsyncClient(
            transport=ASGITransport(app=ws_app), base_url="http://test"
        ) as c:
            r = await c.get(
                "/health",
                headers={"X-Request-ID": "search-test-abc12345"},
            )
            assert r.headers["X-Request-ID"] == "search-test-abc12345"

    @pytest.mark.asyncio
    async def test_malformed_id_replaced_with_uuid(self, ws_app):
        """Malformed request IDs are rejected and replaced with a UUID."""
        async with AsyncClient(
            transport=ASGITransport(app=ws_app), base_url="http://test"
        ) as c:
            r = await c.get(
                "/health",
                headers={"X-Request-ID": "bad;id!"},
            )
            rid = r.headers["X-Request-ID"]
            # Should be a valid UUID, not the malformed input.
            assert rid != "bad;id!"
            import uuid

            uuid.UUID(rid)

    @pytest.mark.asyncio
    async def test_distinct_ids_per_request(self, ws_app):
        """Each request gets a unique ID when none is provided."""
        async with AsyncClient(
            transport=ASGITransport(app=ws_app), base_url="http://test"
        ) as c:
            ids = set()
            for _ in range(5):
                r = await c.get("/health")
                ids.add(r.headers["X-Request-ID"])
            assert len(ids) == 5


# =====================================================================
# 6. Dashboard panel coverage
# =====================================================================


class TestDashboardCoverage:
    """Grafana dashboard covers all required SLO panels."""

    def test_all_required_panels_in_catalog(self):
        panel_keys = {
            p.key
            for d in DEFAULT_OPERATIONAL_CATALOG.dashboards
            for p in d.panels
        }
        assert REQUIRED_DASHBOARD_PANEL_KEYS.issubset(panel_keys)

    def test_dashboard_json_exists_and_matches_catalog(self):
        """The deployed dashboard JSON references all catalog panel titles."""
        from pathlib import Path

        dashboard_path = (
            Path(__file__).resolve().parents[3]
            / "deploy"
            / "grafana"
            / "dashboards"
            / "control-plane-reliability.json"
        )
        assert dashboard_path.exists(), f"Dashboard not found: {dashboard_path}"

        dashboard = json.loads(dashboard_path.read_text())
        panel_titles = {
            p["title"] for p in dashboard.get("panels", []) if p.get("type") != "row"
        }

        for db in DEFAULT_OPERATIONAL_CATALOG.dashboards:
            for panel in db.panels:
                assert panel.title in panel_titles, (
                    f"Dashboard missing panel: {panel.title!r}"
                )


# =====================================================================
# 7. Path normalization for metric cardinality control
# =====================================================================


class TestPathNormalization:
    """Path normalizer prevents high-cardinality metric labels."""

    def test_pty_session_normalized(self):
        assert _normalize_path("/ws/pty/abc123") == "/ws/pty/{session}"

    def test_stream_session_normalized(self):
        assert _normalize_path("/ws/stream/xyz789") == "/ws/stream/{session}"

    def test_workspace_id_normalized(self):
        assert (
            _normalize_path("/api/v1/workspaces/ws_abc123")
            == "/api/v1/workspaces/{id}"
        )

    def test_static_paths_unchanged(self):
        assert _normalize_path("/health") == "/health"
        assert _normalize_path("/metrics") == "/metrics"
        assert _normalize_path("/api/v1/me") == "/api/v1/me"


# =====================================================================
# 8. Request-ID validation regex
# =====================================================================


class TestRequestIdValidation:
    """Request-ID regex accepts valid IDs and rejects bad ones."""

    @pytest.mark.parametrize(
        "valid_id",
        [
            "abc12345",
            "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "A" * 128,
            "request-id-with-dashes",
        ],
    )
    def test_accepts_valid_ids(self, valid_id):
        assert _VALID_REQUEST_ID.match(valid_id)

    @pytest.mark.parametrize(
        "bad_id",
        [
            "short",
            "",
            "A" * 200,
            "invalid;chars!",
            "has spaces in it",
            "tab\there",
        ],
    )
    def test_rejects_invalid_ids(self, bad_id):
        assert not _VALID_REQUEST_ID.match(bad_id)
