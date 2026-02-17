"""Release selection + sandbox naming contract for workspace provisioning.

Bead: bd-223o.10.1 (D1)

Implements design-doc section 8.4 and 8.5 requirements:
  - Resolve immutable ``release_id`` for create/retry.
  - Block provisioning when release artifacts are unavailable.
  - Compute deterministic sandbox names using:
    ``sbx-{app_id}-{workspace_id}-{env}``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

RELEASE_UNAVAILABLE_CODE = 'release_unavailable'
SANDBOX_PREFIX = 'sbx'
_TOKEN_SANITIZE_RE = re.compile(r'[^a-z0-9-]+')
_DASH_RUN_RE = re.compile(r'-{2,}')


class ReleaseArtifactLookup(Protocol):
    """Artifact lookup abstraction used by create/retry orchestration."""

    def bundle_sha256(self, app_id: str, release_id: str) -> str | None:
        """Return bundle checksum for ``{app_id, release_id}`` or ``None``."""


@dataclass(frozen=True, slots=True)
class ProvisioningTarget:
    """Resolved immutable deployment selectors for a provisioning attempt."""

    app_id: str
    workspace_id: str
    release_id: str
    sandbox_name: str
    bundle_sha256: str


class ReleaseUnavailableError(RuntimeError):
    """Raised when release metadata cannot be resolved for provisioning."""

    def __init__(self, app_id: str, release_id: str, reason: str) -> None:
        self.app_id = app_id
        self.release_id = release_id
        self.reason = reason
        super().__init__(
            f'{RELEASE_UNAVAILABLE_CODE}: app_id={app_id!r} '
            f'release_id={release_id!r} reason={reason}'
        )

    @property
    def code(self) -> str:
        return RELEASE_UNAVAILABLE_CODE


def release_unavailable_payload(error: ReleaseUnavailableError) -> dict[str, str]:
    """Build canonical API error payload for unavailable release artifacts."""
    return {
        'error': RELEASE_UNAVAILABLE_CODE,
        'code': RELEASE_UNAVAILABLE_CODE,
        'detail': (
            f'release artifacts unavailable for app_id={error.app_id!r} '
            f'release_id={error.release_id!r}'
        ),
    }


def resolve_provisioning_target(
    *,
    app_id: str,
    workspace_id: str,
    env: str,
    requested_release_id: str | None,
    default_release_id: str | None,
    artifact_lookup: ReleaseArtifactLookup,
) -> ProvisioningTarget:
    """Resolve immutable release + sandbox selectors for create/retry.

    Raises:
        ReleaseUnavailableError: If no release can be resolved or artifacts
            for the resolved release are unavailable.
        ValueError: If sandbox token normalization produces empty values.
    """
    release_id = _resolve_release_id(
        app_id=app_id,
        requested_release_id=requested_release_id,
        default_release_id=default_release_id,
    )
    bundle_sha256 = artifact_lookup.bundle_sha256(app_id, release_id)
    if not bundle_sha256:
        raise ReleaseUnavailableError(
            app_id=app_id,
            release_id=release_id,
            reason='artifacts_not_found',
        )

    sandbox_name = build_sandbox_name(
        app_id=app_id,
        workspace_id=workspace_id,
        env=env,
    )

    return ProvisioningTarget(
        app_id=app_id,
        workspace_id=workspace_id,
        release_id=release_id,
        sandbox_name=sandbox_name,
        bundle_sha256=bundle_sha256,
    )


def build_sandbox_name(*, app_id: str, workspace_id: str, env: str) -> str:
    """Compute deterministic Sprite sandbox name for runtime identity."""
    app_token = normalize_sandbox_token(app_id, label='app_id')
    workspace_token = normalize_sandbox_token(
        workspace_id,
        label='workspace_id',
    )
    env_token = normalize_sandbox_token(env, label='env')
    return (
        f'{SANDBOX_PREFIX}-{app_token}-{workspace_token}-{env_token}'
    )


def normalize_sandbox_token(raw: str, *, label: str) -> str:
    """Normalize user/config IDs into stable slug-safe sandbox tokens."""
    lowered = raw.strip().lower()
    replaced = _TOKEN_SANITIZE_RE.sub('-', lowered)
    squashed = _DASH_RUN_RE.sub('-', replaced).strip('-')
    if not squashed:
        raise ValueError(f'{label} must contain at least one slug-safe token')
    return squashed


def _resolve_release_id(
    *,
    app_id: str,
    requested_release_id: str | None,
    default_release_id: str | None,
) -> str:
    """Resolve immutable release ID from request override or app default."""
    requested = (requested_release_id or '').strip()
    if requested:
        return requested

    default = (default_release_id or '').strip()
    if default:
        return default

    raise ReleaseUnavailableError(
        app_id=app_id,
        release_id='',
        reason='no_release_available',
    )
