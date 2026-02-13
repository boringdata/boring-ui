"""SLO, alert, and dashboard catalog for Feature 3 operations readiness.

Bead: bd-223o.15.1 (J1)

This module codifies section 17.2 of
``docs/ideas/feature-3-external-control-plane-with-auth.md`` into a
machine-readable catalog that can be validated in tests and exported to
monitoring systems.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class SLOSpec:
    """Service level objective definition."""

    key: str
    description: str
    target_percent: float
    measurement_window: str
    sli_query: str
    alert_keys: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AlertSpec:
    """Alert rule definition for on-call signals and escalation."""

    key: str
    description: str
    severity: str
    window: str
    threshold: float
    threshold_unit: str
    expr: str
    owner: str
    group_by: tuple[str, ...] = field(default_factory=tuple)
    immediate: bool = False
    mandatory_actions: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class DashboardPanelSpec:
    """Single dashboard panel contract."""

    key: str
    title: str
    query: str
    category: str


@dataclass(frozen=True, slots=True)
class DashboardSpec:
    """Dashboard contract used to verify required coverage exists."""

    key: str
    description: str
    panels: tuple[DashboardPanelSpec, ...]


@dataclass(frozen=True, slots=True)
class OperationalCatalog:
    """Top-level SLO/alert/dashboard contract and owner model."""

    slos: tuple[SLOSpec, ...]
    alerts: tuple[AlertSpec, ...]
    dashboards: tuple[DashboardSpec, ...]
    escalation_owner_model: dict[str, str]


REQUIRED_SLO_KEYS = frozenset(
    {
        'api_availability_monthly',
        'provisioning_reliability_monthly',
    }
)

REQUIRED_ALERT_KEYS = frozenset(
    {
        'api_5xx_error_rate_burn',
        'provisioning_error_rate_burn',
        'tenant_isolation_violation',
    }
)

REQUIRED_DASHBOARD_PANEL_KEYS = frozenset(
    {
        'api_availability_monthly',
        'api_5xx_error_rate_5m',
        'provisioning_success_rate_30d',
        'provisioning_error_rate_15m_by_code',
        'tenant_isolation_incidents',
    }
)

REQUIRED_ESCALATION_OWNERS = {
    'control_plane_api_failures': 'backend_oncall_owner',
    'supabase_auth_or_rls_failures': 'database_platform_owner',
    'sprite_runtime_or_proxy_failures': 'runtime_owner',
}


def build_default_operational_catalog() -> OperationalCatalog:
    """Build the canonical Feature 3 V0 operational catalog."""

    alerts = (
        AlertSpec(
            key='api_5xx_error_rate_burn',
            description='5m 5xx burn-rate for /api/v1/workspaces* and /auth/callback',
            severity='warning',
            window='5m',
            threshold=2.0,
            threshold_unit='percent_error_rate',
            expr=(
                "(" 
                "sum(rate(http_server_requests_total{path=~\"/api/v1/workspaces.*|/auth/callback\",status=~\"5..\"}[5m]))"
                " / "
                "sum(rate(http_server_requests_total{path=~\"/api/v1/workspaces.*|/auth/callback\"}[5m]))"
                ") > 0.02"
            ),
            owner='backend_oncall_owner',
            group_by=('path',),
        ),
        AlertSpec(
            key='provisioning_error_rate_burn',
            description='15m provisioning failure rate by last_error_code',
            severity='critical',
            window='15m',
            threshold=5.0,
            threshold_unit='percent_failure_rate',
            expr=(
                "(" 
                "sum by (last_error_code)(increase(control_plane_provision_jobs_total{state=\"error\"}[15m]))"
                " / clamp_min(" 
                "sum(increase(control_plane_provision_jobs_total{state=~\"ready|error\"}[15m])), 1"
                ")"
                ") > 0.05"
            ),
            owner='runtime_owner',
            group_by=('last_error_code',),
        ),
        AlertSpec(
            key='tenant_isolation_violation',
            description='Immediate SEV-1 alert on confirmed cross-workspace access event',
            severity='sev1',
            window='1m',
            threshold=0.0,
            threshold_unit='count_gt',
            expr='increase(control_plane_tenant_boundary_incidents_total[1m]) > 0',
            owner='backend_oncall_owner',
            immediate=True,
            mandatory_actions=(
                'freeze_rollout',
                'rotate_affected_credentials',
                'publish_incident_summary',
            ),
        ),
    )

    slos = (
        SLOSpec(
            key='api_availability_monthly',
            description='Control-plane auth/workspace API availability',
            target_percent=99.5,
            measurement_window='30d',
            sli_query=(
                "100 * (1 - ("
                "sum(increase(http_server_requests_total{path=~\"/api/v1/workspaces.*|/auth/callback\",status=~\"5..\"}[30d]))"
                " / clamp_min(sum(increase(http_server_requests_total{path=~\"/api/v1/workspaces.*|/auth/callback\"}[30d])), 1)"
                "))"
            ),
            alert_keys=('api_5xx_error_rate_burn',),
        ),
        SLOSpec(
            key='provisioning_reliability_monthly',
            description='Successful provisioning ratio for valid releases',
            target_percent=99.0,
            measurement_window='30d',
            sli_query=(
                "100 * ("
                "sum(increase(control_plane_provision_jobs_total{state=\"ready\",release_valid=\"true\"}[30d]))"
                " / clamp_min(sum(increase(control_plane_provision_jobs_total{state=~\"ready|error\",release_valid=\"true\"}[30d])), 1)"
                ")"
            ),
            alert_keys=('provisioning_error_rate_burn',),
        ),
    )

    dashboards = (
        DashboardSpec(
            key='control_plane_reliability',
            description=(
                'Availability, provisioning reliability, and tenant-boundary ' 
                'incident visibility for Feature 3 operations.'
            ),
            panels=(
                DashboardPanelSpec(
                    key='api_availability_monthly',
                    title='API Availability (30d)',
                    query='api_availability_monthly',
                    category='availability',
                ),
                DashboardPanelSpec(
                    key='api_5xx_error_rate_5m',
                    title='API 5xx Error Rate (5m)',
                    query='api_5xx_error_rate_burn',
                    category='availability',
                ),
                DashboardPanelSpec(
                    key='provisioning_success_rate_30d',
                    title='Provisioning Success Rate (30d)',
                    query='provisioning_reliability_monthly',
                    category='provisioning',
                ),
                DashboardPanelSpec(
                    key='provisioning_error_rate_15m_by_code',
                    title='Provisioning Error Rate by last_error_code (15m)',
                    query='provisioning_error_rate_burn',
                    category='provisioning',
                ),
                DashboardPanelSpec(
                    key='tenant_isolation_incidents',
                    title='Tenant Isolation Incidents (SEV-1 trigger)',
                    query='tenant_isolation_violation',
                    category='tenant_safety',
                ),
            ),
        ),
    )

    return OperationalCatalog(
        slos=slos,
        alerts=alerts,
        dashboards=dashboards,
        escalation_owner_model=dict(REQUIRED_ESCALATION_OWNERS),
    )


DEFAULT_OPERATIONAL_CATALOG = build_default_operational_catalog()


def validate_operational_catalog(catalog: OperationalCatalog) -> None:
    """Validate that required Feature 3 operational contracts exist."""

    slo_keys = {slo.key for slo in catalog.slos}
    if not REQUIRED_SLO_KEYS.issubset(slo_keys):
        missing = sorted(REQUIRED_SLO_KEYS - slo_keys)
        raise ValueError(f'missing required SLO entries: {missing}')

    alert_map = {alert.key: alert for alert in catalog.alerts}
    alert_keys = set(alert_map)
    if not REQUIRED_ALERT_KEYS.issubset(alert_keys):
        missing = sorted(REQUIRED_ALERT_KEYS - alert_keys)
        raise ValueError(f'missing required alert entries: {missing}')

    api_alert = alert_map['api_5xx_error_rate_burn']
    if api_alert.threshold != 2.0 or api_alert.window != '5m':
        raise ValueError('api_5xx_error_rate_burn must remain 2% over 5m')

    prov_alert = alert_map['provisioning_error_rate_burn']
    if prov_alert.threshold != 5.0 or prov_alert.window != '15m':
        raise ValueError('provisioning_error_rate_burn must remain 5% over 15m')
    if 'last_error_code' not in prov_alert.group_by:
        raise ValueError('provisioning_error_rate_burn must group by last_error_code')

    tenant_alert = alert_map['tenant_isolation_violation']
    if tenant_alert.severity.lower() != 'sev1' or not tenant_alert.immediate:
        raise ValueError('tenant_isolation_violation must be immediate SEV-1')

    panel_keys = {
        panel.key
        for dashboard in catalog.dashboards
        for panel in dashboard.panels
    }
    if not REQUIRED_DASHBOARD_PANEL_KEYS.issubset(panel_keys):
        missing = sorted(REQUIRED_DASHBOARD_PANEL_KEYS - panel_keys)
        raise ValueError(f'missing required dashboard panels: {missing}')

    if catalog.escalation_owner_model != REQUIRED_ESCALATION_OWNERS:
        raise ValueError('escalation owner model does not match Feature 3 contract')


def build_prometheus_rule_groups(
    catalog: OperationalCatalog = DEFAULT_OPERATIONAL_CATALOG,
) -> list[dict[str, Any]]:
    """Render alert rules into Prometheus rule-group shape."""

    validate_operational_catalog(catalog)

    rules = []
    for alert in catalog.alerts:
        labels = {
            'severity': alert.severity,
            'owner': alert.owner,
            'window': alert.window,
        }
        if alert.immediate:
            labels['page'] = 'immediate'

        annotations = {
            'summary': alert.description,
            'threshold': f'{alert.threshold} {alert.threshold_unit}',
        }
        if alert.mandatory_actions:
            annotations['mandatory_actions'] = ', '.join(alert.mandatory_actions)

        rules.append(
            {
                'alert': alert.key,
                'expr': alert.expr,
                'for': alert.window,
                'labels': labels,
                'annotations': annotations,
            }
        )

    return [
        {
            'name': 'feature3-control-plane-operations',
            'rules': rules,
        }
    ]


def operational_catalog_as_dict(
    catalog: OperationalCatalog = DEFAULT_OPERATIONAL_CATALOG,
) -> dict[str, Any]:
    """Serialize catalog for diagnostics or export."""

    validate_operational_catalog(catalog)
    return asdict(catalog)
