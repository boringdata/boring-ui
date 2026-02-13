#!/usr/bin/env python3
"""Validate Modal secrets for control-plane/runtime auth.

Bead: bd-223o.2 (P2)

Checks:
1. All required Modal secrets exist (via ``modal secret list``).
2. Secret keys match expected names.
3. Sprite bearer rotation runbook is valid.
4. Proxy security config has redaction rules for all secret headers.
5. Token verifier can be constructed from expected env vars.

Usage::

    python scripts/validate_modal_secrets.py
    python scripts/validate_modal_secrets.py --skip-modal   # offline mode
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))


def _header(msg: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {msg}")
    print(f"{'=' * 60}")


def _ok(msg: str) -> None:
    print(f"  [PASS] {msg}")


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def _skip(msg: str) -> None:
    print(f"  [SKIP] {msg}")


def verify_modal_secrets() -> tuple[int, int]:
    """Check that required Modal secrets exist."""
    passed = 0
    failed = 0

    _header("Modal secret existence")

    try:
        result = subprocess.run(
            ["modal", "secret", "list", "--json"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            _fail(f"modal secret list failed: {result.stderr.strip()}")
            failed += 1
            return passed, failed

        secrets_data = json.loads(result.stdout)
        existing_names = {s.get("name", s.get("Name", "")) for s in secrets_data}
    except FileNotFoundError:
        _fail("modal CLI not found in PATH")
        failed += 1
        return passed, failed
    except json.JSONDecodeError:
        # Fallback: parse table output
        result = subprocess.run(
            ["modal", "secret", "list"],
            capture_output=True, text=True, timeout=30,
        )
        existing_names = set()
        for line in result.stdout.splitlines():
            parts = line.split()
            if parts and not parts[0].startswith(("─", "┃", "┏", "┗", "┡", "Name")):
                existing_names.add(parts[0].strip("│ "))

    from control_plane.app.security.secret_config import CONTROL_PLANE_SECRETS

    for spec in CONTROL_PLANE_SECRETS:
        if spec.name in existing_names:
            _ok(f"Modal secret exists: {spec.name} ({spec.description})")
            passed += 1
        elif spec.optional:
            _skip(f"Optional Modal secret missing: {spec.name}")
        else:
            _fail(f"Required Modal secret missing: {spec.name}")
            failed += 1

    return passed, failed


def verify_secret_specs() -> tuple[int, int]:
    """Validate the secret specification is complete and consistent."""
    passed = 0
    failed = 0

    _header("Secret specification consistency")

    from control_plane.app.security.secret_config import (
        CONTROL_PLANE_SECRETS,
        SECRET_KEYS,
    )

    # All secret env vars should have specs.
    all_keys = set()
    for spec in CONTROL_PLANE_SECRETS:
        for key in spec.required_keys:
            all_keys.add(key)

    if len(CONTROL_PLANE_SECRETS) >= 3:
        _ok(f"Secret catalog defines {len(CONTROL_PLANE_SECRETS)} specs")
        passed += 1
    else:
        _fail(f"Only {len(CONTROL_PLANE_SECRETS)} secret specs (expected >= 3)")
        failed += 1

    # Sensitive keys should be in SECRET_KEYS for leak detection.
    sensitive_expected = {
        'SPRITE_BEARER_TOKEN',
        'SUPABASE_SERVICE_ROLE_KEY',
        'ANTHROPIC_API_KEY',
    }
    for key in sensitive_expected:
        if key in SECRET_KEYS:
            _ok(f"Leak detection covers: {key}")
            passed += 1
        else:
            _fail(f"Leak detection missing: {key}")
            failed += 1

    return passed, failed


def verify_rotation_runbook() -> tuple[int, int]:
    """Validate the sprite bearer rotation runbook."""
    passed = 0
    failed = 0

    _header("Rotation runbook validation")

    from control_plane.app.operations.sprite_rotation import (
        DEFAULT_ROTATION_RUNBOOK,
        REQUIRED_PHASES,
        REQUIRED_SMOKE_TYPES,
        validate_rotation_runbook,
    )

    try:
        validate_rotation_runbook(DEFAULT_ROTATION_RUNBOOK)
        _ok("Rotation runbook passes validation")
        passed += 1
    except ValueError as exc:
        _fail(f"Rotation runbook invalid: {exc}")
        failed += 1

    # All phases covered.
    covered = {step.phase for step in DEFAULT_ROTATION_RUNBOOK.steps}
    if covered >= REQUIRED_PHASES:
        _ok(f"All {len(REQUIRED_PHASES)} rotation phases covered")
        passed += 1
    else:
        _fail(f"Missing phases: {REQUIRED_PHASES - covered}")
        failed += 1

    # All smoke check types present.
    check_types = {c.check_type for c in DEFAULT_ROTATION_RUNBOOK.smoke_checks}
    if check_types >= REQUIRED_SMOKE_TYPES:
        _ok(f"All {len(REQUIRED_SMOKE_TYPES)} smoke check types covered")
        passed += 1
    else:
        _fail(f"Missing smoke checks: {REQUIRED_SMOKE_TYPES - check_types}")
        failed += 1

    # Runbook has an owner.
    if DEFAULT_ROTATION_RUNBOOK.owner:
        _ok(f"Rotation owner: {DEFAULT_ROTATION_RUNBOOK.owner}")
        passed += 1
    else:
        _fail("Rotation runbook has no owner")
        failed += 1

    return passed, failed


def verify_proxy_redaction() -> tuple[int, int]:
    """Verify proxy security redacts all sensitive headers."""
    passed = 0
    failed = 0

    _header("Proxy header redaction")

    from control_plane.app.routing.proxy_security import (
        _DEFAULT_STRIP_HEADERS,
        _RESPONSE_REDACT_HEADERS,
    )

    # Bearer-related headers must be stripped from requests.
    for header in ('authorization', 'x-sprite-bearer', 'x-service-role'):
        if header in _DEFAULT_STRIP_HEADERS:
            _ok(f"Request strip: {header}")
            passed += 1
        else:
            _fail(f"Missing request strip: {header}")
            failed += 1

    # Bearer-related headers must be redacted from responses.
    for header in ('authorization', 'x-sprite-bearer', 'x-service-role'):
        if header in _RESPONSE_REDACT_HEADERS:
            _ok(f"Response redact: {header}")
            passed += 1
        else:
            _fail(f"Missing response redact: {header}")
            failed += 1

    return passed, failed


def verify_token_verifier() -> tuple[int, int]:
    """Verify token verifier factory accepts expected configurations."""
    passed = 0
    failed = 0

    _header("Token verifier configuration")

    from control_plane.app.security.token_verify import (
        create_token_verifier,
        TokenVerifier,
    )

    # HS256 fallback (local dev).
    try:
        verifier = create_token_verifier(jwt_secret="test-secret-for-validation")
        if isinstance(verifier, TokenVerifier):
            _ok("HS256 fallback verifier constructs OK")
            passed += 1
        else:
            _fail("HS256 verifier wrong type")
            failed += 1
    except Exception as exc:
        _fail(f"HS256 verifier failed: {exc}")
        failed += 1

    # RS256 JWKS (production).
    try:
        verifier = create_token_verifier(supabase_url="https://example.supabase.co")
        if isinstance(verifier, TokenVerifier):
            _ok("RS256 JWKS verifier constructs OK")
            passed += 1
        else:
            _fail("RS256 verifier wrong type")
            failed += 1
    except Exception as exc:
        _fail(f"RS256 verifier failed: {exc}")
        failed += 1

    # Missing both should raise.
    try:
        create_token_verifier()
        _fail("Expected ValueError when no config provided")
        failed += 1
    except ValueError:
        _ok("Rejects missing auth config (ValueError)")
        passed += 1

    return passed, failed


def verify_token_generation() -> tuple[int, int]:
    """Verify sprite bearer token generation meets requirements."""
    passed = 0
    failed = 0

    _header("Token generation")

    from control_plane.app.operations.sprite_rotation import (
        generate_sprite_bearer_token,
    )

    # Token is generated and has sufficient length.
    token = generate_sprite_bearer_token()
    if len(token) >= 40:
        _ok(f"Token length: {len(token)} chars (>= 40)")
        passed += 1
    else:
        _fail(f"Token too short: {len(token)} chars")
        failed += 1

    # Token is unique on each call.
    token2 = generate_sprite_bearer_token()
    if token != token2:
        _ok("Tokens are unique per generation")
        passed += 1
    else:
        _fail("Tokens are not unique!")
        failed += 1

    # Minimum length enforcement.
    try:
        generate_sprite_bearer_token(length=16)
        _fail("Should reject length < 32")
        failed += 1
    except ValueError:
        _ok("Rejects short token length (< 32 bytes)")
        passed += 1

    return passed, failed


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Modal secrets")
    parser.add_argument(
        "--skip-modal", action="store_true",
        help="Skip Modal CLI checks (offline validation only)",
    )
    args = parser.parse_args()

    total_passed = 0
    total_failed = 0

    # Modal secret existence.
    if not args.skip_modal:
        p, f = verify_modal_secrets()
        total_passed += p
        total_failed += f
    else:
        _header("Modal secret existence")
        _skip("Skipped (--skip-modal)")

    # Secret specs.
    p, f = verify_secret_specs()
    total_passed += p
    total_failed += f

    # Rotation runbook.
    p, f = verify_rotation_runbook()
    total_passed += p
    total_failed += f

    # Proxy redaction.
    p, f = verify_proxy_redaction()
    total_passed += p
    total_failed += f

    # Token verifier.
    p, f = verify_token_verifier()
    total_passed += p
    total_failed += f

    # Token generation.
    p, f = verify_token_generation()
    total_passed += p
    total_failed += f

    # Summary.
    _header("Summary")
    print(f"  Passed: {total_passed}")
    print(f"  Failed: {total_failed}")
    print()

    if total_failed > 0:
        print("  RESULT: FAIL")
        sys.exit(1)
    else:
        print("  RESULT: PASS")
        sys.exit(0)


if __name__ == "__main__":
    main()
