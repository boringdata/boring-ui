"""Unit tests for fault injection suite.

Tests all fault scenarios, assertion helpers, the runner, and
verifies deterministic pass/fail behavior for each injected fault.
"""
import json

import pytest

from boring_ui.api.fault_injection import (
    ALL_FAULT_SCENARIOS,
    AssertionOutcome,
    FaultAssertion,
    FaultInjectionRunner,
    FaultScenarioResult,
    FaultType,
    inject_auth_expiry,
    inject_exec_attach_fail,
    inject_health_flap_active,
    inject_provider_timeout_cascade,
    inject_rate_limit_burst,
    inject_service_503,
    inject_ws_midstream_disconnect,
)
from boring_ui.api.error_normalization import (
    WS_PROVIDER_TIMEOUT,
    WS_PROVIDER_UNAVAILABLE,
    WS_RATE_LIMITED,
    WS_SESSION_TERMINATED,
)
from boring_ui.api.test_artifacts import EventTimeline, StructuredTestLogger


# ── FaultAssertion ──


class TestFaultAssertion:

    def test_pass(self):
        a = FaultAssertion(
            name='test', outcome=AssertionOutcome.PASS,
            expected='200', actual='200',
        )
        assert a.passed

    def test_fail(self):
        a = FaultAssertion(
            name='test', outcome=AssertionOutcome.FAIL,
            expected='200', actual='500', message='wrong status',
        )
        assert not a.passed
        assert a.message == 'wrong status'

    def test_frozen(self):
        a = FaultAssertion(
            name='test', outcome=AssertionOutcome.PASS,
            expected='x', actual='x',
        )
        with pytest.raises(AttributeError):
            a.name = 'changed'

    def test_to_dict(self):
        a = FaultAssertion(
            name='check', outcome=AssertionOutcome.PASS,
            expected='a', actual='a',
        )
        d = a.to_dict()
        assert d['name'] == 'check'
        assert d['outcome'] == 'pass'


# ── FaultScenarioResult ──


class TestFaultScenarioResult:

    def test_all_passed(self):
        r = FaultScenarioResult(
            fault_type=FaultType.SERVICE_503,
            assertions=[
                FaultAssertion('a', AssertionOutcome.PASS, '1', '1'),
                FaultAssertion('b', AssertionOutcome.PASS, '2', '2'),
            ],
        )
        assert r.all_passed
        assert r.pass_count == 2
        assert r.fail_count == 0

    def test_some_failed(self):
        r = FaultScenarioResult(
            fault_type=FaultType.SERVICE_503,
            assertions=[
                FaultAssertion('a', AssertionOutcome.PASS, '1', '1'),
                FaultAssertion('b', AssertionOutcome.FAIL, '2', '3'),
            ],
        )
        assert not r.all_passed
        assert r.pass_count == 1
        assert r.fail_count == 1

    def test_empty_assertions(self):
        r = FaultScenarioResult(fault_type=FaultType.SERVICE_503)
        assert r.all_passed
        assert r.pass_count == 0

    def test_to_dict(self):
        r = FaultScenarioResult(
            fault_type=FaultType.RATE_LIMIT_BURST,
            assertions=[FaultAssertion('a', AssertionOutcome.PASS, '1', '1')],
            elapsed_ms=1.5,
        )
        d = r.to_dict()
        assert d['fault_type'] == 'rate_limit_burst'
        assert d['all_passed'] is True
        assert d['elapsed_ms'] == 1.5

    def test_to_dict_serializable(self):
        r = FaultScenarioResult(
            fault_type=FaultType.SERVICE_503,
            assertions=[FaultAssertion('a', AssertionOutcome.PASS, '1', '1')],
        )
        json.dumps(r.to_dict())


# ── inject_service_503 ──


class TestInjectService503:

    def test_all_pass(self):
        result = inject_service_503()
        assert result.fault_type == FaultType.SERVICE_503
        assert result.all_passed
        assert result.pass_count >= 7

    def test_http_mapped_status(self):
        result = inject_service_503()
        status_checks = [a for a in result.assertions if 'mapped' in a.name or 'http_status' in a.name]
        assert all(a.passed for a in status_checks)

    def test_ws_close_code(self):
        result = inject_service_503()
        ws_checks = [a for a in result.assertions if 'ws_close' in a.name]
        assert all(a.passed for a in ws_checks)

    def test_retry_after(self):
        result = inject_service_503()
        retry_checks = [a for a in result.assertions if 'retry' in a.name]
        assert all(a.passed for a in retry_checks)


# ── inject_exec_attach_fail ──


class TestInjectExecAttachFail:

    def test_all_pass(self):
        result = inject_exec_attach_fail()
        assert result.fault_type == FaultType.EXEC_ATTACH_FAIL
        assert result.all_passed

    def test_no_internal_leak(self):
        result = inject_exec_attach_fail()
        leak_checks = [a for a in result.assertions if 'leak' in a.name]
        assert all(a.passed for a in leak_checks)

    def test_category_provider_error(self):
        result = inject_exec_attach_fail()
        cat_checks = [a for a in result.assertions if a.name == 'category']
        assert all(a.passed for a in cat_checks)
        assert any(a.expected == 'provider_error' for a in cat_checks)


# ── inject_ws_midstream_disconnect ──


class TestInjectWsMidstreamDisconnect:

    def test_all_pass(self):
        result = inject_ws_midstream_disconnect()
        assert result.fault_type == FaultType.WS_MIDSTREAM_DISCONNECT
        assert result.all_passed

    def test_session_terminated_code(self):
        result = inject_ws_midstream_disconnect()
        code_checks = [a for a in result.assertions if a.name == 'ws_close_code']
        assert any(a.expected == str(WS_SESSION_TERMINATED) for a in code_checks)

    def test_no_upstream_leak(self):
        result = inject_ws_midstream_disconnect()
        leak_checks = [a for a in result.assertions if 'leak' in a.name]
        assert all(a.passed for a in leak_checks)


# ── inject_rate_limit_burst ──


class TestInjectRateLimitBurst:

    def test_all_pass(self):
        result = inject_rate_limit_burst()
        assert result.fault_type == FaultType.RATE_LIMIT_BURST
        assert result.all_passed

    def test_http_429(self):
        result = inject_rate_limit_burst()
        status_checks = [a for a in result.assertions if a.name == 'http_status']
        assert all(a.passed for a in status_checks)
        assert any(a.expected == '429' for a in status_checks)

    def test_ws_close_code(self):
        result = inject_rate_limit_burst()
        code_checks = [a for a in result.assertions if a.name == 'ws_close_code']
        assert any(a.expected == str(WS_RATE_LIMITED) for a in code_checks)

    def test_retry_after(self):
        result = inject_rate_limit_burst()
        retry_checks = [a for a in result.assertions if 'retry' in a.name]
        assert all(a.passed for a in retry_checks)


# ── inject_auth_expiry ──


class TestInjectAuthExpiry:

    def test_all_pass(self):
        result = inject_auth_expiry()
        assert result.fault_type == FaultType.AUTH_EXPIRY
        assert result.all_passed

    def test_http_403(self):
        result = inject_auth_expiry()
        status_checks = [a for a in result.assertions if a.name == 'http_status']
        assert any(a.expected == '403' for a in status_checks)

    def test_no_retry(self):
        result = inject_auth_expiry()
        retry_checks = [a for a in result.assertions if 'retry' in a.name]
        assert all(a.passed for a in retry_checks)

    def test_ws_close_4008(self):
        result = inject_auth_expiry()
        code_checks = [a for a in result.assertions if a.name == 'ws_close_code']
        assert any(a.expected == '4008' for a in code_checks)


# ── inject_provider_timeout_cascade ──


class TestInjectProviderTimeoutCascade:

    def test_all_pass(self):
        result = inject_provider_timeout_cascade()
        assert result.fault_type == FaultType.PROVIDER_TIMEOUT_CASCADE
        assert result.all_passed

    def test_http_504(self):
        result = inject_provider_timeout_cascade()
        status_checks = [a for a in result.assertions if a.name == 'http_status']
        assert any(a.expected == '504' for a in status_checks)

    def test_ws_timeout_code(self):
        result = inject_provider_timeout_cascade()
        code_checks = [a for a in result.assertions if a.name == 'ws_close_code']
        assert any(a.expected == str(WS_PROVIDER_TIMEOUT) for a in code_checks)

    def test_no_internal_leak(self):
        result = inject_provider_timeout_cascade()
        leak_checks = [a for a in result.assertions if 'leak' in a.name]
        assert all(a.passed for a in leak_checks)


# ── inject_health_flap_active ──


class TestInjectHealthFlapActive:

    def test_all_pass(self):
        result = inject_health_flap_active()
        assert result.fault_type == FaultType.HEALTH_FLAP_ACTIVE
        assert result.all_passed

    def test_unhealthy_503(self):
        result = inject_health_flap_active()
        status_checks = [a for a in result.assertions if a.name == 'unhealthy_status']
        assert all(a.passed for a in status_checks)

    def test_retry_after_on_unavailable(self):
        result = inject_health_flap_active()
        retry_checks = [a for a in result.assertions if a.name == 'unhealthy_retry']
        assert all(a.passed for a in retry_checks)

    def test_ws_unavailable_code(self):
        result = inject_health_flap_active()
        ws_checks = [a for a in result.assertions if a.name == 'ws_unavail_code']
        assert all(a.passed for a in ws_checks)
        assert any(a.expected == str(WS_PROVIDER_UNAVAILABLE) for a in ws_checks)


# ── Scenario registry ──


class TestScenarioRegistry:

    def test_all_scenarios_registered(self):
        expected = {
            FaultType.SERVICE_503,
            FaultType.EXEC_ATTACH_FAIL,
            FaultType.WS_MIDSTREAM_DISCONNECT,
            FaultType.RATE_LIMIT_BURST,
            FaultType.AUTH_EXPIRY,
            FaultType.PROVIDER_TIMEOUT_CASCADE,
            FaultType.HEALTH_FLAP_ACTIVE,
        }
        assert set(ALL_FAULT_SCENARIOS.keys()) == expected

    def test_all_callable(self):
        for fn in ALL_FAULT_SCENARIOS.values():
            assert callable(fn)

    def test_all_return_result(self):
        for fault_type, fn in ALL_FAULT_SCENARIOS.items():
            result = fn()
            assert isinstance(result, FaultScenarioResult)
            assert result.fault_type == fault_type

    def test_all_pass_deterministically(self):
        for fault_type, fn in ALL_FAULT_SCENARIOS.items():
            result = fn()
            assert result.all_passed, (
                f'{fault_type.value} failed: '
                + ', '.join(a.message for a in result.assertions if not a.passed)
            )


# ── FaultInjectionRunner ──


class TestFaultInjectionRunner:

    def test_run_single(self):
        runner = FaultInjectionRunner()
        result = runner.run_scenario(FaultType.SERVICE_503)
        assert result.all_passed
        assert len(runner.results) == 1

    def test_run_all(self):
        runner = FaultInjectionRunner()
        runner.run_all()
        assert len(runner.results) == len(ALL_FAULT_SCENARIOS)

    def test_all_passed(self):
        runner = FaultInjectionRunner()
        runner.run_all()
        assert runner.all_passed

    def test_total_assertions(self):
        runner = FaultInjectionRunner()
        runner.run_all()
        assert runner.total_assertions > 0

    def test_total_failures_zero(self):
        runner = FaultInjectionRunner()
        runner.run_all()
        assert runner.total_failures == 0

    def test_logger_records(self):
        test_logger = StructuredTestLogger()
        runner = FaultInjectionRunner(logger=test_logger)
        runner.run_scenario(FaultType.SERVICE_503)
        assert test_logger.count == 1

    def test_timeline_records(self):
        timeline = EventTimeline()
        runner = FaultInjectionRunner(timeline=timeline)
        runner.run_scenario(FaultType.SERVICE_503)
        assert timeline.count == 1

    def test_summary(self):
        runner = FaultInjectionRunner()
        runner.run_all()
        summary = runner.summary()
        assert summary['total_scenarios'] == len(ALL_FAULT_SCENARIOS)
        assert summary['all_passed'] is True
        assert summary['total_failures'] == 0

    def test_summary_serializable(self):
        runner = FaultInjectionRunner()
        runner.run_all()
        json.dumps(runner.summary())

    def test_logger_property(self):
        test_logger = StructuredTestLogger()
        runner = FaultInjectionRunner(logger=test_logger)
        assert runner.logger is test_logger

    def test_timeline_property(self):
        timeline = EventTimeline()
        runner = FaultInjectionRunner(timeline=timeline)
        assert runner.timeline is timeline


# ── Enum coverage ──


class TestEnums:

    def test_fault_types(self):
        assert FaultType.SERVICE_503.value == 'service_503'
        assert FaultType.EXEC_ATTACH_FAIL.value == 'exec_attach_fail'
        assert FaultType.WS_MIDSTREAM_DISCONNECT.value == 'ws_midstream_disconnect'
        assert FaultType.RATE_LIMIT_BURST.value == 'rate_limit_burst'
        assert FaultType.AUTH_EXPIRY.value == 'auth_expiry'
        assert FaultType.PROVIDER_TIMEOUT_CASCADE.value == 'provider_timeout_cascade'
        assert FaultType.HEALTH_FLAP_ACTIVE.value == 'health_flap_active'

    def test_assertion_outcomes(self):
        assert AssertionOutcome.PASS.value == 'pass'
        assert AssertionOutcome.FAIL.value == 'fail'
