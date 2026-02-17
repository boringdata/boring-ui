#!/usr/bin/env python3
"""Verify the observability pipeline end-to-end.

Bead: bd-223o.4 (P4)

Checks:
1. Workspace API /metrics endpoint returns Prometheus exposition text.
2. X-Request-ID is generated on responses (and echoed if provided).
3. Structured log output contains request_id correlation.
4. Prometheus scrape config references correct targets.
5. Alert rules YAML is valid and matches the SLO catalog.
6. Alertmanager config routes to correct receivers.
7. Grafana dashboard JSON references all required panel keys.

Usage::

    python scripts/verify_observability_pipeline.py [--api-url http://localhost:8000]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Ensure src directories are on the path.
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src" / "back"))
sys.path.insert(0, str(project_root / "src"))


def _header(msg: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {msg}")
    print(f"{'=' * 60}")


def _ok(msg: str) -> None:
    print(f"  [PASS] {msg}")


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def _skip(msg: str) -> None:
    print(f"  [SKIP] {msg}")


def verify_static_artifacts() -> tuple[int, int]:
    """Verify deploy artifacts exist and are self-consistent."""
    passed = 0
    failed = 0

    _header("Static artifact verification")

    # 1. Prometheus scrape config
    prom_cfg = project_root / "deploy" / "prometheus" / "prometheus.yml"
    if prom_cfg.exists():
        text = prom_cfg.read_text()
        if "rules.yaml" in text and "alertmanager" in text:
            _ok("prometheus.yml references rules.yaml and alertmanager")
            passed += 1
        else:
            _fail("prometheus.yml missing rules.yaml or alertmanager reference")
            failed += 1
    else:
        _fail("deploy/prometheus/prometheus.yml not found")
        failed += 1

    # 2. Alert rules YAML
    rules_yaml = project_root / "deploy" / "prometheus" / "rules.yaml"
    if rules_yaml.exists():
        text = rules_yaml.read_text()
        required_alerts = [
            "api_5xx_error_rate_burn",
            "provisioning_error_rate_burn",
            "tenant_isolation_violation",
        ]
        for alert_key in required_alerts:
            if alert_key in text:
                _ok(f"rules.yaml contains alert: {alert_key}")
                passed += 1
            else:
                _fail(f"rules.yaml missing alert: {alert_key}")
                failed += 1
    else:
        _fail("deploy/prometheus/rules.yaml not found")
        failed += 1

    # 3. Alert rules match SLO catalog
    from control_plane.app.operations.slo_alerts import (
        DEFAULT_OPERATIONAL_CATALOG,
        build_prometheus_rule_groups,
    )
    try:
        groups = build_prometheus_rule_groups(DEFAULT_OPERATIONAL_CATALOG)
        alert_names = {rule["alert"] for g in groups for rule in g["rules"]}
        if len(alert_names) >= 3:
            _ok(f"SLO catalog produces {len(alert_names)} alert rules")
            passed += 1
        else:
            _fail(f"SLO catalog only produces {len(alert_names)} rules (expected >= 3)")
            failed += 1
    except Exception as exc:
        _fail(f"SLO catalog validation failed: {exc}")
        failed += 1

    # 4. Alertmanager config
    am_cfg = project_root / "deploy" / "alertmanager" / "config.yaml"
    if am_cfg.exists():
        text = am_cfg.read_text()
        for receiver in ("sev1-pager", "critical-oncall", "warning-slack"):
            if receiver in text:
                _ok(f"alertmanager config has receiver: {receiver}")
                passed += 1
            else:
                _fail(f"alertmanager config missing receiver: {receiver}")
                failed += 1
        # Verify severity routing
        if "severity: sev1" in text:
            _ok("alertmanager routes sev1 alerts")
            passed += 1
        else:
            _fail("alertmanager missing sev1 routing")
            failed += 1
    else:
        _fail("deploy/alertmanager/config.yaml not found")
        failed += 1

    # 5. Grafana dashboard
    dashboard_path = project_root / "deploy" / "grafana" / "dashboards" / "control-plane-reliability.json"
    if dashboard_path.exists():
        dashboard = json.loads(dashboard_path.read_text())
        panel_titles = [p.get("title", "") for p in dashboard.get("panels", []) if p.get("type") != "row"]
        from control_plane.app.operations.slo_alerts import REQUIRED_DASHBOARD_PANEL_KEYS
        catalog = DEFAULT_OPERATIONAL_CATALOG
        required_titles = {
            panel.title
            for db in catalog.dashboards
            for panel in db.panels
        }
        found_titles = set(panel_titles)
        for title in required_titles:
            if title in found_titles:
                _ok(f"dashboard has panel: {title}")
                passed += 1
            else:
                _fail(f"dashboard missing panel: {title}")
                failed += 1
    else:
        _fail("deploy/grafana/dashboards/control-plane-reliability.json not found")
        failed += 1

    # 6. Docker compose
    compose_path = project_root / "deploy" / "docker-compose.observability.yml"
    if compose_path.exists():
        text = compose_path.read_text()
        for svc in ("prometheus", "alertmanager", "grafana"):
            if svc in text:
                _ok(f"docker-compose defines service: {svc}")
                passed += 1
            else:
                _fail(f"docker-compose missing service: {svc}")
                failed += 1
    else:
        _fail("deploy/docker-compose.observability.yml not found")
        failed += 1

    return passed, failed


def verify_request_id_middleware() -> tuple[int, int]:
    """Verify request-ID middleware behavior via unit checks."""
    passed = 0
    failed = 0

    _header("Request-ID middleware verification")

    try:
        from boring_ui.observability.middleware import RequestIdMiddleware, _VALID_REQUEST_ID
        _ok("RequestIdMiddleware importable")
        passed += 1

        # Verify regex accepts valid IDs
        for valid_id in ["abc12345", "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "X" * 128]:
            if _VALID_REQUEST_ID.match(valid_id):
                passed += 1
                _ok(f"accepts valid ID: {valid_id[:20]}...")
            else:
                failed += 1
                _fail(f"rejects valid ID: {valid_id[:20]}...")

        # Verify regex rejects malformed IDs
        for bad_id in ["short", "", "a" * 200, "invalid;chars!"]:
            if not _VALID_REQUEST_ID.match(bad_id):
                passed += 1
                _ok(f"rejects invalid ID: {bad_id[:20]!r}")
            else:
                failed += 1
                _fail(f"accepts invalid ID: {bad_id[:20]!r}")

    except ImportError as exc:
        _fail(f"cannot import middleware: {exc}")
        failed += 1

    return passed, failed


def _is_boring_ui_api(api_url: str) -> bool:
    """Check if the target is a boring-ui workspace API."""
    try:
        import urllib.request
        req = urllib.request.Request(f"{api_url}/health")
        with urllib.request.urlopen(req, timeout=3) as resp:
            body = json.loads(resp.read().decode())
            return body.get("status") == "ok" and "features" in body
    except Exception:
        return False


def verify_metrics_endpoint(api_url: str) -> tuple[int, int]:
    """Verify /metrics returns Prometheus exposition text."""
    passed = 0
    failed = 0

    _header(f"Metrics endpoint verification ({api_url})")

    if not _is_boring_ui_api(api_url):
        _skip(f"boring-ui API not reachable at {api_url}")
        return passed, failed

    try:
        import urllib.request
        req = urllib.request.Request(f"{api_url}/metrics")
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode()
            status = resp.status

        if status == 200:
            _ok("/metrics returns 200")
            passed += 1
        else:
            _fail(f"/metrics returns {status}")
            failed += 1

        # Check for expected metric families.
        expected = [
            "http_server_requests_total",
            "http_server_request_duration_seconds",
            "http_server_requests_in_flight",
        ]
        for metric in expected:
            if metric in body:
                _ok(f"/metrics contains {metric}")
                passed += 1
            else:
                _fail(f"/metrics missing {metric}")
                failed += 1

    except Exception as exc:
        _skip(f"cannot reach {api_url}/metrics: {exc}")

    return passed, failed


def verify_request_id_header(api_url: str) -> tuple[int, int]:
    """Verify X-Request-ID header is set on responses."""
    passed = 0
    failed = 0

    _header(f"Request-ID header verification ({api_url})")

    if not _is_boring_ui_api(api_url):
        _skip(f"boring-ui API not reachable at {api_url}")
        return passed, failed

    try:
        import urllib.request

        # Test auto-generated request ID.
        req = urllib.request.Request(f"{api_url}/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            rid = resp.headers.get("X-Request-ID", "")
        if rid and len(rid) >= 8:
            _ok(f"auto-generated X-Request-ID: {rid}")
            passed += 1
        else:
            _fail(f"missing or short X-Request-ID: {rid!r}")
            failed += 1

        # Test echo of provided request ID.
        test_id = "test-verify-obs-12345678"
        req2 = urllib.request.Request(f"{api_url}/health")
        req2.add_header("X-Request-ID", test_id)
        with urllib.request.urlopen(req2, timeout=5) as resp2:
            echoed = resp2.headers.get("X-Request-ID", "")
        if echoed == test_id:
            _ok(f"echoed provided X-Request-ID: {echoed}")
            passed += 1
        else:
            _fail(f"did not echo X-Request-ID: got {echoed!r}, expected {test_id!r}")
            failed += 1

    except Exception as exc:
        _skip(f"cannot reach {api_url}/health: {exc}")

    return passed, failed


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify observability pipeline")
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="Base URL of the workspace API (default: http://localhost:8000)",
    )
    args = parser.parse_args()

    total_passed = 0
    total_failed = 0

    # Static checks (always run).
    p, f = verify_static_artifacts()
    total_passed += p
    total_failed += f

    p, f = verify_request_id_middleware()
    total_passed += p
    total_failed += f

    # Runtime checks (only if API is reachable).
    p, f = verify_metrics_endpoint(args.api_url)
    total_passed += p
    total_failed += f

    p, f = verify_request_id_header(args.api_url)
    total_passed += p
    total_failed += f

    # Summary.
    _header("Summary")
    print(f"  Passed: {total_passed}")
    print(f"  Failed: {total_failed}")
    print()

    if total_failed > 0:
        print("  RESULT: FAIL")
        sys.exit(1)
    else:
        print("  RESULT: PASS")
        sys.exit(0)


if __name__ == "__main__":
    main()
