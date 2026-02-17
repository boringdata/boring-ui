"""Tests for control-plane secret configuration and validation.

Bead: bd-223o.2 (P2)

Validates:
  - ControlPlaneSecrets immutability and repr/str redaction
  - load_control_plane_secrets from env vars and explicit args
  - validate_secrets: required, optional, minimum-length checks
  - SecretValidationError structure
  - Integration: secrets wire into create_token_verifier and build_proxy_config
  - Rotation readiness: generate_sprite_bearer_token
"""

from __future__ import annotations

import pytest

from control_plane.app.security.secrets import (
    ControlPlaneSecrets,
    SecretValidationError,
    _MIN_SESSION_SECRET_LENGTH,
    _MIN_SPRITE_BEARER_LENGTH,
    load_control_plane_secrets,
    validate_secrets,
)
from control_plane.app.security.token_verify import create_token_verifier
from control_plane.app.routing.proxy_security import build_proxy_config
from control_plane.app.operations.sprite_rotation import (
    generate_sprite_bearer_token,
)


# ── Fixtures ────────────────────────────────────────────────────────


def _make_secrets(
    supabase_url: str = 'https://test.supabase.co',
    supabase_jwt_secret: str = 'a' * 64,
    session_secret: str = 'b' * 64,
    sprite_bearer_token: str = 'c' * 64,
) -> ControlPlaneSecrets:
    return ControlPlaneSecrets(
        supabase_url=supabase_url,
        supabase_jwt_secret=supabase_jwt_secret,
        session_secret=session_secret,
        sprite_bearer_token=sprite_bearer_token,
    )


@pytest.fixture()
def _clean_env(monkeypatch):
    """Remove all secret env vars for isolated tests."""
    for var in [
        'SUPABASE_URL',
        'SUPABASE_JWT_SECRET',
        'SESSION_SECRET',
        'SPRITE_BEARER_TOKEN',
    ]:
        monkeypatch.delenv(var, raising=False)


# =====================================================================
# 1. ControlPlaneSecrets — immutability and redaction
# =====================================================================


class TestControlPlaneSecrets:

    def test_frozen_dataclass(self):
        s = _make_secrets()
        with pytest.raises(AttributeError):
            s.session_secret = 'new_value'

    def test_repr_redacts_secrets(self):
        s = _make_secrets(
            supabase_jwt_secret='super_secret_jwt',
            session_secret='super_secret_session',
            sprite_bearer_token='super_secret_bearer',
        )
        text = repr(s)
        assert 'super_secret_jwt' not in text
        assert 'super_secret_session' not in text
        assert 'super_secret_bearer' not in text
        assert '<redacted>' in text

    def test_repr_shows_supabase_url(self):
        s = _make_secrets(supabase_url='https://my.supabase.co')
        text = repr(s)
        assert 'https://my.supabase.co' in text

    def test_str_redacts_secrets(self):
        s = _make_secrets(
            supabase_jwt_secret='jwt_val',
            session_secret='sess_val_long_enough_for_minimum_check',
            sprite_bearer_token='bearer_val',
        )
        text = str(s)
        assert 'jwt_val' not in text
        assert 'sess_val' not in text
        assert 'bearer_val' not in text

    def test_all_fields_accessible(self):
        s = _make_secrets(
            supabase_url='https://url.co',
            supabase_jwt_secret='jwt',
            session_secret='sess',
            sprite_bearer_token='bearer',
        )
        assert s.supabase_url == 'https://url.co'
        assert s.supabase_jwt_secret == 'jwt'
        assert s.session_secret == 'sess'
        assert s.sprite_bearer_token == 'bearer'


# =====================================================================
# 2. validate_secrets — required fields
# =====================================================================


class TestValidateRequired:

    def test_valid_secrets_pass(self):
        """No error when all required secrets are present."""
        s = _make_secrets()
        validate_secrets(s)  # Should not raise.

    def test_missing_both_supabase_credentials(self):
        s = _make_secrets(supabase_url='', supabase_jwt_secret='')
        with pytest.raises(SecretValidationError) as exc_info:
            validate_secrets(s)
        assert 'SUPABASE_URL or SUPABASE_JWT_SECRET' in exc_info.value.missing

    def test_supabase_url_alone_sufficient(self):
        """SUPABASE_URL without JWT secret is valid (uses JWKS)."""
        s = _make_secrets(supabase_jwt_secret='')
        validate_secrets(s)

    def test_jwt_secret_alone_sufficient(self):
        """SUPABASE_JWT_SECRET without URL is valid (uses HS256)."""
        s = _make_secrets(supabase_url='')
        validate_secrets(s)

    def test_missing_session_secret(self):
        s = _make_secrets(session_secret='')
        with pytest.raises(SecretValidationError) as exc_info:
            validate_secrets(s)
        assert 'SESSION_SECRET' in exc_info.value.missing

    def test_session_secret_too_short(self):
        s = _make_secrets(session_secret='short')
        with pytest.raises(SecretValidationError) as exc_info:
            validate_secrets(s)
        assert any('SESSION_SECRET' in i for i in exc_info.value.invalid)

    def test_session_secret_exact_minimum_passes(self):
        s = _make_secrets(session_secret='x' * _MIN_SESSION_SECRET_LENGTH)
        validate_secrets(s)


# =====================================================================
# 3. validate_secrets — conditional (sprite bearer)
# =====================================================================


class TestValidateSpriteBearer:

    def test_sprite_bearer_optional_by_default(self):
        s = _make_secrets(sprite_bearer_token='')
        validate_secrets(s)  # Should not raise.

    def test_sprite_bearer_required_when_strict(self):
        s = _make_secrets(sprite_bearer_token='')
        with pytest.raises(SecretValidationError) as exc_info:
            validate_secrets(s, require_sprite_bearer=True)
        assert 'SPRITE_BEARER_TOKEN' in exc_info.value.missing

    def test_sprite_bearer_too_short_when_strict(self):
        s = _make_secrets(sprite_bearer_token='short')
        with pytest.raises(SecretValidationError) as exc_info:
            validate_secrets(s, require_sprite_bearer=True)
        assert any('SPRITE_BEARER_TOKEN' in i for i in exc_info.value.invalid)

    def test_sprite_bearer_exact_minimum_passes(self):
        s = _make_secrets(
            sprite_bearer_token='x' * _MIN_SPRITE_BEARER_LENGTH,
        )
        validate_secrets(s, require_sprite_bearer=True)


# =====================================================================
# 4. SecretValidationError structure
# =====================================================================


class TestSecretValidationError:

    def test_missing_field(self):
        err = SecretValidationError(missing=['SESSION_SECRET'])
        assert 'SESSION_SECRET' in str(err)
        assert err.missing == ['SESSION_SECRET']
        assert err.invalid == []

    def test_invalid_field(self):
        err = SecretValidationError(
            missing=[], invalid=['SESSION_SECRET (min 32)'],
        )
        assert 'invalid' in str(err)
        assert err.missing == []

    def test_both_missing_and_invalid(self):
        err = SecretValidationError(
            missing=['A'], invalid=['B'],
        )
        assert 'missing' in str(err)
        assert 'invalid' in str(err)

    def test_is_value_error_subclass(self):
        err = SecretValidationError(missing=['X'])
        assert isinstance(err, ValueError)


# =====================================================================
# 5. load_control_plane_secrets — from env vars
# =====================================================================


class TestLoadFromEnv:

    @pytest.fixture(autouse=True)
    def _env(self, _clean_env):
        pass

    def test_loads_from_env(self, monkeypatch):
        monkeypatch.setenv('SUPABASE_URL', 'https://env.supabase.co')
        monkeypatch.setenv('SUPABASE_JWT_SECRET', 'j' * 64)
        monkeypatch.setenv('SESSION_SECRET', 's' * 64)
        monkeypatch.setenv('SPRITE_BEARER_TOKEN', 'b' * 64)

        secrets = load_control_plane_secrets()
        assert secrets.supabase_url == 'https://env.supabase.co'
        assert secrets.session_secret == 's' * 64

    def test_explicit_args_override_env(self, monkeypatch):
        monkeypatch.setenv('SUPABASE_URL', 'https://env.supabase.co')
        monkeypatch.setenv('SESSION_SECRET', 's' * 64)

        secrets = load_control_plane_secrets(
            supabase_url='https://override.supabase.co',
        )
        assert secrets.supabase_url == 'https://override.supabase.co'

    def test_fails_when_env_missing(self):
        with pytest.raises(SecretValidationError):
            load_control_plane_secrets()

    def test_whitespace_trimmed(self, monkeypatch):
        monkeypatch.setenv('SUPABASE_URL', '  https://ws.supabase.co  ')
        monkeypatch.setenv('SESSION_SECRET', '  ' + 's' * 64 + '  ')

        secrets = load_control_plane_secrets()
        assert secrets.supabase_url == 'https://ws.supabase.co'
        assert not secrets.session_secret.startswith(' ')


# =====================================================================
# 6. Integration: secrets → create_token_verifier
# =====================================================================


class TestTokenVerifierIntegration:

    def test_supabase_url_creates_jwks_verifier(self):
        """ControlPlaneSecrets.supabase_url wires into JWKS mode."""
        s = _make_secrets(
            supabase_url='https://integration.supabase.co',
            supabase_jwt_secret='',
        )
        verifier = create_token_verifier(supabase_url=s.supabase_url)
        assert verifier is not None

    def test_jwt_secret_creates_static_verifier(self):
        """ControlPlaneSecrets.supabase_jwt_secret wires into HS256 mode."""
        s = _make_secrets(supabase_url='', supabase_jwt_secret='secret' * 10)
        verifier = create_token_verifier(jwt_secret=s.supabase_jwt_secret)
        assert verifier is not None

    def test_both_prefers_jwks(self):
        s = _make_secrets(
            supabase_url='https://both.supabase.co',
            supabase_jwt_secret='secret' * 10,
        )
        verifier = create_token_verifier(
            supabase_url=s.supabase_url,
            jwt_secret=s.supabase_jwt_secret,
        )
        # JWKS mode uses RS256.
        assert 'RS256' in verifier._algorithms


# =====================================================================
# 7. Integration: secrets → build_proxy_config
# =====================================================================


class TestProxyConfigIntegration:

    def test_bearer_token_injected(self):
        s = _make_secrets(sprite_bearer_token='my-bearer-token-' + 'x' * 32)
        config = build_proxy_config(sprite_bearer_token=s.sprite_bearer_token)
        assert 'Authorization' in config.inject_headers
        assert config.inject_headers['Authorization'].startswith('Bearer ')

    def test_no_bearer_in_local_mode(self):
        s = _make_secrets(sprite_bearer_token='')
        config = build_proxy_config(sprite_bearer_token=s.sprite_bearer_token or None)
        assert 'Authorization' not in config.inject_headers

    def test_bearer_never_in_response_redact_list(self):
        config = build_proxy_config(sprite_bearer_token='tok' * 20)
        assert 'authorization' in config.response_redact_headers


# =====================================================================
# 8. Rotation readiness
# =====================================================================


class TestRotationReadiness:

    def test_generate_token_sufficient_length(self):
        token = generate_sprite_bearer_token()
        assert len(token) >= 32

    def test_generate_token_unique(self):
        tokens = {generate_sprite_bearer_token() for _ in range(100)}
        assert len(tokens) == 100

    def test_generate_token_rejects_short_length(self):
        with pytest.raises(ValueError, match='32 bytes'):
            generate_sprite_bearer_token(length=16)

    def test_generated_token_passes_validation(self):
        token = generate_sprite_bearer_token()
        s = _make_secrets(sprite_bearer_token=token)
        validate_secrets(s, require_sprite_bearer=True)


# =====================================================================
# 9. Multiple missing secrets
# =====================================================================


class TestMultipleMissing:

    def test_all_missing_reports_all(self):
        s = ControlPlaneSecrets(
            supabase_url='',
            supabase_jwt_secret='',
            session_secret='',
            sprite_bearer_token='',
        )
        with pytest.raises(SecretValidationError) as exc_info:
            validate_secrets(s, require_sprite_bearer=True)
        err = exc_info.value
        assert len(err.missing) >= 2  # At least supabase + session
