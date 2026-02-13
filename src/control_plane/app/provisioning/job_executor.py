"""Provisioning job executor: drives state machine through deploy steps.

Bead: bd-223o.10.4 (D4)

Orchestrates the deploy-only flow for a provisioning job:
  queued -> release_resolve -> creating_sandbox -> uploading_artifact
  -> bootstrapping -> health_check -> ready

At each step the executor:
  1. Advances the state machine.
  2. Performs the step action via injected providers.
  3. Verifies checksums where applicable.
  4. Transitions to error on failure with actionable codes.
  5. Persists runtime metadata on success.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from .release_contract import ProvisioningTarget
from .state_machine import (
    ARTIFACT_CHECKSUM_MISMATCH_CODE,
    ProvisioningJobState,
    advance_state,
    create_queued_job,
    transition_to_checksum_mismatch,
    transition_to_error,
)


# ── Provider protocols ───────────────────────────────────────────────


class SandboxProvider(Protocol):
    """Create and manage runtime sandboxes."""

    async def create_sandbox(self, sandbox_name: str) -> str:
        """Create a sandbox and return its identifier."""
        ...

    async def upload_artifact(
        self, sandbox_name: str, bundle_path: Path, bundle_sha256: str,
    ) -> None:
        """Upload and extract the release bundle into the sandbox."""
        ...

    async def bootstrap(self, sandbox_name: str) -> None:
        """Run bootstrap commands in the sandbox."""
        ...

    async def health_check(self, sandbox_name: str) -> bool:
        """Return True if the sandbox is healthy and ready to serve."""
        ...


class ArtifactVerifier(Protocol):
    """Verify artifact integrity before upload."""

    def verify_bundle(self, app_id: str, release_id: str) -> bool:
        """Return True if bundle checksum matches manifest."""
        ...

    def bundle_path(self, app_id: str, release_id: str) -> Path | None:
        """Return path to the bundle file."""
        ...


class RuntimeMetadataStore(Protocol):
    """Persist runtime deployment metadata."""

    async def upsert_runtime(
        self,
        *,
        workspace_id: str,
        app_id: str,
        state: str,
        step: str | None,
        attempt: int,
        release_id: str,
        sandbox_name: str,
        bundle_sha256: str,
        last_error_code: str | None,
        last_error_detail: str | None,
    ) -> None:
        """Create or update runtime row for a workspace."""
        ...


# ── In-memory implementations (testing) ──────────────────────────────


class InMemorySandboxProvider:
    """Test sandbox provider that tracks calls."""

    def __init__(
        self,
        *,
        create_fails: bool = False,
        upload_fails: bool = False,
        bootstrap_fails: bool = False,
        health_check_fails: bool = False,
    ) -> None:
        self.create_fails = create_fails
        self.upload_fails = upload_fails
        self.bootstrap_fails = bootstrap_fails
        self.health_check_fails = health_check_fails
        self.calls: list[tuple[str, str]] = []

    async def create_sandbox(self, sandbox_name: str) -> str:
        self.calls.append(('create_sandbox', sandbox_name))
        if self.create_fails:
            raise RuntimeError('sandbox creation failed')
        return sandbox_name

    async def upload_artifact(
        self, sandbox_name: str, bundle_path: Path, bundle_sha256: str,
    ) -> None:
        self.calls.append(('upload_artifact', sandbox_name))
        if self.upload_fails:
            raise RuntimeError('artifact upload failed')

    async def bootstrap(self, sandbox_name: str) -> None:
        self.calls.append(('bootstrap', sandbox_name))
        if self.bootstrap_fails:
            raise RuntimeError('bootstrap failed')

    async def health_check(self, sandbox_name: str) -> bool:
        self.calls.append(('health_check', sandbox_name))
        return not self.health_check_fails


class InMemoryRuntimeMetadataStore:
    """Test runtime metadata store."""

    def __init__(self) -> None:
        self.runtimes: dict[str, dict] = {}

    async def upsert_runtime(
        self,
        *,
        workspace_id: str,
        app_id: str,
        state: str,
        step: str | None,
        attempt: int,
        release_id: str,
        sandbox_name: str,
        bundle_sha256: str,
        last_error_code: str | None,
        last_error_detail: str | None,
    ) -> None:
        self.runtimes[workspace_id] = {
            'workspace_id': workspace_id,
            'app_id': app_id,
            'state': state,
            'step': step,
            'attempt': attempt,
            'release_id': release_id,
            'sandbox_name': sandbox_name,
            'bundle_sha256': bundle_sha256,
            'last_error_code': last_error_code,
            'last_error_detail': last_error_detail,
        }


class InMemoryArtifactVerifier:
    """Test artifact verifier."""

    def __init__(
        self,
        *,
        valid: bool = True,
        bundle_file: Path | None = None,
    ) -> None:
        self._valid = valid
        self._bundle_file = bundle_file

    def verify_bundle(self, app_id: str, release_id: str) -> bool:
        return self._valid

    def bundle_path(self, app_id: str, release_id: str) -> Path | None:
        return self._bundle_file


# ── Execution result ─────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Outcome of a provisioning job execution attempt."""

    job: ProvisioningJobState
    success: bool
    error_code: str | None = None
    error_detail: str | None = None


# ── Executor ─────────────────────────────────────────────────────────


class ProvisioningJobExecutor:
    """Drives a provisioning job through the state machine steps.

    Each step is executed via injected providers, with checksum
    verification between artifact fetch and upload. On any failure
    the job transitions to ``error`` with an actionable code.

    Runtime metadata is persisted after reaching ``ready`` or ``error``.
    """

    def __init__(
        self,
        *,
        sandbox_provider: SandboxProvider,
        artifact_verifier: ArtifactVerifier,
        runtime_store: RuntimeMetadataStore,
    ) -> None:
        self._sandbox = sandbox_provider
        self._artifacts = artifact_verifier
        self._runtime = runtime_store

    async def execute(
        self,
        *,
        target: ProvisioningTarget,
    ) -> ExecutionResult:
        """Execute the full provisioning flow for a resolved target.

        Returns an ExecutionResult with the final job state.
        """
        now = datetime.now(timezone.utc)
        job = create_queued_job(
            workspace_id=target.workspace_id,
            now=now,
        )

        # Step 1: queued -> release_resolve
        job = advance_state(job, now=_now())
        # Verify artifact integrity.
        if not self._artifacts.verify_bundle(target.app_id, target.release_id):
            job = transition_to_checksum_mismatch(
                job,
                now=_now(),
                expected_sha256=target.bundle_sha256,
                actual_sha256='<verification_failed>',
            )
            await self._persist_runtime(target, job, 'error')
            return ExecutionResult(
                job=job,
                success=False,
                error_code=ARTIFACT_CHECKSUM_MISMATCH_CODE,
                error_detail=job.last_error_detail,
            )

        bundle_file = self._artifacts.bundle_path(
            target.app_id, target.release_id,
        )
        if bundle_file is None:
            job = transition_to_error(
                job,
                now=_now(),
                error_code='artifact_not_found',
                error_detail=(
                    f'bundle file missing for {target.app_id}/{target.release_id}'
                ),
            )
            await self._persist_runtime(target, job, 'error')
            return ExecutionResult(
                job=job,
                success=False,
                error_code='artifact_not_found',
                error_detail=job.last_error_detail,
            )

        # Step 2: release_resolve -> creating_sandbox
        job = advance_state(job, now=_now())
        try:
            await self._sandbox.create_sandbox(target.sandbox_name)
        except Exception as exc:
            job = transition_to_error(
                job,
                now=_now(),
                error_code='sandbox_creation_failed',
                error_detail=str(exc),
            )
            await self._persist_runtime(target, job, 'error')
            return ExecutionResult(
                job=job,
                success=False,
                error_code='sandbox_creation_failed',
                error_detail=str(exc),
            )

        # Step 3: creating_sandbox -> uploading_artifact
        job = advance_state(job, now=_now())
        try:
            await self._sandbox.upload_artifact(
                target.sandbox_name,
                bundle_file,
                target.bundle_sha256,
            )
        except Exception as exc:
            job = transition_to_error(
                job,
                now=_now(),
                error_code='artifact_upload_failed',
                error_detail=str(exc),
            )
            await self._persist_runtime(target, job, 'error')
            return ExecutionResult(
                job=job,
                success=False,
                error_code='artifact_upload_failed',
                error_detail=str(exc),
            )

        # Step 4: uploading_artifact -> bootstrapping
        job = advance_state(job, now=_now())
        try:
            await self._sandbox.bootstrap(target.sandbox_name)
        except Exception as exc:
            job = transition_to_error(
                job,
                now=_now(),
                error_code='bootstrap_failed',
                error_detail=str(exc),
            )
            await self._persist_runtime(target, job, 'error')
            return ExecutionResult(
                job=job,
                success=False,
                error_code='bootstrap_failed',
                error_detail=str(exc),
            )

        # Step 5: bootstrapping -> health_check
        job = advance_state(job, now=_now())
        try:
            healthy = await self._sandbox.health_check(target.sandbox_name)
        except Exception as exc:
            job = transition_to_error(
                job,
                now=_now(),
                error_code='health_check_failed',
                error_detail=str(exc),
            )
            await self._persist_runtime(target, job, 'error')
            return ExecutionResult(
                job=job,
                success=False,
                error_code='health_check_failed',
                error_detail=str(exc),
            )

        if not healthy:
            job = transition_to_error(
                job,
                now=_now(),
                error_code='health_check_failed',
                error_detail='sandbox health check returned unhealthy',
            )
            await self._persist_runtime(target, job, 'error')
            return ExecutionResult(
                job=job,
                success=False,
                error_code='health_check_failed',
                error_detail='sandbox health check returned unhealthy',
            )

        # Step 6: health_check -> ready
        job = advance_state(job, now=_now())
        await self._persist_runtime(target, job, 'ready')
        return ExecutionResult(job=job, success=True)

    async def _persist_runtime(
        self,
        target: ProvisioningTarget,
        job: ProvisioningJobState,
        runtime_state: str,
    ) -> None:
        """Write runtime metadata after terminal state."""
        await self._runtime.upsert_runtime(
            workspace_id=target.workspace_id,
            app_id=target.app_id,
            state=runtime_state,
            step=job.state if job.state != 'ready' else None,
            attempt=job.attempt,
            release_id=target.release_id,
            sandbox_name=target.sandbox_name,
            bundle_sha256=target.bundle_sha256,
            last_error_code=job.last_error_code,
            last_error_detail=job.last_error_detail,
        )


def _now() -> datetime:
    """UTC-aware now for state transitions."""
    return datetime.now(timezone.utc)
