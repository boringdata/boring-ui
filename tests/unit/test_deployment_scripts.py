"""Deployment script guardrails for core vs sandbox-proxy modes (bd-8lda)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_FULL_APP = REPO_ROOT / "scripts" / "run_full_app.py"
RUN_FULL_APP_SH = REPO_ROOT / "scripts" / "run_full_app.sh"
RUN_BACKEND = REPO_ROOT / "scripts" / "run_backend.py"


def _load_run_full_app_module():
    spec = importlib.util.spec_from_file_location("run_full_app", RUN_FULL_APP)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_run_full_app_help_includes_deployment_flags() -> None:
    result = subprocess.run(
        [sys.executable, str(RUN_FULL_APP), "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "--deploy-mode" in result.stdout
    assert "--sandbox-proxy-url" in result.stdout


def test_run_full_app_shell_help_includes_deployment_flags() -> None:
    result = subprocess.run(
        ["bash", str(RUN_FULL_APP_SH), "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "--deploy-mode" in result.stdout
    assert "--sandbox-proxy-url" in result.stdout


def test_run_backend_help_includes_deploy_mode() -> None:
    result = subprocess.run(
        [sys.executable, str(RUN_BACKEND), "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "--deploy-mode" in result.stdout


def test_deployment_mode_resolution_prefers_cli_and_normalizes_proxy_mode() -> None:
    module = _load_run_full_app_module()
    mode, proxy_url = module._resolve_deploy_mode(  # type: ignore[attr-defined]
        cli_mode="sandbox-proxy",
        cli_proxy_url="http://127.0.0.1:8080/",
        cfg={"deployment": {"mode": "core", "sandbox_proxy_url": "http://ignored"}},
        env={"DEPLOY_MODE": "core"},
    )
    assert mode == "sandbox-proxy"
    assert proxy_url == "http://127.0.0.1:8080"


def test_deployment_mode_defaults_to_core() -> None:
    module = _load_run_full_app_module()
    mode, proxy_url = module._resolve_deploy_mode(  # type: ignore[attr-defined]
        cli_mode=None,
        cli_proxy_url=None,
        cfg={},
        env={},
    )
    assert mode == "core"
    assert proxy_url is None


def test_frontend_env_core_mode_uses_backend_api_url() -> None:
    module = _load_run_full_app_module()
    fe_env = module._resolve_frontend_env(  # type: ignore[attr-defined]
        base_env={"DEPLOY_MODE": "core"},
        frontend_cfg={"vite_api_url": "http://127.0.0.1:9000"},
        deploy_mode="core",
        sandbox_proxy_url=None,
        backend_port=8000,
    )
    assert fe_env["VITE_API_URL"] == "http://127.0.0.1:9000"
    assert "VITE_GATEWAY_URL" not in fe_env


def test_frontend_env_core_mode_uses_optional_gateway_override() -> None:
    module = _load_run_full_app_module()
    fe_env = module._resolve_frontend_env(  # type: ignore[attr-defined]
        base_env={"DEPLOY_MODE": "core", "VITE_GATEWAY_URL": "http://stale"},
        frontend_cfg={
            "vite_api_url": "http://127.0.0.1:9000",
            "vite_gateway_url": "http://127.0.0.1:8100/",
        },
        deploy_mode="core",
        sandbox_proxy_url=None,
        backend_port=8000,
    )
    assert fe_env["VITE_API_URL"] == "http://127.0.0.1:9000"
    assert fe_env["VITE_GATEWAY_URL"] == "http://127.0.0.1:8100"


def test_frontend_env_sandbox_proxy_mode_points_api_and_gateway_to_proxy() -> None:
    module = _load_run_full_app_module()
    fe_env = module._resolve_frontend_env(  # type: ignore[attr-defined]
        base_env={"DEPLOY_MODE": "sandbox-proxy"},
        frontend_cfg={"vite_api_url": "http://127.0.0.1:9000"},
        deploy_mode="sandbox-proxy",
        sandbox_proxy_url="http://127.0.0.1:8080",
        backend_port=8000,
    )
    assert fe_env["VITE_API_URL"] == "http://127.0.0.1:8080"
    assert fe_env["VITE_GATEWAY_URL"] == "http://127.0.0.1:8080"
