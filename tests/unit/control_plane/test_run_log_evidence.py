"""Structured run log and per-step evidence capture tests.

Bead: bd-223o.16.3.1 (K3a)

Validates:
  1. StepResult.to_dict() emits expected/observed evidence.
  2. ScenarioResult.to_run_log() produces machine-readable output.
  3. RunLog aggregation: summary, verdict, metadata, counts.
  4. RunLog.to_json() and .write() produce valid JSON.
  5. RunLog.failed_steps() filters failures across scenarios.
  6. Include_bodies flag propagation.
  7. Frozen dataclass invariants.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from control_plane.app.testing.scenario_runner import (
    ScenarioResult,
    StepOutcome,
    StepResult,
)
from control_plane.app.testing.run_log import RunLog


# ── Test fixtures ────────────────────────────────────────────────────


def _make_step(
    *,
    step: int = 1,
    method: str = "GET",
    path: str = "/api/v1/me",
    expected_status: int = 200,
    actual_status: int | None = 200,
    outcome: StepOutcome = StepOutcome.PASS,
    request_id: str = "req-001",
    duration_ms: float = 42.5,
    response_body: dict | None = None,
    error_detail: str | None = None,
    missing_fields: tuple[str, ...] = (),
) -> StepResult:
    return StepResult(
        step_number=step,
        method=method,
        path=path,
        expected_status=expected_status,
        actual_status=actual_status,
        outcome=outcome,
        request_id=request_id,
        timestamp="2026-02-13T14:00:00+00:00",
        duration_ms=duration_ms,
        response_body=response_body,
        error_detail=error_detail,
        missing_fields=missing_fields,
    )


def _make_scenario(
    *,
    scenario_id: str = "S-001",
    title: str = "Login and Session",
    steps: tuple[StepResult, ...] | None = None,
) -> ScenarioResult:
    if steps is None:
        steps = (
            _make_step(step=1, path="/api/v1/app-config"),
            _make_step(step=2, path="/auth/callback", expected_status=302, actual_status=302),
        )
    return ScenarioResult(
        scenario_id=scenario_id,
        title=title,
        step_results=steps,
        started_at="2026-02-13T14:00:00+00:00",
        finished_at="2026-02-13T14:00:01+00:00",
        total_duration_ms=1000.0,
    )


# ── StepResult.to_dict() ────────────────────────────────────────────


class TestStepResultToDict:
    """Validate per-step expected/observed evidence format."""

    def test_pass_step_has_expected_observed(self):
        step = _make_step()
        d = step.to_dict()
        assert d["expected"]["status"] == 200
        assert d["observed"]["status"] == 200
        assert d["outcome"] == "pass"

    def test_fail_step_has_error_detail(self):
        step = _make_step(
            outcome=StepOutcome.FAIL,
            actual_status=500,
            error_detail="Expected status 200, got 500",
        )
        d = step.to_dict()
        assert d["outcome"] == "fail"
        assert d["error_detail"] == "Expected status 200, got 500"

    def test_error_step_has_null_status(self):
        step = _make_step(
            outcome=StepOutcome.ERROR,
            actual_status=None,
            error_detail="ConnectError: connection refused",
        )
        d = step.to_dict()
        assert d["observed"]["status"] is None
        assert d["outcome"] == "error"

    def test_skip_step(self):
        step = _make_step(
            outcome=StepOutcome.SKIP,
            actual_status=None,
            duration_ms=0.0,
            error_detail="Skipped due to prior failure",
        )
        d = step.to_dict()
        assert d["outcome"] == "skip"

    def test_missing_fields_in_expected_and_observed(self):
        step = _make_step(
            outcome=StepOutcome.FAIL,
            missing_fields=("app_id", "name"),
        )
        d = step.to_dict()
        assert d["expected"]["key_fields"] == ["app_id", "name"]
        assert d["observed"]["missing_fields"] == ["app_id", "name"]

    def test_no_body_by_default(self):
        step = _make_step(response_body={"user": "alice"})
        d = step.to_dict()
        assert "body" not in d.get("observed", {})

    def test_include_body_flag(self):
        step = _make_step(response_body={"user": "alice"})
        d = step.to_dict(include_body=True)
        assert d["observed"]["body"] == {"user": "alice"}

    def test_duration_rounded(self):
        step = _make_step(duration_ms=42.5678)
        d = step.to_dict()
        assert d["duration_ms"] == 42.57

    def test_request_id_present(self):
        step = _make_step(request_id="req-xyz-123")
        d = step.to_dict()
        assert d["request_id"] == "req-xyz-123"

    def test_timestamp_present(self):
        step = _make_step()
        d = step.to_dict()
        assert "timestamp" in d
        assert "2026" in d["timestamp"]


# ── ScenarioResult.to_run_log() ─────────────────────────────────────


class TestScenarioResultToRunLog:
    """Validate machine-readable scenario run log."""

    def test_verdict_pass_when_all_pass(self):
        result = _make_scenario()
        log = result.to_run_log()
        assert log["verdict"] == "pass"

    def test_verdict_fail_when_any_fails(self):
        steps = (
            _make_step(step=1, outcome=StepOutcome.PASS),
            _make_step(step=2, outcome=StepOutcome.FAIL, actual_status=500),
        )
        result = _make_scenario(steps=steps)
        log = result.to_run_log()
        assert log["verdict"] == "fail"

    def test_counts_correct(self):
        steps = (
            _make_step(step=1, outcome=StepOutcome.PASS),
            _make_step(step=2, outcome=StepOutcome.FAIL, actual_status=500),
            _make_step(step=3, outcome=StepOutcome.SKIP, actual_status=None),
        )
        result = _make_scenario(steps=steps)
        log = result.to_run_log()
        assert log["counts"]["total"] == 3
        assert log["counts"]["pass"] == 1
        assert log["counts"]["fail"] == 1
        assert log["counts"]["skip"] == 1
        assert log["counts"]["error"] == 0

    def test_steps_list_matches_count(self):
        result = _make_scenario()
        log = result.to_run_log()
        assert len(log["steps"]) == log["counts"]["total"]

    def test_scenario_id_and_title(self):
        result = _make_scenario(scenario_id="S-003", title="Workspace Switch")
        log = result.to_run_log()
        assert log["scenario_id"] == "S-003"
        assert log["title"] == "Workspace Switch"

    def test_duration_present(self):
        result = _make_scenario()
        log = result.to_run_log()
        assert log["duration_ms"] == 1000.0

    def test_timestamps_present(self):
        result = _make_scenario()
        log = result.to_run_log()
        assert "started_at" in log
        assert "finished_at" in log

    def test_include_bodies_propagated(self):
        steps = (
            _make_step(response_body={"key": "val"}),
        )
        result = _make_scenario(steps=steps)
        log_with = result.to_run_log(include_bodies=True)
        log_without = result.to_run_log(include_bodies=False)
        assert "body" in log_with["steps"][0]["observed"]
        assert "body" not in log_without["steps"][0]["observed"]


# ── RunLog aggregation ───────────────────────────────────────────────


class TestRunLogAggregation:
    """Validate multi-scenario RunLog."""

    def test_from_results_basic(self):
        s1 = _make_scenario(scenario_id="S-001")
        s2 = _make_scenario(scenario_id="S-002")
        log = RunLog.from_results([s1, s2], run_id="run-test-001")
        assert log.run_id == "run-test-001"
        assert log.scenario_count == 2

    def test_auto_generated_run_id(self):
        s1 = _make_scenario()
        log = RunLog.from_results([s1])
        assert log.run_id.startswith("run-")
        assert len(log.run_id) > 4

    def test_overall_passed_all_pass(self):
        s1 = _make_scenario()
        s2 = _make_scenario(scenario_id="S-002")
        log = RunLog.from_results([s1, s2])
        assert log.overall_passed is True

    def test_overall_failed_one_fails(self):
        s_pass = _make_scenario(scenario_id="S-001")
        s_fail = _make_scenario(
            scenario_id="S-002",
            steps=(
                _make_step(outcome=StepOutcome.FAIL, actual_status=500),
            ),
        )
        log = RunLog.from_results([s_pass, s_fail])
        assert log.overall_passed is False

    def test_total_steps(self):
        s1 = _make_scenario(scenario_id="S-001")  # 2 steps
        s2 = _make_scenario(
            scenario_id="S-002",
            steps=(_make_step(),),
        )  # 1 step
        log = RunLog.from_results([s1, s2])
        assert log.total_steps == 3

    def test_total_pass_fail_error(self):
        s1 = _make_scenario(
            scenario_id="S-001",
            steps=(
                _make_step(step=1, outcome=StepOutcome.PASS),
                _make_step(step=2, outcome=StepOutcome.FAIL, actual_status=500),
            ),
        )
        s2 = _make_scenario(
            scenario_id="S-002",
            steps=(
                _make_step(step=1, outcome=StepOutcome.ERROR, actual_status=None),
            ),
        )
        log = RunLog.from_results([s1, s2])
        assert log.total_pass == 1
        assert log.total_fail == 1
        assert log.total_error == 1

    def test_metadata_attached(self):
        s1 = _make_scenario()
        log = RunLog.from_results(
            [s1],
            metadata={"base_url": "http://localhost:8000", "auth": "token"},
        )
        assert log.metadata["base_url"] == "http://localhost:8000"
        assert log.metadata["auth"] == "token"

    def test_created_at_present(self):
        s1 = _make_scenario()
        log = RunLog.from_results([s1])
        assert "2026" in log.created_at


# ── RunLog.to_dict() and .to_json() ─────────────────────────────────


class TestRunLogSerialization:
    """Validate JSON serialization."""

    def test_to_dict_has_required_keys(self):
        s1 = _make_scenario()
        log = RunLog.from_results([s1], run_id="run-test")
        d = log.to_dict()
        assert "run_id" in d
        assert "created_at" in d
        assert "overall_passed" in d
        assert "summary" in d
        assert "metadata" in d
        assert "scenarios" in d

    def test_summary_section(self):
        s1 = _make_scenario()
        log = RunLog.from_results([s1])
        d = log.to_dict()
        summary = d["summary"]
        assert "scenarios" in summary
        assert "steps" in summary
        assert "pass" in summary
        assert "fail" in summary
        assert "error" in summary

    def test_to_json_valid(self):
        s1 = _make_scenario()
        log = RunLog.from_results([s1])
        json_str = log.to_json()
        parsed = json.loads(json_str)
        assert parsed["run_id"] == log.run_id

    def test_to_json_round_trips(self):
        s1 = _make_scenario()
        log = RunLog.from_results([s1], run_id="run-rt")
        d1 = log.to_dict()
        d2 = json.loads(log.to_json())
        assert d1 == d2


# ── RunLog.write() ───────────────────────────────────────────────────


class TestRunLogFileWrite:
    """Validate file output."""

    def test_write_creates_file(self):
        s1 = _make_scenario()
        log = RunLog.from_results([s1], run_id="run-write-test")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "evidence" / "run.json"
            log.write(path)
            assert path.exists()
            data = json.loads(path.read_text())
            assert data["run_id"] == "run-write-test"

    def test_write_creates_parent_dirs(self):
        s1 = _make_scenario()
        log = RunLog.from_results([s1])
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "deep" / "nested" / "run.json"
            log.write(path)
            assert path.exists()

    def test_write_file_is_valid_json(self):
        s1 = _make_scenario()
        s2 = _make_scenario(scenario_id="S-002")
        log = RunLog.from_results([s1, s2])
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "run.json"
            log.write(path)
            data = json.loads(path.read_text())
            assert data["summary"]["scenarios"] == 2


# ── RunLog.failed_steps() ───────────────────────────────────────────


class TestRunLogFailedSteps:
    """Validate failure filtering across scenarios."""

    def test_no_failures_returns_empty(self):
        s1 = _make_scenario()
        log = RunLog.from_results([s1])
        assert log.failed_steps() == []

    def test_single_failure_returned(self):
        s1 = _make_scenario(
            steps=(
                _make_step(step=1, outcome=StepOutcome.PASS),
                _make_step(
                    step=2,
                    outcome=StepOutcome.FAIL,
                    actual_status=500,
                    path="/api/v1/broken",
                ),
            ),
        )
        log = RunLog.from_results([s1])
        failures = log.failed_steps()
        assert len(failures) == 1
        assert failures[0]["path"] == "/api/v1/broken"
        assert failures[0]["scenario_id"] == "S-001"

    def test_errors_included_in_failures(self):
        s1 = _make_scenario(
            steps=(
                _make_step(
                    step=1,
                    outcome=StepOutcome.ERROR,
                    actual_status=None,
                    error_detail="ConnectError",
                ),
            ),
        )
        log = RunLog.from_results([s1])
        failures = log.failed_steps()
        assert len(failures) == 1
        assert failures[0]["outcome"] == "error"

    def test_skips_not_included(self):
        s1 = _make_scenario(
            steps=(
                _make_step(step=1, outcome=StepOutcome.SKIP, actual_status=None),
            ),
        )
        log = RunLog.from_results([s1])
        assert log.failed_steps() == []

    def test_failures_across_multiple_scenarios(self):
        s1 = _make_scenario(
            scenario_id="S-001",
            steps=(
                _make_step(step=1, outcome=StepOutcome.FAIL, actual_status=401),
            ),
        )
        s2 = _make_scenario(
            scenario_id="S-002",
            steps=(
                _make_step(step=1, outcome=StepOutcome.PASS),
                _make_step(step=2, outcome=StepOutcome.FAIL, actual_status=500),
            ),
        )
        log = RunLog.from_results([s1, s2])
        failures = log.failed_steps()
        assert len(failures) == 2
        scenario_ids = {f["scenario_id"] for f in failures}
        assert scenario_ids == {"S-001", "S-002"}

    def test_failure_entry_has_scenario_id(self):
        s1 = _make_scenario(
            scenario_id="S-004",
            steps=(
                _make_step(step=1, outcome=StepOutcome.FAIL, actual_status=404),
            ),
        )
        log = RunLog.from_results([s1])
        failures = log.failed_steps()
        assert failures[0]["scenario_id"] == "S-004"


# ── Frozen invariants ────────────────────────────────────────────────


class TestFrozenInvariants:
    """RunLog and its components are immutable."""

    def test_step_result_frozen(self):
        step = _make_step()
        with pytest.raises(AttributeError):
            step.outcome = StepOutcome.FAIL

    def test_scenario_result_frozen(self):
        result = _make_scenario()
        with pytest.raises((AttributeError, TypeError)):
            result.scenario_id = "mutated"

    def test_run_log_frozen(self):
        s1 = _make_scenario()
        log = RunLog.from_results([s1])
        with pytest.raises(AttributeError):
            log.run_id = "mutated"


# ── Edge cases ───────────────────────────────────────────────────────


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_scenario_list(self):
        log = RunLog.from_results([])
        assert log.scenario_count == 0
        assert log.total_steps == 0
        assert log.overall_passed is True
        assert log.failed_steps() == []

    def test_scenario_with_no_steps(self):
        result = _make_scenario(steps=())
        log = RunLog.from_results([result])
        assert log.total_steps == 0
        assert log.overall_passed is True

    def test_large_scenario_count(self):
        scenarios = [
            _make_scenario(scenario_id=f"S-{i:03d}")
            for i in range(20)
        ]
        log = RunLog.from_results(scenarios)
        assert log.scenario_count == 20
        assert log.total_steps == 40  # 2 steps each

    def test_include_bodies_default_false(self):
        s1 = _make_scenario(
            steps=(_make_step(response_body={"data": "secret"}),),
        )
        log = RunLog.from_results([s1])
        steps = log.scenarios[0]["steps"]
        assert "body" not in steps[0].get("observed", {})
