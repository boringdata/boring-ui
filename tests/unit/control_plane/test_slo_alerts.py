"""Tests for Feature 3 SLO/alert operational catalog.

Bead: bd-223o.15.1 (J1)
"""

from __future__ import annotations

import pytest

from control_plane.app.operations.slo_alerts import (
    DEFAULT_OPERATIONAL_CATALOG,
    REQUIRED_ALERT_KEYS,
    REQUIRED_DASHBOARD_PANEL_KEYS,
    REQUIRED_ESCALATION_OWNERS,
    REQUIRED_SLO_KEYS,
    build_prometheus_rule_groups,
    operational_catalog_as_dict,
    validate_operational_catalog,
)


class TestCatalogContract:
    """Ensure required Feature 3 section 17.2 contract is encoded."""

    def test_default_catalog_validates(self):
        validate_operational_catalog(DEFAULT_OPERATIONAL_CATALOG)

    def test_required_slos_exist(self):
        keys = {slo.key for slo in DEFAULT_OPERATIONAL_CATALOG.slos}
        assert REQUIRED_SLO_KEYS.issubset(keys)

    def test_api_availability_slo_target(self):
        api_slo = next(
            slo for slo in DEFAULT_OPERATIONAL_CATALOG.slos
            if slo.key == 'api_availability_monthly'
        )
        assert api_slo.target_percent == pytest.approx(99.5)
        assert api_slo.measurement_window == '30d'
        assert 'api_5xx_error_rate_burn' in api_slo.alert_keys

    def test_provisioning_reliability_target(self):
        slo = next(
            item for item in DEFAULT_OPERATIONAL_CATALOG.slos
            if item.key == 'provisioning_reliability_monthly'
        )
        assert slo.target_percent == pytest.approx(99.0)
        assert slo.measurement_window == '30d'
        assert 'provisioning_error_rate_burn' in slo.alert_keys

    def test_required_alerts_exist(self):
        keys = {alert.key for alert in DEFAULT_OPERATIONAL_CATALOG.alerts}
        assert REQUIRED_ALERT_KEYS.issubset(keys)

    def test_api_5xx_alert_threshold_and_window(self):
        alert = next(
            item for item in DEFAULT_OPERATIONAL_CATALOG.alerts
            if item.key == 'api_5xx_error_rate_burn'
        )
        assert alert.threshold == pytest.approx(2.0)
        assert alert.window == '5m'
        assert '/api/v1/workspaces' in alert.expr
        assert '/auth/callback' in alert.expr

    def test_provisioning_alert_grouped_by_error_code(self):
        alert = next(
            item for item in DEFAULT_OPERATIONAL_CATALOG.alerts
            if item.key == 'provisioning_error_rate_burn'
        )
        assert alert.threshold == pytest.approx(5.0)
        assert alert.window == '15m'
        assert 'last_error_code' in alert.group_by

    def test_tenant_isolation_alert_is_immediate_sev1(self):
        alert = next(
            item for item in DEFAULT_OPERATIONAL_CATALOG.alerts
            if item.key == 'tenant_isolation_violation'
        )
        assert alert.severity.lower() == 'sev1'
        assert alert.immediate is True
        assert 'freeze_rollout' in alert.mandatory_actions

    def test_required_dashboard_coverage_exists(self):
        panel_keys = {
            panel.key
            for dashboard in DEFAULT_OPERATIONAL_CATALOG.dashboards
            for panel in dashboard.panels
        }
        assert REQUIRED_DASHBOARD_PANEL_KEYS.issubset(panel_keys)

    def test_escalation_owner_model_matches_contract(self):
        assert DEFAULT_OPERATIONAL_CATALOG.escalation_owner_model == REQUIRED_ESCALATION_OWNERS


class TestExporters:
    """Ensure we can export alerting configuration from the catalog."""

    def test_prometheus_rule_groups_shape(self):
        groups = build_prometheus_rule_groups(DEFAULT_OPERATIONAL_CATALOG)
        assert len(groups) == 1
        group = groups[0]
        assert group['name'] == 'feature3-control-plane-operations'

        alert_names = {rule['alert'] for rule in group['rules']}
        assert REQUIRED_ALERT_KEYS.issubset(alert_names)

    def test_catalog_as_dict_contains_core_sections(self):
        payload = operational_catalog_as_dict(DEFAULT_OPERATIONAL_CATALOG)
        assert 'slos' in payload
        assert 'alerts' in payload
        assert 'dashboards' in payload
        assert 'escalation_owner_model' in payload
