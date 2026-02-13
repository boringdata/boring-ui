from __future__ import annotations

from unittest.mock import patch

import pytest


def test_modal_app_imports_create_app_indirectly():
    # Import should succeed without executing create_app at import time.
    import control_plane.modal.modal_app as modal_app

    assert hasattr(modal_app, "_build_control_plane_app")


def test_required_env_vars_list_matches_spec():
    import control_plane.modal.modal_app as modal_app

    assert modal_app.REQUIRED_ENV_VARS == (
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_PUBLISHABLE_KEY",
        "SESSION_SECRET",
        "SPRITE_BEARER_TOKEN",
    )


def test_jwks_url_derived_from_supabase_url():
    import control_plane.modal.modal_app as modal_app

    assert (
        modal_app.derive_jwks_url("https://xyz.supabase.co")
        == "https://xyz.supabase.co/auth/v1/certs"
    )
    assert (
        modal_app.derive_jwks_url("https://xyz.supabase.co/")
        == "https://xyz.supabase.co/auth/v1/certs"
    )


def test_volume_mount_configured_for_mnt_artifacts():
    import control_plane.modal.modal_app as modal_app

    assert modal_app.ARTIFACTS_MOUNT_PATH == "/mnt/artifacts"


def test_scaling_config_constants_match_spec():
    import control_plane.modal.modal_app as modal_app

    assert modal_app.MIN_CONTAINERS == 0
    assert modal_app.MAX_CONTAINERS == 10
    assert modal_app.TIMEOUT_SECONDS == 600


def test_image_dependency_list_contains_required_packages():
    import control_plane.modal.modal_app as modal_app

    deps = " ".join(modal_app.IMAGE_PIP_DEPS)
    assert "fastapi" in deps
    assert "uvicorn" in deps
    assert "httpx" in deps
    assert "PyJWT" in deps
    assert "modal" in deps


def test_build_control_plane_app_calls_create_app(monkeypatch):
    import control_plane.modal.modal_app as modal_app

    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc-key")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "pub-key")
    monkeypatch.setenv("SESSION_SECRET", "x" * 32)
    monkeypatch.setenv("SPRITE_BEARER_TOKEN", "sprite-token")

    with patch("control_plane.app.main.create_app") as create_app:
        # We only need to ensure the modal entrypoint defers to CP0 factory.
        create_app.return_value = object()
        app_obj = modal_app._build_control_plane_app()

    assert app_obj is create_app.return_value
