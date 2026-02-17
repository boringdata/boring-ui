import os
from pathlib import Path

from boring_ui.api.config import APIConfig


def test_api_config_companion_url_defaults_to_none(monkeypatch):
    monkeypatch.delenv('COMPANION_URL', raising=False)
    config = APIConfig(workspace_root=Path.cwd())
    assert config.companion_url is None


def test_api_config_companion_url_reads_env(monkeypatch):
    monkeypatch.setenv('COMPANION_URL', 'http://localhost:3456')
    config = APIConfig(workspace_root=Path.cwd())
    assert config.companion_url == 'http://localhost:3456'


def test_api_config_pi_url_defaults_to_none(monkeypatch):
    monkeypatch.delenv('PI_URL', raising=False)
    config = APIConfig(workspace_root=Path.cwd())
    assert config.pi_url is None


def test_api_config_pi_url_reads_env(monkeypatch):
    monkeypatch.setenv('PI_URL', 'http://localhost:8787')
    config = APIConfig(workspace_root=Path.cwd())
    assert config.pi_url == 'http://localhost:8787'
