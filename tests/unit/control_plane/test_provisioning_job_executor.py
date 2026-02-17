"""Provisioning job executor tests: deploy flow + checksum verification.

Bead: bd-223o.10.4 (D4)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from control_plane.app.provisioning.job_executor import (
    ExecutionResult,
    InMemoryArtifactVerifier,
    InMemoryRuntimeMetadataStore,
    InMemorySandboxProvider,
    ProvisioningJobExecutor,
)
from control_plane.app.provisioning.release_contract import ProvisioningTarget


def _make_target(
    *,
    workspace_id: str = 'ws_test',
    app_id: str = 'boring-ui',
    release_id: str = 'rel-001',
    sandbox_name: str = 'sbx-boring-ui-ws-test-dev',
    bundle_sha256: str = 'abc123def456',
) -> ProvisioningTarget:
    return ProvisioningTarget(
        app_id=app_id,
        workspace_id=workspace_id,
        release_id=release_id,
        sandbox_name=sandbox_name,
        bundle_sha256=bundle_sha256,
    )


def _make_executor(
    *,
    sandbox: InMemorySandboxProvider | None = None,
    verifier: InMemoryArtifactVerifier | None = None,
    runtime: InMemoryRuntimeMetadataStore | None = None,
) -> tuple[
    ProvisioningJobExecutor,
    InMemorySandboxProvider,
    InMemoryArtifactVerifier,
    InMemoryRuntimeMetadataStore,
]:
    sandbox = sandbox or InMemorySandboxProvider()
    verifier = verifier or InMemoryArtifactVerifier(
        bundle_file=Path('/tmp/test-bundle.tar.gz'),
    )
    runtime = runtime or InMemoryRuntimeMetadataStore()
    executor = ProvisioningJobExecutor(
        sandbox_provider=sandbox,
        artifact_verifier=verifier,
        runtime_store=runtime,
    )
    return executor, sandbox, verifier, runtime


# ── Happy path ───────────────────────────────────────────────────────


class TestHappyPath:
    @pytest.mark.asyncio
    async def test_executes_all_steps_to_ready(self):
        executor, sandbox, _, runtime = _make_executor()
        target = _make_target()

        result = await executor.execute(target=target)

        assert result.success is True
        assert result.job.state == 'ready'
        assert result.error_code is None
        assert result.error_detail is None

    @pytest.mark.asyncio
    async def test_calls_all_sandbox_methods(self):
        executor, sandbox, _, _ = _make_executor()
        target = _make_target()

        await executor.execute(target=target)

        call_methods = [c[0] for c in sandbox.calls]
        assert call_methods == [
            'create_sandbox',
            'upload_artifact',
            'bootstrap',
            'health_check',
        ]

    @pytest.mark.asyncio
    async def test_passes_correct_sandbox_name(self):
        executor, sandbox, _, _ = _make_executor()
        target = _make_target(sandbox_name='sbx-my-app-ws1-prod')

        await executor.execute(target=target)

        for _, name in sandbox.calls:
            assert name == 'sbx-my-app-ws1-prod'

    @pytest.mark.asyncio
    async def test_persists_runtime_on_ready(self):
        executor, _, _, runtime = _make_executor()
        target = _make_target()

        await executor.execute(target=target)

        rt = runtime.runtimes['ws_test']
        assert rt['state'] == 'ready'
        assert rt['release_id'] == 'rel-001'
        assert rt['sandbox_name'] == 'sbx-boring-ui-ws-test-dev'
        assert rt['bundle_sha256'] == 'abc123def456'
        assert rt['last_error_code'] is None

    @pytest.mark.asyncio
    async def test_final_job_is_ready_with_finished_at(self):
        executor, _, _, _ = _make_executor()
        result = await executor.execute(target=_make_target())
        assert result.job.state == 'ready'
        assert result.job.finished_at is not None


# ── Checksum verification failure ────────────────────────────────────


class TestChecksumFailure:
    @pytest.mark.asyncio
    async def test_checksum_mismatch_returns_error(self):
        verifier = InMemoryArtifactVerifier(valid=False)
        executor, _, _, _ = _make_executor(verifier=verifier)

        result = await executor.execute(target=_make_target())

        assert result.success is False
        assert result.error_code == 'ARTIFACT_CHECKSUM_MISMATCH'
        assert result.job.state == 'error'

    @pytest.mark.asyncio
    async def test_checksum_mismatch_persists_error_runtime(self):
        verifier = InMemoryArtifactVerifier(valid=False)
        executor, _, _, runtime = _make_executor(verifier=verifier)

        await executor.execute(target=_make_target())

        rt = runtime.runtimes['ws_test']
        assert rt['state'] == 'error'
        assert rt['last_error_code'] == 'ARTIFACT_CHECKSUM_MISMATCH'

    @pytest.mark.asyncio
    async def test_no_sandbox_calls_on_checksum_failure(self):
        verifier = InMemoryArtifactVerifier(valid=False)
        executor, sandbox, _, _ = _make_executor(verifier=verifier)

        await executor.execute(target=_make_target())

        assert len(sandbox.calls) == 0


# ── Missing bundle file ──────────────────────────────────────────────


class TestMissingBundle:
    @pytest.mark.asyncio
    async def test_missing_bundle_returns_error(self):
        verifier = InMemoryArtifactVerifier(bundle_file=None)
        executor, _, _, _ = _make_executor(verifier=verifier)

        result = await executor.execute(target=_make_target())

        assert result.success is False
        assert result.error_code == 'artifact_not_found'
        assert result.job.state == 'error'


# ── Sandbox creation failure ─────────────────────────────────────────


class TestSandboxCreationFailure:
    @pytest.mark.asyncio
    async def test_sandbox_create_failure(self):
        sandbox = InMemorySandboxProvider(create_fails=True)
        executor, _, _, _ = _make_executor(sandbox=sandbox)

        result = await executor.execute(target=_make_target())

        assert result.success is False
        assert result.error_code == 'sandbox_creation_failed'
        assert result.job.state == 'error'

    @pytest.mark.asyncio
    async def test_no_upload_on_create_failure(self):
        sandbox = InMemorySandboxProvider(create_fails=True)
        executor, _, _, _ = _make_executor(sandbox=sandbox)

        await executor.execute(target=_make_target())

        call_methods = [c[0] for c in sandbox.calls]
        assert 'upload_artifact' not in call_methods


# ── Upload failure ───────────────────────────────────────────────────


class TestUploadFailure:
    @pytest.mark.asyncio
    async def test_upload_failure(self):
        sandbox = InMemorySandboxProvider(upload_fails=True)
        executor, _, _, _ = _make_executor(sandbox=sandbox)

        result = await executor.execute(target=_make_target())

        assert result.success is False
        assert result.error_code == 'artifact_upload_failed'

    @pytest.mark.asyncio
    async def test_no_bootstrap_on_upload_failure(self):
        sandbox = InMemorySandboxProvider(upload_fails=True)
        executor, _, _, _ = _make_executor(sandbox=sandbox)

        await executor.execute(target=_make_target())

        call_methods = [c[0] for c in sandbox.calls]
        assert 'bootstrap' not in call_methods


# ── Bootstrap failure ────────────────────────────────────────────────


class TestBootstrapFailure:
    @pytest.mark.asyncio
    async def test_bootstrap_failure(self):
        sandbox = InMemorySandboxProvider(bootstrap_fails=True)
        executor, _, _, _ = _make_executor(sandbox=sandbox)

        result = await executor.execute(target=_make_target())

        assert result.success is False
        assert result.error_code == 'bootstrap_failed'


# ── Health check failure ─────────────────────────────────────────────


class TestHealthCheckFailure:
    @pytest.mark.asyncio
    async def test_health_check_returns_unhealthy(self):
        sandbox = InMemorySandboxProvider(health_check_fails=True)
        executor, _, _, _ = _make_executor(sandbox=sandbox)

        result = await executor.execute(target=_make_target())

        assert result.success is False
        assert result.error_code == 'health_check_failed'
        assert result.job.state == 'error'

    @pytest.mark.asyncio
    async def test_health_check_failure_persists_error(self):
        sandbox = InMemorySandboxProvider(health_check_fails=True)
        executor, _, _, runtime = _make_executor(sandbox=sandbox)

        await executor.execute(target=_make_target())

        rt = runtime.runtimes['ws_test']
        assert rt['state'] == 'error'
        assert rt['last_error_code'] == 'health_check_failed'


# ── Runtime metadata ─────────────────────────────────────────────────


class TestRuntimeMetadata:
    @pytest.mark.asyncio
    async def test_error_persists_app_id(self):
        sandbox = InMemorySandboxProvider(create_fails=True)
        executor, _, _, runtime = _make_executor(sandbox=sandbox)
        target = _make_target(app_id='my-app')

        await executor.execute(target=target)

        rt = runtime.runtimes[target.workspace_id]
        assert rt['app_id'] == 'my-app'

    @pytest.mark.asyncio
    async def test_ready_persists_step_as_none(self):
        executor, _, _, runtime = _make_executor()
        await executor.execute(target=_make_target())

        rt = runtime.runtimes['ws_test']
        assert rt['step'] is None

    @pytest.mark.asyncio
    async def test_error_persists_current_step(self):
        sandbox = InMemorySandboxProvider(bootstrap_fails=True)
        executor, _, _, runtime = _make_executor(sandbox=sandbox)
        await executor.execute(target=_make_target())

        rt = runtime.runtimes['ws_test']
        assert rt['state'] == 'error'
        # The job transitioned to error from bootstrapping step.
        assert rt['step'] == 'error'


# ── ExecutionResult ──────────────────────────────────────────────────


class TestExecutionResult:
    @pytest.mark.asyncio
    async def test_result_is_frozen(self):
        executor, _, _, _ = _make_executor()
        result = await executor.execute(target=_make_target())
        with pytest.raises(AttributeError):
            result.success = False
