#!/usr/bin/env python3
"""Validate control-plane secrets are configured correctly.

Bead: bd-223o.2 (P2)

Checks:
  1. All required environment variables are set and non-empty.
  2. Secret values meet minimum length requirements.
  3. JWKS endpoint is reachable (if SUPABASE_URL is set).
  4. Rotation readiness: sprite bearer token generation works.
  5. No-leak: secrets do not appear in repr/str of config objects.

Usage::

    # Validate from environment (Modal injects secrets as env vars):
    python3 scripts/validate_secrets.py

    # With explicit values:
    SUPABASE_URL=https://xxx.supabase.co \\
    SUPABASE_JWT_SECRET=... \\
    SESSION_SECRET=... \\
    python3 scripts/validate_secrets.py

    # Strict mode (require SPRITE_BEARER_TOKEN):
    python3 scripts/validate_secrets.py --strict

Exit codes:
  0 — All checks passed.
  1 — One or more checks failed.
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.error
import urllib.request

# Allow running from project root.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_PROJECT_ROOT, 'src'))

from control_plane.app.security.secrets import (
    ControlPlaneSecrets,
    SecretValidationError,
    load_control_plane_secrets,
)
from control_plane.app.operations.sprite_rotation import (
    generate_sprite_bearer_token,
)


# ── Check helpers ───────────────────────────────────────────────────

PASS = 0
FAIL = 0


def check(name: str, fn) -> bool:
    global PASS, FAIL
    try:
        result = fn()
        if result is False:
            raise AssertionError('returned False')
        print(f'  PASS: {name}')
        PASS += 1
        return True
    except Exception as exc:
        print(f'  FAIL: {name} — {exc}')
        FAIL += 1
        return False


# ── Checks ──────────────────────────────────────────────────────────


def check_secret_loading(strict: bool) -> ControlPlaneSecrets | None:
    """Validate that secrets load successfully from environment."""
    secrets = None

    def _load():
        nonlocal secrets
        secrets = load_control_plane_secrets(
            require_sprite_bearer=strict,
        )
        return True

    check('Secrets load from environment', _load)
    return secrets


def check_jwks_reachable(supabase_url: str) -> None:
    """Validate that the JWKS endpoint is reachable."""
    if not supabase_url:
        print('  SKIP: JWKS reachability (no SUPABASE_URL)')
        return

    jwks_url = f'{supabase_url.rstrip("/")}/auth/v1/.well-known/jwks.json'

    def _fetch():
        req = urllib.request.Request(jwks_url, method='GET')
        req.add_header('Accept', 'application/json')
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status != 200:
                raise AssertionError(f'HTTP {resp.status}')
            data = resp.read()
            if b'"keys"' not in data:
                raise AssertionError('Response missing "keys" field')
        return True

    check(f'JWKS endpoint reachable ({jwks_url})', _fetch)


def check_rotation_readiness() -> None:
    """Validate that bearer token generation works."""
    def _generate():
        token = generate_sprite_bearer_token()
        if len(token) < 32:
            raise AssertionError(f'Token too short: {len(token)}')
        return True

    check('Sprite bearer token generation', _generate)


def check_no_leak(secrets: ControlPlaneSecrets) -> None:
    """Validate that secrets don't leak in string representations."""
    def _repr_check():
        text = repr(secrets)
        for secret_val in [
            secrets.supabase_jwt_secret,
            secrets.session_secret,
            secrets.sprite_bearer_token,
        ]:
            if secret_val and secret_val in text:
                raise AssertionError('Secret value found in repr()')
        return True

    def _str_check():
        text = str(secrets)
        for secret_val in [
            secrets.supabase_jwt_secret,
            secrets.session_secret,
            secrets.sprite_bearer_token,
        ]:
            if secret_val and secret_val in text:
                raise AssertionError('Secret value found in str()')
        return True

    check('Secrets not leaked in repr()', _repr_check)
    check('Secrets not leaked in str()', _str_check)


def check_env_vars_present(strict: bool) -> None:
    """Check which environment variables are set."""
    required = ['SESSION_SECRET']
    one_of = [('SUPABASE_URL', 'SUPABASE_JWT_SECRET')]
    optional = ['SPRITE_BEARER_TOKEN']

    if strict:
        required.append('SPRITE_BEARER_TOKEN')
        optional = []

    def _make_required_check(var_name: str):
        def _check():
            if not os.environ.get(var_name, '').strip():
                raise AssertionError(f'{var_name} not set')
            return True
        return _check

    def _make_one_of_check(group: tuple[str, ...]):
        def _check():
            if not any(os.environ.get(v, '').strip() for v in group):
                raise AssertionError(
                    f'Neither {" nor ".join(group)} is set'
                )
            return True
        return _check

    for var in required:
        check(f'Env var {var} is set', _make_required_check(var))

    for group in one_of:
        names = ' or '.join(group)
        check(f'Env var {names} is set', _make_one_of_check(group))

    for var in optional:
        val = os.environ.get(var, '').strip()
        if val:
            print(f'  INFO: {var} is set')
        else:
            print(f'  INFO: {var} not set (optional)')


# ── Main ────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Validate control-plane secrets configuration.',
    )
    parser.add_argument(
        '--strict',
        action='store_true',
        help='Require all secrets including SPRITE_BEARER_TOKEN.',
    )
    args = parser.parse_args()

    print('=== Control Plane Secret Validation ===')
    print()

    print('[1/5] Environment variables')
    check_env_vars_present(strict=args.strict)

    print()
    print('[2/5] Secret loading and validation')
    secrets = check_secret_loading(strict=args.strict)

    if secrets:
        print()
        print('[3/5] JWKS endpoint reachability')
        check_jwks_reachable(secrets.supabase_url)

        print()
        print('[4/5] No-leak verification')
        check_no_leak(secrets)
    else:
        print()
        print('  SKIP: JWKS, no-leak (secrets failed to load)')

    print()
    print('[5/5] Rotation readiness')
    check_rotation_readiness()

    print()
    print(f'=== Results: {PASS} passed, {FAIL} failed ===')

    if FAIL > 0:
        print('Secret configuration NOT ready.')
        sys.exit(1)
    else:
        print('Secret configuration ready.')
        sys.exit(0)


if __name__ == '__main__':
    main()
