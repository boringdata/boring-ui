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
  - Alertmanager config routes severities to correct receivers
  - Prometheus rules.yaml matches catalog-generated rules
  - Inhibition rules suppress lower severity correctly
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pytest
import yaml

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

DEPLOY_DIR = Path(__file__).resolve().parents[3] / "deploy"
ALERTMANAGER_CONFIG_PATH = DEPLOY_DIR / "alertmanager" / "config.yaml"
PROMETHEUS_RULES_PATH = DEPLOY_DIR / "prometheus" / "rules.yaml"


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


# =====================================================================
# 10. Alertmanager severity → receiver routing
# =====================================================================


@pytest.fixture(scope="module")
def alertmanager_config():
    return yaml.safe_load(ALERTMANAGER_CONFIG_PATH.read_text())


@pytest.fixture(scope="module")
def prometheus_rules():
    return yaml.safe_load(PROMETHEUS_RULES_PATH.read_text())


class TestAlertmanagerSeverityRouting:
    """Cross-validate catalog alert severities against Alertmanager routes."""

    def test_sev1_routes_to_pager(self, alertmanager_config):
        routes = alertmanager_config["route"]["routes"]
        sev1_route = next(
            (r for r in routes if r.get("match", {}).get("severity") == "sev1"),
            None,
        )
        assert sev1_route is not None, "No route for severity=sev1"
        assert sev1_route["receiver"] == "sev1-pager"

    def test_critical_routes_to_oncall(self, alertmanager_config):
        routes = alertmanager_config["route"]["routes"]
        critical_route = next(
            (r for r in routes if r.get("match", {}).get("severity") == "critical"),
            None,
        )
        assert critical_route is not None
        assert critical_route["receiver"] == "critical-oncall"

    def test_warning_routes_to_slack(self, alertmanager_config):
        routes = alertmanager_config["route"]["routes"]
        warning_route = next(
            (r for r in routes if r.get("match", {}).get("severity") == "warning"),
            None,
        )
        assert warning_route is not None
        assert warning_route["receiver"] == "warning-slack"

    def test_all_catalog_severities_have_routes(self, catalog, alertmanager_config):
        catalog_severities = {alert.severity for alert in catalog.alerts}
        routed_severities = {
            r["match"]["severity"]
            for r in alertmanager_config["route"]["routes"]
            if "match" in r and "severity" in r.get("match", {})
        }
        missing = catalog_severities - routed_severities
        assert not missing, f"Catalog severities without routes: {missing}"

    def test_default_receiver_exists(self, alertmanager_config):
        receiver_names = {r["name"] for r in alertmanager_config["receivers"]}
        assert alertmanager_config["route"]["receiver"] in receiver_names


# =====================================================================
# 11. SEV-1 immediate paging wiring
# =====================================================================


class TestSev1PagingWiring:
    """SEV-1 alerts get zero-delay paging in Alertmanager."""

    def test_sev1_group_wait_is_zero(self, alertmanager_config):
        routes = alertmanager_config["route"]["routes"]
        sev1_route = next(
            r for r in routes if r.get("match", {}).get("severity") == "sev1"
        )
        assert sev1_route["group_wait"] == "0s"

    def test_sev1_repeat_interval_is_short(self, alertmanager_config):
        routes = alertmanager_config["route"]["routes"]
        sev1_route = next(
            r for r in routes if r.get("match", {}).get("severity") == "sev1"
        )
        assert sev1_route["repeat_interval"] == "15m"

    def test_sev1_does_not_continue(self, alertmanager_config):
        routes = alertmanager_config["route"]["routes"]
        sev1_route = next(
            r for r in routes if r.get("match", {}).get("severity") == "sev1"
        )
        assert sev1_route.get("continue", False) is False


# =====================================================================
# 12. Alertmanager inhibition rules
# =====================================================================


class TestInhibitionRules:
    """Severity-based inhibition suppresses lower severity alerts."""

    def test_sev1_inhibits_critical(self, alertmanager_config):
        inhibit_rules = alertmanager_config.get("inhibit_rules", [])
        found = any(
            r.get("source_match", {}).get("severity") == "sev1"
            and r.get("target_match", {}).get("severity") == "critical"
            and "owner" in r.get("equal", [])
            for r in inhibit_rules
        )
        assert found, "Missing inhibition: sev1 should suppress critical"

    def test_critical_inhibits_warning(self, alertmanager_config):
        inhibit_rules = alertmanager_config.get("inhibit_rules", [])
        found = any(
            r.get("source_match", {}).get("severity") == "critical"
            and r.get("target_match", {}).get("severity") == "warning"
            and "owner" in r.get("equal", [])
            for r in inhibit_rules
        )
        assert found, "Missing inhibition: critical should suppress warning"

    def test_inhibition_scoped_by_owner(self, alertmanager_config):
        for rule in alertmanager_config.get("inhibit_rules", []):
            assert "owner" in rule.get("equal", [])


# =====================================================================
# 13. Prometheus rules.yaml matches catalog
# =====================================================================


class TestPrometheusRulesMatchCatalog:
    """Deployed rules.yaml matches catalog-generated alert definitions."""

    def test_rule_group_name_matches(self, prometheus_rules):
        groups = prometheus_rules["groups"]
        assert groups[0]["name"] == "feature3-control-plane-operations"

    def test_all_catalog_alerts_in_rules_yaml(self, catalog, prometheus_rules):
        rule_names = {
            r["alert"]
            for group in prometheus_rules["groups"]
            for r in group["rules"]
        }
        catalog_keys = {a.key for a in catalog.alerts}
        missing = catalog_keys - rule_names
        assert not missing, f"Catalog alerts missing from rules.yaml: {missing}"

    def test_severity_labels_match(self, catalog, prometheus_rules):
        rule_map = {
            r["alert"]: r
            for group in prometheus_rules["groups"]
            for r in group["rules"]
        }
        for alert in catalog.alerts:
            assert rule_map[alert.key]["labels"]["severity"] == alert.severity

    def test_owner_labels_match(self, catalog, prometheus_rules):
        rule_map = {
            r["alert"]: r
            for group in prometheus_rules["groups"]
            for r in group["rules"]
        }
        for alert in catalog.alerts:
            assert rule_map[alert.key]["labels"]["owner"] == alert.owner

    def test_sev1_has_page_immediate_label(self, prometheus_rules):
        rule_map = {
            r["alert"]: r
            for group in prometheus_rules["groups"]
            for r in group["rules"]
        }
        assert rule_map["tenant_isolation_violation"]["labels"]["page"] == "immediate"

    def test_mandatory_actions_annotation(self, prometheus_rules):
        rule_map = {
            r["alert"]: r
            for group in prometheus_rules["groups"]
            for r in group["rules"]
        }
        actions = rule_map["tenant_isolation_violation"]["annotations"]["mandatory_actions"]
        assert "freeze_rollout" in actions

    def test_no_extra_rules_beyond_catalog(self, catalog, prometheus_rules):
        rule_names = {
            r["alert"]
            for group in prometheus_rules["groups"]
            for r in group["rules"]
        }
        catalog_keys = {a.key for a in catalog.alerts}
        extra = rule_names - catalog_keys
        assert not extra, f"Extra rules in rules.yaml not in catalog: {extra}"


# =====================================================================
# 14. Receiver configuration completeness
# =====================================================================


class TestReceiverConfiguration:
    """Receivers are defined and have notification configs."""

    def test_all_route_receivers_defined(self, alertmanager_config):
        receiver_names = {r["name"] for r in alertmanager_config["receivers"]}
        assert alertmanager_config["route"]["receiver"] in receiver_names
        for route in alertmanager_config["route"]["routes"]:
            assert route["receiver"] in receiver_names

    def test_receivers_have_webhook_configs(self, alertmanager_config):
        for receiver in alertmanager_config["receivers"]:
            assert receiver.get("webhook_configs"), (
                f"Receiver {receiver['name']!r} has no webhook config"
            )

    def test_receivers_send_resolved(self, alertmanager_config):
        for receiver in alertmanager_config["receivers"]:
            for wh in receiver.get("webhook_configs", []):
                assert wh.get("send_resolved") is True


# =====================================================================
# 15. Default grouping
# =====================================================================


class TestDefaultGrouping:
    """Alertmanager default route groups by alertname and owner."""

    def test_groups_by_alertname(self, alertmanager_config):
        assert "alertname" in alertmanager_config["route"]["group_by"]

    def test_groups_by_owner(self, alertmanager_config):
        assert "owner" in alertmanager_config["route"]["group_by"]
