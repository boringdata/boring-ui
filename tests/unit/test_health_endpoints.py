"""Unit tests for structured health and readiness endpoints."""
import pytest

from boring_ui.api.health_endpoints import (
    DependencyState,
    DependencyStatus,
    HealthRegistry,
    create_default_registry,
)


NOW = 1700000000.0


class TestDependencyState:

    def test_defaults(self):
        d = DependencyState(name='svc')
        assert d.status == DependencyStatus.UNKNOWN
        assert d.critical is True

    def test_mark_healthy(self):
        d = DependencyState(name='svc')
        d.mark_healthy('ok', now=NOW)
        assert d.status == DependencyStatus.HEALTHY
        assert d.message == 'ok'
        assert d.last_check_ts == NOW

    def test_mark_degraded(self):
        d = DependencyState(name='svc')
        d.mark_degraded('slow', now=NOW)
        assert d.status == DependencyStatus.DEGRADED

    def test_mark_unhealthy(self):
        d = DependencyState(name='svc')
        d.mark_unhealthy('down', now=NOW)
        assert d.status == DependencyStatus.UNHEALTHY


class TestHealthRegistry:

    def test_register_and_get(self):
        reg = HealthRegistry()
        dep = reg.register('svc')
        assert reg.get('svc') is dep

    def test_get_unknown(self):
        reg = HealthRegistry()
        assert reg.get('nope') is None

    def test_all_deps(self):
        reg = HealthRegistry()
        reg.register('a')
        reg.register('b')
        assert len(reg.all_deps) == 2

    def test_critical_deps(self):
        reg = HealthRegistry()
        reg.register('crit', critical=True)
        reg.register('non_crit', critical=False)
        assert len(reg.critical_deps) == 1
        assert reg.critical_deps[0].name == 'crit'


class TestLiveness:

    def test_always_live(self):
        reg = HealthRegistry()
        reg.register('svc')
        assert reg.is_live() is True

    def test_live_even_with_unhealthy_dep(self):
        reg = HealthRegistry()
        dep = reg.register('svc')
        dep.mark_unhealthy('down')
        assert reg.is_live() is True

    def test_liveness_response_ok(self):
        reg = HealthRegistry()
        dep = reg.register('svc')
        dep.mark_healthy('ok')
        resp = reg.liveness_response()
        assert resp['status'] == 'ok'

    def test_liveness_response_degraded(self):
        reg = HealthRegistry()
        dep = reg.register('svc')
        dep.mark_degraded('slow')
        resp = reg.liveness_response()
        assert resp['status'] == 'degraded'

    def test_liveness_response_unhealthy_shows_degraded(self):
        reg = HealthRegistry()
        dep = reg.register('svc')
        dep.mark_unhealthy('down')
        resp = reg.liveness_response()
        assert resp['status'] == 'degraded'

    def test_liveness_includes_checks(self):
        reg = HealthRegistry()
        dep = reg.register('svc')
        dep.mark_healthy('ok')
        resp = reg.liveness_response()
        assert 'svc' in resp['checks']
        assert resp['checks']['svc']['status'] == 'healthy'


class TestReadiness:

    def test_ready_when_all_healthy(self):
        reg = HealthRegistry()
        dep = reg.register('svc')
        dep.mark_healthy('ok')
        assert reg.is_ready() is True

    def test_not_ready_when_critical_unhealthy(self):
        reg = HealthRegistry()
        dep = reg.register('svc', critical=True)
        dep.mark_unhealthy('down')
        assert reg.is_ready() is False

    def test_ready_when_non_critical_unhealthy(self):
        reg = HealthRegistry()
        crit = reg.register('crit', critical=True)
        crit.mark_healthy('ok')
        non_crit = reg.register('optional', critical=False)
        non_crit.mark_unhealthy('down')
        assert reg.is_ready() is True

    def test_not_ready_when_unknown(self):
        reg = HealthRegistry()
        reg.register('svc', critical=True)
        assert reg.is_ready() is False

    def test_ready_with_degraded_critical(self):
        reg = HealthRegistry()
        dep = reg.register('svc', critical=True)
        dep.mark_degraded('slow')
        # Degraded is not unhealthy - still ready
        assert reg.is_ready() is True

    def test_readiness_response_ready(self):
        reg = HealthRegistry()
        dep = reg.register('svc')
        dep.mark_healthy('ok')
        status, body = reg.readiness_response()
        assert status == 200
        assert body['status'] == 'ready'

    def test_readiness_response_not_ready(self):
        reg = HealthRegistry()
        dep = reg.register('svc')
        dep.mark_unhealthy('down')
        status, body = reg.readiness_response()
        assert status == 503
        assert body['status'] == 'not_ready'

    def test_readiness_includes_critical_flag(self):
        reg = HealthRegistry()
        reg.register('crit', critical=True)
        reg.register('opt', critical=False)
        _, body = reg.readiness_response()
        assert body['checks']['crit']['critical'] is True
        assert body['checks']['opt']['critical'] is False

    def test_empty_registry_is_ready(self):
        reg = HealthRegistry()
        assert reg.is_ready() is True


class TestCreateDefaultRegistry:

    def test_has_workspace_service(self):
        reg = create_default_registry()
        assert reg.get('workspace_service') is not None

    def test_has_workspace_version(self):
        reg = create_default_registry()
        assert reg.get('workspace_version') is not None

    def test_both_critical(self):
        reg = create_default_registry()
        assert reg.get('workspace_service').critical is True
        assert reg.get('workspace_version').critical is True

    def test_not_ready_initially(self):
        reg = create_default_registry()
        assert reg.is_ready() is False  # Unknown status
