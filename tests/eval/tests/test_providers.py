"""Unit tests for eval harness provider adapters.

Run with: python3 -m pytest tests/eval/tests/test_providers.py -v
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import tests.eval.providers.neon as neon_module
from tests.eval.fly_cli import resolve_fly_cli
from tests.eval.providers.fly import FlyAdapter
from tests.eval.providers.neon import NeonAdapter
from tests.eval.providers.vault import VaultAdapter
from tests.eval.redaction import SecretRegistry


class TestFlyCliDiscovery:
    def test_resolve_fly_cli_uses_home_install(self, monkeypatch, tmp_path):
        home = tmp_path / "home"
        fly_path = home / ".fly" / "bin" / "fly"
        fly_path.parent.mkdir(parents=True)
        fly_path.write_text("#!/bin/sh\nexit 0\n")
        fly_path.chmod(0o755)

        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setenv("PATH", "")
        monkeypatch.delenv("FLYCTL_BIN", raising=False)

        assert resolve_fly_cli() == str(fly_path)

    def test_fly_adapter_defaults_to_resolved_home_install(self, monkeypatch, tmp_path):
        home = tmp_path / "home"
        fly_path = home / ".fly" / "bin" / "fly"
        fly_path.parent.mkdir(parents=True)
        fly_path.write_text("#!/bin/sh\nexit 0\n")
        fly_path.chmod(0o755)

        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setenv("PATH", "")
        monkeypatch.delenv("FLYCTL_BIN", raising=False)

        adapter = FlyAdapter()
        assert Path(adapter._cmd) == fly_path


class TestFlyAdapter:
    def test_app_exists_returns_true_for_known_app(self, monkeypatch):
        adapter = FlyAdapter(fly_cmd="fly")
        monkeypatch.setattr(
            adapter,
            "list_apps",
            lambda prefix=None: [SimpleNamespace(name="known-app", hostname="known-app.fly.dev")],
        )

        assert adapter.app_exists("known-app") is True

    def test_app_exists_returns_false_for_unknown_app(self, monkeypatch):
        adapter = FlyAdapter(fly_cmd="fly")
        monkeypatch.setattr(adapter, "list_apps", lambda prefix=None: [])

        assert adapter.app_exists("missing-app") is False

    def test_app_url_derives_fly_hostname(self, monkeypatch):
        adapter = FlyAdapter(fly_cmd="fly")
        monkeypatch.setattr(
            adapter,
            "list_apps",
            lambda prefix=None: [SimpleNamespace(name="demo", hostname="demo.fly.dev")],
        )

        assert adapter.app_url("demo") == "https://demo.fly.dev"
        assert adapter.app_url("missing") is None

    def test_stop_app_calls_suspend(self, monkeypatch):
        adapter = FlyAdapter(fly_cmd="fly")
        calls: list[list[str]] = []

        def fake_run(args, timeout=30):
            calls.append(args)
            return 0, "", ""

        monkeypatch.setattr(adapter, "_run", fake_run)

        assert adapter.stop_app("demo") is True
        assert calls == [["apps", "suspend", "demo"]]

    def test_delete_app_handles_already_deleted_gracefully(self, monkeypatch):
        adapter = FlyAdapter(fly_cmd="fly")
        monkeypatch.setattr(
            adapter,
            "_run",
            lambda args, timeout=30: (1, "", "Could not find App demo"),
        )

        assert adapter.delete_app("demo") is True


class TestNeonAdapter:
    def test_project_exists_checks_bui_status_output(self, monkeypatch):
        adapter = NeonAdapter(bui_cmd="bui")
        calls: list[list[str]] = []

        def fake_run(args, timeout=30):
            calls.append(args)
            return 0, "project neon-123 is healthy", ""

        monkeypatch.setattr(adapter, "_run", fake_run)

        assert adapter.project_exists("neon-123") is True
        assert calls == [["bui", "neon", "status"]]

    def test_project_exists_returns_false_when_bui_missing(self, monkeypatch):
        adapter = NeonAdapter(bui_cmd="bui")
        monkeypatch.setattr(
            adapter,
            "_run",
            lambda args, timeout=30: (-1, "", "command not found: bui"),
        )

        assert adapter.project_exists("neon-123") is False

    def test_jwks_reachable_uses_httpx_when_available(self, monkeypatch):
        adapter = NeonAdapter(bui_cmd="bui")
        calls: list[str] = []

        def fake_get(url, timeout=10, follow_redirects=True):
            calls.append(url)
            return SimpleNamespace(status_code=200)

        monkeypatch.setattr(neon_module, "_HAS_HTTPX", True)
        monkeypatch.setattr(
            neon_module,
            "httpx",
            SimpleNamespace(get=fake_get),
            raising=False,
        )

        assert adapter.jwks_reachable("https://example.test/.well-known/jwks.json") is True
        assert calls == ["https://example.test/.well-known/jwks.json"]

    def test_jwks_reachable_falls_back_to_curl_when_httpx_errors(self, monkeypatch):
        adapter = NeonAdapter(bui_cmd="bui")
        calls: list[list[str]] = []
        url = "https://example.test/.well-known/jwks.json"

        def fake_get(*args, **kwargs):
            raise RuntimeError("network boom")

        def fake_run(args, timeout=30):
            calls.append(args)
            return 0, "200", ""

        monkeypatch.setattr(neon_module, "_HAS_HTTPX", True)
        monkeypatch.setattr(
            neon_module,
            "httpx",
            SimpleNamespace(get=fake_get),
            raising=False,
        )
        monkeypatch.setattr(adapter, "_run", fake_run)

        assert adapter.jwks_reachable(url) is True
        assert calls == [["curl", "-sSf", "-o", "/dev/null", "-w", "%{http_code}", url]]

    def test_destroy_project_uses_force_delete(self, monkeypatch):
        adapter = NeonAdapter(bui_cmd="bui")
        calls: list[list[str]] = []

        def fake_run(args, timeout=30):
            calls.append(args)
            return 0, "", ""

        monkeypatch.setattr(adapter, "_run", fake_run)

        assert adapter.destroy_project("neon-123") is True
        assert calls == [["bui", "neon", "destroy", "--force", "--project-id", "neon-123"]]


class TestVaultAdapter:
    def test_read_secret_registers_value_for_redaction(self, monkeypatch):
        registry = SecretRegistry()
        adapter = VaultAdapter(registry=registry, vault_cmd="vault")
        calls: list[list[str]] = []

        def fake_run(args, timeout=15):
            calls.append(args)
            return 0, "supersecretvalue12345", ""

        monkeypatch.setattr(adapter, "_run", fake_run)

        value = adapter.read_secret("secret/agent/app/demo", "api_key")

        assert value == "supersecretvalue12345"
        assert calls == [["kv", "get", "-field=api_key", "secret/agent/app/demo"]]
        matches = registry.scan("token=supersecretvalue12345")
        assert matches
        assert matches[0].name == "secret/agent/app/demo:api_key"

    def test_secret_exists_returns_true_for_existing_path(self, monkeypatch):
        adapter = VaultAdapter(vault_cmd="vault")
        monkeypatch.setattr(adapter, "_run", lambda args, timeout=15: (0, "ok", ""))

        assert adapter.secret_exists("secret/agent/app/demo") is True

    def test_secret_exists_handles_vault_unavailable_gracefully(self, monkeypatch):
        adapter = VaultAdapter(vault_cmd="vault")
        monkeypatch.setattr(
            adapter,
            "_run",
            lambda args, timeout=15: (-1, "", "vault CLI not found"),
        )

        assert adapter.secret_exists("secret/agent/app/demo") is False

    def test_read_and_register_eval_secrets_counts_successes(self, monkeypatch):
        registry = SecretRegistry()
        adapter = VaultAdapter(registry=registry, vault_cmd="vault")
        values = {
            ("secret/agent/anthropic", "api_key"): "sk-ant-secret-1234567890",
            ("secret/agent/boringdata-agent", "token"): "ghp_abcdefghijklmnopqrstuvwxyz1234567890",
            ("secret/agent/openai", "api_key"): "sk-abcdefghijklmnopqrstuvwxyz123456",
        }

        def fake_run(args, timeout=15):
            path = args[-1]
            field = args[2].split("=", 1)[1]
            value = values.get((path, field))
            if value is None:
                return 2, "", "missing"
            return 0, value, ""

        monkeypatch.setattr(adapter, "_run", fake_run)

        assert adapter.read_and_register_eval_secrets() == 3
        assert registry.count == 3
