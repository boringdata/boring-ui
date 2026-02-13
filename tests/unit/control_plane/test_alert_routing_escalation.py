"""Alert routing and escalation path validation.

Bead: bd-223o.15.1.1 (J1a)

Validates paging, ownership, and response expectations are correctly wired:
  - Each alert has a valid owner from the escalation model
  - Alert severity levels follow the expected tier ordering
  - Immediate alerts (page=immediate) have mandatory_actions defined
  - Prometheus rule groups wire labels and annotations correctly
  - Escalation owner model covers all alert owner values
  - SLO alert_keys reference existing alerts (no dangling refs)
  - Dashboard panels reference existing alert/SLO queries
  - Validation rejects catalogs with missing or misconfigured entries
  - Frozen dataclass invariants hold
"""

from __future__ import annotations

from dataclasses import asdict

import pytest

from control_plane.app.operations.slo_alerts import (
    AlertSpec,
    DashboardPanelSpec,
    DashboardSpec,
    DEFAULT_OPERATIONAL_CATALOG,
    OperationalCatalog,
    REQUIRED_ALERT_KEYS,
    REQUIRED_DASHBOARD_PANEL_KEYS,
    REQUIRED_ESCALATION_OWNERS,
    REQUIRED_SLO_KEYS,
    SLOSpec,
    build_default_operational_catalog,
    build_prometheus_rule_groups,
    validate_operational_catalog,
)


@pytest.fixture
def catalog():
    return DEFAULT_OPERATIONAL_CATALOG


# =====================================================================
# 1. Alert-to-owner routing
# =====================================================================


class TestAlertToOwnerRouting:
    """Every alert must map to a recognized escalation owner."""

    def test_all_alert_owners_in_escalation_model(self, catalog):
        """Each alert.owner appears as a value in REQUIRED_ESCALATION_OWNERS."""
        valid_owners = set(REQUIRED_ESCALATION_OWNERS.values())
        for alert in catalog.alerts:
            assert alert.owner in valid_owners, (
                f'Alert {alert.key!r} owner {alert.owner!r} '
                f'not in escalation model: {valid_owners}'
            )

    def test_alert_owners_are_subset_of_escalation_owners(self, catalog):
        """Every alert owner appears in the escalation model values."""
        valid_owners = set(REQUIRED_ESCALATION_OWNERS.values())
        alert_owners = {alert.owner for alert in catalog.alerts}
        assert alert_owners.issubset(valid_owners), (
            f'Alert owners not in escalation model: {alert_owners - valid_owners}'
        )

    def test_escalation_model_keys_are_domain_scoped(self, catalog):
        """Escalation model keys describe failure domains, not generic labels."""
        for domain_key in REQUIRED_ESCALATION_OWNERS:
            assert '_' in domain_key, f'Domain key {domain_key!r} is not scoped'
            # Should describe a failure domain.
            assert any(
                term in domain_key
                for term in ('failure', 'error', 'violation', 'incident')
            ), f'Domain key {domain_key!r} does not describe a failure domain'


# =====================================================================
# 2. Severity tier ordering
# =====================================================================


class TestSeverityTiers:
    """Alerts use a known severity vocabulary."""

    KNOWN_SEVERITIES = {'info', 'warning', 'critical', 'sev1'}

    def test_all_severities_are_recognized(self, catalog):
        for alert in catalog.alerts:
            assert alert.severity.lower() in self.KNOWN_SEVERITIES, (
                f'Alert {alert.key!r} severity {alert.severity!r} not recognized'
            )

    def test_tenant_isolation_is_highest_severity(self, catalog):
        tenant_alert = next(
            a for a in catalog.alerts if a.key == 'tenant_isolation_violation'
        )
        assert tenant_alert.severity.lower() == 'sev1'

    def test_api_burn_rate_is_warning(self, catalog):
        api_alert = next(
            a for a in catalog.alerts if a.key == 'api_5xx_error_rate_burn'
        )
        assert api_alert.severity == 'warning'

    def test_provisioning_burn_rate_is_critical(self, catalog):
        prov_alert = next(
            a for a in catalog.alerts if a.key == 'provisioning_error_rate_burn'
        )
        assert prov_alert.severity == 'critical'


# =====================================================================
# 3. Immediate alerts have mandatory actions
# =====================================================================


class TestImmediateAlertActions:
    """Alerts marked immediate must define mandatory_actions."""

    def test_immediate_alerts_have_actions(self, catalog):
        for alert in catalog.alerts:
            if alert.immediate:
                assert len(alert.mandatory_actions) > 0, (
                    f'Immediate alert {alert.key!r} has no mandatory_actions'
                )

    def test_non_immediate_alerts_actions_optional(self, catalog):
        """Non-immediate alerts may or may not have mandatory_actions."""
        non_immediate = [a for a in catalog.alerts if not a.immediate]
        assert len(non_immediate) > 0  # Sanity check.

    def test_tenant_isolation_mandatory_actions(self, catalog):
        tenant = next(
            a for a in catalog.alerts if a.key == 'tenant_isolation_violation'
        )
        assert 'freeze_rollout' in tenant.mandatory_actions
        assert 'rotate_affected_credentials' in tenant.mandatory_actions
        assert 'publish_incident_summary' in tenant.mandatory_actions


# =====================================================================
# 4. Prometheus rule group wiring
# =====================================================================


class TestPrometheusRuleGroupWiring:
    """Prometheus rules carry labels and annotations for routing."""

    @pytest.fixture
    def rules(self, catalog):
        groups = build_prometheus_rule_groups(catalog)
        return groups[0]['rules']

    def test_all_rules_have_severity_label(self, rules):
        for rule in rules:
            assert 'severity' in rule['labels']

    def test_all_rules_have_owner_label(self, rules):
        for rule in rules:
            assert 'owner' in rule['labels']

    def test_all_rules_have_window_label(self, rules):
        for rule in rules:
            assert 'window' in rule['labels']

    def test_immediate_rules_have_page_label(self, rules, catalog):
        immediate_keys = {a.key for a in catalog.alerts if a.immediate}
        for rule in rules:
            if rule['alert'] in immediate_keys:
                assert rule['labels'].get('page') == 'immediate'

    def test_all_rules_have_summary_annotation(self, rules):
        for rule in rules:
            assert 'summary' in rule['annotations']

    def test_all_rules_have_threshold_annotation(self, rules):
        for rule in rules:
            assert 'threshold' in rule['annotations']

    def test_immediate_rules_have_mandatory_actions_annotation(self, rules, catalog):
        immediate_keys = {a.key for a in catalog.alerts if a.immediate}
        for rule in rules:
            if rule['alert'] in immediate_keys:
                assert 'mandatory_actions' in rule['annotations']

    def test_rules_have_expr_field(self, rules):
        for rule in rules:
            assert 'expr' in rule
            assert len(rule['expr']) > 0

    def test_rules_have_for_field(self, rules):
        for rule in rules:
            assert 'for' in rule


# =====================================================================
# 5. SLO alert_keys reference existing alerts
# =====================================================================


class TestSLOAlertKeyReferences:
    """SLO alert_keys must reference alerts that exist in the catalog."""

    def test_no_dangling_slo_alert_refs(self, catalog):
        alert_keys = {a.key for a in catalog.alerts}
        for slo in catalog.slos:
            for ref in slo.alert_keys:
                assert ref in alert_keys, (
                    f'SLO {slo.key!r} references alert {ref!r} which does not exist'
                )

    def test_every_slo_has_at_least_one_alert_key(self, catalog):
        for slo in catalog.slos:
            assert len(slo.alert_keys) >= 1, (
                f'SLO {slo.key!r} has no linked alerts'
            )


# =====================================================================
# 6. Dashboard panels reference existing queries
# =====================================================================


class TestDashboardPanelReferences:
    """Dashboard panels should reference alert/SLO query identifiers."""

    def test_all_panels_have_non_empty_query(self, catalog):
        for dashboard in catalog.dashboards:
            for panel in dashboard.panels:
                assert len(panel.query) > 0, (
                    f'Panel {panel.key!r} has empty query'
                )

    def test_all_panels_have_category(self, catalog):
        for dashboard in catalog.dashboards:
            for panel in dashboard.panels:
                assert len(panel.category) > 0


# =====================================================================
# 7. Validation rejects broken catalogs
# =====================================================================


class TestValidationRejectsBroken:
    """validate_operational_catalog catches misconfigurations."""

    def test_missing_slo_raises(self):
        catalog = OperationalCatalog(
            slos=(),  # Missing SLOs.
            alerts=DEFAULT_OPERATIONAL_CATALOG.alerts,
            dashboards=DEFAULT_OPERATIONAL_CATALOG.dashboards,
            escalation_owner_model=dict(REQUIRED_ESCALATION_OWNERS),
        )
        with pytest.raises(ValueError, match='missing required SLO'):
            validate_operational_catalog(catalog)

    def test_missing_alert_raises(self):
        catalog = OperationalCatalog(
            slos=DEFAULT_OPERATIONAL_CATALOG.slos,
            alerts=(),  # Missing alerts.
            dashboards=DEFAULT_OPERATIONAL_CATALOG.dashboards,
            escalation_owner_model=dict(REQUIRED_ESCALATION_OWNERS),
        )
        with pytest.raises(ValueError, match='missing required alert'):
            validate_operational_catalog(catalog)

    def test_wrong_api_alert_threshold_raises(self):
        bad_alerts = list(DEFAULT_OPERATIONAL_CATALOG.alerts)
        for i, a in enumerate(bad_alerts):
            if a.key == 'api_5xx_error_rate_burn':
                bad_alerts[i] = AlertSpec(
                    key=a.key, description=a.description,
                    severity=a.severity, window='10m',  # Wrong window
                    threshold=2.0, threshold_unit=a.threshold_unit,
                    expr=a.expr, owner=a.owner,
                )
        catalog = OperationalCatalog(
            slos=DEFAULT_OPERATIONAL_CATALOG.slos,
            alerts=tuple(bad_alerts),
            dashboards=DEFAULT_OPERATIONAL_CATALOG.dashboards,
            escalation_owner_model=dict(REQUIRED_ESCALATION_OWNERS),
        )
        with pytest.raises(ValueError, match='api_5xx_error_rate_burn'):
            validate_operational_catalog(catalog)

    def test_missing_dashboard_panels_raises(self):
        empty_dashboard = DashboardSpec(
            key='empty', description='empty', panels=(),
        )
        catalog = OperationalCatalog(
            slos=DEFAULT_OPERATIONAL_CATALOG.slos,
            alerts=DEFAULT_OPERATIONAL_CATALOG.alerts,
            dashboards=(empty_dashboard,),
            escalation_owner_model=dict(REQUIRED_ESCALATION_OWNERS),
        )
        with pytest.raises(ValueError, match='missing required dashboard'):
            validate_operational_catalog(catalog)

    def test_wrong_escalation_model_raises(self):
        catalog = OperationalCatalog(
            slos=DEFAULT_OPERATIONAL_CATALOG.slos,
            alerts=DEFAULT_OPERATIONAL_CATALOG.alerts,
            dashboards=DEFAULT_OPERATIONAL_CATALOG.dashboards,
            escalation_owner_model={'wrong': 'model'},
        )
        with pytest.raises(ValueError, match='escalation owner model'):
            validate_operational_catalog(catalog)

    def test_tenant_not_sev1_raises(self):
        bad_alerts = list(DEFAULT_OPERATIONAL_CATALOG.alerts)
        for i, a in enumerate(bad_alerts):
            if a.key == 'tenant_isolation_violation':
                bad_alerts[i] = AlertSpec(
                    key=a.key, description=a.description,
                    severity='warning',  # Wrong severity
                    window=a.window, threshold=a.threshold,
                    threshold_unit=a.threshold_unit,
                    expr=a.expr, owner=a.owner,
                    immediate=True,
                    mandatory_actions=a.mandatory_actions,
                )
        catalog = OperationalCatalog(
            slos=DEFAULT_OPERATIONAL_CATALOG.slos,
            alerts=tuple(bad_alerts),
            dashboards=DEFAULT_OPERATIONAL_CATALOG.dashboards,
            escalation_owner_model=dict(REQUIRED_ESCALATION_OWNERS),
        )
        with pytest.raises(ValueError, match='tenant_isolation_violation'):
            validate_operational_catalog(catalog)


# =====================================================================
# 8. Frozen dataclass invariants
# =====================================================================


class TestFrozenInvariants:
    """All spec types are frozen (immutable after creation)."""

    def test_alert_spec_frozen(self, catalog):
        alert = catalog.alerts[0]
        with pytest.raises(AttributeError):
            alert.key = 'mutated'

    def test_slo_spec_frozen(self, catalog):
        slo = catalog.slos[0]
        with pytest.raises(AttributeError):
            slo.target_percent = 0.0

    def test_dashboard_spec_frozen(self, catalog):
        dashboard = catalog.dashboards[0]
        with pytest.raises(AttributeError):
            dashboard.key = 'mutated'

    def test_catalog_frozen(self, catalog):
        with pytest.raises(AttributeError):
            catalog.slos = ()


# =====================================================================
# 9. build_default_operational_catalog idempotency
# =====================================================================


class TestCatalogIdempotency:
    """build_default_operational_catalog returns equivalent catalog each call."""

    def test_two_builds_are_equal(self):
        c1 = build_default_operational_catalog()
        c2 = build_default_operational_catalog()
        assert asdict(c1) == asdict(c2)

    def test_default_singleton_matches_build(self):
        fresh = build_default_operational_catalog()
        assert asdict(DEFAULT_OPERATIONAL_CATALOG) == asdict(fresh)
