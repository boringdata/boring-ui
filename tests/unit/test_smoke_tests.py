"""Unit tests for credential-gated live smoke test runner."""
from pathlib import Path

import pytest

from boring_ui.api.smoke_tests import (
    CredentialGate,
    GateStatus,
    SmokeCategory,
    SmokeOutcome,
    SmokeStep,
    SmokeTestRunner,
)


def test_credential_gate_status():
    assert CredentialGate().status == GateStatus.MISSING
    assert CredentialGate(api_token='t', base_url='https://x').status == GateStatus.AVAILABLE


def test_runner_from_env(monkeypatch):
    monkeypatch.setenv('SPRITES_API_TOKEN', 'token')
    monkeypatch.setenv('SPRITES_BASE_URL', 'https://sprites.internal')
    monkeypatch.setenv('SPRITES_SPRITE_NAME', 'sprite-a')

    runner = SmokeTestRunner.from_env()
    assert runner.gate.is_available is True
    assert runner.gate.sprite_name == 'sprite-a'


def test_execute_step_skips_when_gate_missing():
    runner = SmokeTestRunner(gate=CredentialGate())
    step = SmokeStep('health', SmokeCategory.HEALTH, 'check health')
    result = runner.execute_step(step)
    assert result.outcome == SmokeOutcome.SKIP
    assert runner.skip_count == 1


def test_execute_command_step_passes_for_success_command():
    runner = SmokeTestRunner(gate=CredentialGate(api_token='t', base_url='https://x'))
    step = SmokeStep('cmd', SmokeCategory.DEPLOY, 'run command')
    result = runner.execute_command_step(step, ['/bin/sh', '-c', 'exit 0'])
    assert result.outcome == SmokeOutcome.PASS
    assert runner.pass_count == 1


def test_execute_command_step_fails_for_nonzero_command():
    runner = SmokeTestRunner(gate=CredentialGate(api_token='t', base_url='https://x'))
    step = SmokeStep('cmd_fail', SmokeCategory.DEPLOY, 'run command')
    result = runner.execute_command_step(step, ['/bin/sh', '-c', 'echo boom >&2; exit 5'])
    assert result.outcome == SmokeOutcome.FAIL
    assert result.response_status == 5
    assert runner.fail_count == 1


def test_save_artifact_bundle_writes_manifest_and_outputs(tmp_path):
    runner = SmokeTestRunner(gate=CredentialGate(api_token='t', base_url='https://x'))
    step = SmokeStep('deploy', SmokeCategory.DEPLOY, 'mock deploy')
    runner.execute_step(step, outcome=SmokeOutcome.PASS)

    manifest = runner.save_artifact_bundle(tmp_path, run_id='run-1')
    manifest_path = Path(tmp_path) / 'sandbox-test' / 'live-smoke' / 'run-1.manifest.json'
    log_path = Path(tmp_path) / 'sandbox-test' / 'live-smoke' / 'run-1.jsonl'
    timeline_path = Path(tmp_path) / 'sandbox-test' / 'live-smoke' / 'run-1.timeline.json'
    summary_path = Path(tmp_path) / 'sandbox-test' / 'live-smoke' / 'run-1.summary.json'

    assert manifest_path.exists()
    assert log_path.exists()
    assert timeline_path.exists()
    assert summary_path.exists()
    assert manifest.summary['passed'] == 1
    assert manifest.summary['failed'] == 0

