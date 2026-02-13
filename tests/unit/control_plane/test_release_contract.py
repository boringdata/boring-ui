"""Tests for release selection and sandbox naming contract.

Bead: bd-223o.10.1.1 (D1a)

Validates:
  - ReleaseUnavailableError when no release_id is resolvable
  - ReleaseUnavailableError when artifacts are not found
  - Requested release_id takes precedence over default
  - Default release_id used when no explicit request
  - Deterministic sandbox naming: sbx-{app_id}-{workspace_id}-{env}
  - Sandbox token normalization (lowercase, slug-safe, stripped)
  - ValueError on empty/invalid sandbox tokens
  - ProvisioningTarget immutability
  - Error payload structure for release_unavailable
"""

from __future__ import annotations

import pytest

from control_plane.app.provisioning.release_contract import (
    RELEASE_UNAVAILABLE_CODE,
    SANDBOX_PREFIX,
    ProvisioningTarget,
    ReleaseUnavailableError,
    build_sandbox_name,
    normalize_sandbox_token,
    release_unavailable_payload,
    resolve_provisioning_target,
)


# ── Helpers ──────────────────────────────────────────────────────────


class _FakeArtifactLookup:
    """Test artifact lookup that returns a checksum for known releases."""

    def __init__(self, known: dict[tuple[str, str], str] | None = None):
        self._known = known or {}

    def bundle_sha256(self, app_id: str, release_id: str) -> str | None:
        return self._known.get((app_id, release_id))


def _make_lookup(**artifacts: str) -> _FakeArtifactLookup:
    """Shorthand: _make_lookup(boring_ui_v1='sha256:abc') →
    {('boring-ui', 'v1'): 'sha256:abc'}."""
    known = {}
    for key, sha in artifacts.items():
        parts = key.rsplit('_', 1)
        if len(parts) == 2:
            known[(parts[0].replace('_', '-'), parts[1])] = sha
    return _FakeArtifactLookup(known)


# =====================================================================
# 1. Release resolution — unavailable scenarios
# =====================================================================


class TestReleaseUnavailable:

    def test_no_release_id_at_all(self):
        """Neither requested nor default release_id → error."""
        lookup = _FakeArtifactLookup()
        with pytest.raises(ReleaseUnavailableError) as exc_info:
            resolve_provisioning_target(
                app_id='boring-ui',
                workspace_id='ws_1',
                env='production',
                requested_release_id=None,
                default_release_id=None,
                artifact_lookup=lookup,
            )
        assert exc_info.value.reason == 'no_release_available'
        assert exc_info.value.code == RELEASE_UNAVAILABLE_CODE

    def test_empty_string_release_ids(self):
        """Empty strings are treated as missing."""
        lookup = _FakeArtifactLookup()
        with pytest.raises(ReleaseUnavailableError) as exc_info:
            resolve_provisioning_target(
                app_id='boring-ui',
                workspace_id='ws_1',
                env='prod',
                requested_release_id='',
                default_release_id='',
                artifact_lookup=lookup,
            )
        assert exc_info.value.reason == 'no_release_available'

    def test_whitespace_only_release_ids(self):
        """Whitespace-only strings treated as missing."""
        lookup = _FakeArtifactLookup()
        with pytest.raises(ReleaseUnavailableError):
            resolve_provisioning_target(
                app_id='boring-ui',
                workspace_id='ws_1',
                env='prod',
                requested_release_id='   ',
                default_release_id='  \t ',
                artifact_lookup=lookup,
            )

    def test_artifacts_not_found_for_resolved_release(self):
        """Release resolves but artifacts are missing → error."""
        lookup = _FakeArtifactLookup()  # Empty — nothing found.
        with pytest.raises(ReleaseUnavailableError) as exc_info:
            resolve_provisioning_target(
                app_id='boring-ui',
                workspace_id='ws_1',
                env='prod',
                requested_release_id='v99',
                default_release_id=None,
                artifact_lookup=lookup,
            )
        assert exc_info.value.reason == 'artifacts_not_found'
        assert exc_info.value.release_id == 'v99'

    def test_default_release_artifacts_not_found(self):
        """Default release resolves but artifacts missing."""
        lookup = _FakeArtifactLookup()
        with pytest.raises(ReleaseUnavailableError) as exc_info:
            resolve_provisioning_target(
                app_id='boring-ui',
                workspace_id='ws_1',
                env='prod',
                requested_release_id=None,
                default_release_id='v1-missing',
                artifact_lookup=lookup,
            )
        assert exc_info.value.reason == 'artifacts_not_found'
        assert exc_info.value.release_id == 'v1-missing'


# =====================================================================
# 2. Release resolution — success scenarios
# =====================================================================


class TestReleaseResolution:

    def test_requested_release_id_used(self):
        lookup = _FakeArtifactLookup({
            ('boring-ui', 'v2'): 'sha256:requested',
        })
        target = resolve_provisioning_target(
            app_id='boring-ui',
            workspace_id='ws_1',
            env='prod',
            requested_release_id='v2',
            default_release_id='v1',
            artifact_lookup=lookup,
        )
        assert target.release_id == 'v2'
        assert target.bundle_sha256 == 'sha256:requested'

    def test_default_release_id_fallback(self):
        lookup = _FakeArtifactLookup({
            ('boring-ui', 'v1'): 'sha256:default',
        })
        target = resolve_provisioning_target(
            app_id='boring-ui',
            workspace_id='ws_1',
            env='prod',
            requested_release_id=None,
            default_release_id='v1',
            artifact_lookup=lookup,
        )
        assert target.release_id == 'v1'
        assert target.bundle_sha256 == 'sha256:default'

    def test_requested_takes_precedence_over_default(self):
        lookup = _FakeArtifactLookup({
            ('boring-ui', 'v2'): 'sha256:v2',
            ('boring-ui', 'v1'): 'sha256:v1',
        })
        target = resolve_provisioning_target(
            app_id='boring-ui',
            workspace_id='ws_1',
            env='prod',
            requested_release_id='v2',
            default_release_id='v1',
            artifact_lookup=lookup,
        )
        assert target.release_id == 'v2'


# =====================================================================
# 3. Sandbox naming
# =====================================================================


class TestSandboxNaming:

    def test_deterministic_name_format(self):
        name = build_sandbox_name(
            app_id='boring-ui', workspace_id='ws-123', env='prod',
        )
        assert name == 'sbx-boring-ui-ws-123-prod'

    def test_starts_with_prefix(self):
        name = build_sandbox_name(
            app_id='app', workspace_id='ws', env='dev',
        )
        assert name.startswith(f'{SANDBOX_PREFIX}-')

    def test_uppercase_normalized(self):
        name = build_sandbox_name(
            app_id='BORING-UI', workspace_id='WS_123', env='PROD',
        )
        assert name == name.lower()

    def test_special_chars_sanitized(self):
        name = build_sandbox_name(
            app_id='boring.ui@v2', workspace_id='ws#123', env='staging!',
        )
        # Should only contain lowercase alphanumeric and dashes.
        assert all(c.isalnum() or c == '-' for c in name)

    def test_same_inputs_same_output(self):
        """Deterministic: same inputs always produce same name."""
        args = dict(app_id='boring-ui', workspace_id='ws_1', env='prod')
        assert build_sandbox_name(**args) == build_sandbox_name(**args)

    def test_different_workspace_different_name(self):
        n1 = build_sandbox_name(
            app_id='boring-ui', workspace_id='ws_1', env='prod',
        )
        n2 = build_sandbox_name(
            app_id='boring-ui', workspace_id='ws_2', env='prod',
        )
        assert n1 != n2

    def test_different_env_different_name(self):
        n1 = build_sandbox_name(
            app_id='boring-ui', workspace_id='ws_1', env='prod',
        )
        n2 = build_sandbox_name(
            app_id='boring-ui', workspace_id='ws_1', env='staging',
        )
        assert n1 != n2


# =====================================================================
# 4. Token normalization edge cases
# =====================================================================


class TestTokenNormalization:

    def test_simple_slug(self):
        assert normalize_sandbox_token('boring-ui', label='app_id') == 'boring-ui'

    def test_uppercase_lowered(self):
        assert normalize_sandbox_token('BORING-UI', label='app_id') == 'boring-ui'

    def test_whitespace_stripped(self):
        assert normalize_sandbox_token('  boring-ui  ', label='app_id') == 'boring-ui'

    def test_special_chars_to_dashes(self):
        result = normalize_sandbox_token('boring.ui@v2', label='app_id')
        assert result == 'boring-ui-v2'

    def test_consecutive_dashes_squashed(self):
        result = normalize_sandbox_token('boring---ui', label='app_id')
        assert result == 'boring-ui'

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match='app_id'):
            normalize_sandbox_token('', label='app_id')

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match='env'):
            normalize_sandbox_token('   ', label='env')

    def test_special_chars_only_raises(self):
        with pytest.raises(ValueError, match='workspace_id'):
            normalize_sandbox_token('!!!', label='workspace_id')


# =====================================================================
# 5. ProvisioningTarget immutability
# =====================================================================


class TestProvisioningTarget:

    def test_frozen_dataclass(self):
        target = ProvisioningTarget(
            app_id='boring-ui',
            workspace_id='ws_1',
            release_id='v1',
            sandbox_name='sbx-boring-ui-ws-1-prod',
            bundle_sha256='sha256:abc',
        )
        with pytest.raises(AttributeError):
            target.release_id = 'v2'

    def test_all_fields_accessible(self):
        target = ProvisioningTarget(
            app_id='boring-ui',
            workspace_id='ws_1',
            release_id='v1',
            sandbox_name='sbx-boring-ui-ws-1-prod',
            bundle_sha256='sha256:abc',
        )
        assert target.app_id == 'boring-ui'
        assert target.workspace_id == 'ws_1'
        assert target.release_id == 'v1'
        assert target.sandbox_name == 'sbx-boring-ui-ws-1-prod'
        assert target.bundle_sha256 == 'sha256:abc'


# =====================================================================
# 6. Error payload structure
# =====================================================================


class TestErrorPayload:

    def test_payload_includes_error_code(self):
        err = ReleaseUnavailableError('boring-ui', 'v1', 'not_found')
        payload = release_unavailable_payload(err)
        assert payload['error'] == RELEASE_UNAVAILABLE_CODE
        assert payload['code'] == RELEASE_UNAVAILABLE_CODE

    def test_payload_includes_detail(self):
        err = ReleaseUnavailableError('boring-ui', 'v1', 'not_found')
        payload = release_unavailable_payload(err)
        assert 'boring-ui' in payload['detail']
        assert 'v1' in payload['detail']

    def test_error_code_property(self):
        err = ReleaseUnavailableError('a', 'b', 'c')
        assert err.code == RELEASE_UNAVAILABLE_CODE

    def test_error_attributes(self):
        err = ReleaseUnavailableError('my-app', 'v3', 'checksum_missing')
        assert err.app_id == 'my-app'
        assert err.release_id == 'v3'
        assert err.reason == 'checksum_missing'
