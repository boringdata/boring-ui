"""Load app identity configuration from JSON.

Bead: bd-223o.3 (P3)

Reads ``app_identity.json`` at startup and populates an
``AppIdentityResolver`` with host mappings and app configs.

Expected JSON schema::

    {
      "host_mapping": {
        "boring-ui.modal.run": "boring-ui",
        "staging.boring-ui.dev": "boring-ui",
        "*": "boring-ui"
      },
      "apps": {
        "boring-ui": {
          "app_id": "boring-ui",
          "name": "Boring UI",
          "logo": "B",
          "default_release_id": "2026-02-13.1"
        }
      }
    }

Configuration sources (in order):
  1. Explicit ``data`` dict argument (tests, embedded config).
  2. Filesystem path via ``path`` argument.
  3. ``APP_IDENTITY_CONFIG`` environment variable pointing to a file.
  4. Default path: ``config/app_identity.json`` relative to CWD.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .resolver import AppConfig, AppIdentityResolver

_DEFAULT_CONFIG_PATH = 'config/app_identity.json'
_ENV_VAR = 'APP_IDENTITY_CONFIG'


class IdentityConfigError(ValueError):
    """Raised when app identity configuration is invalid or missing."""


def load_identity_config(
    *,
    path: str | Path | None = None,
    data: dict | None = None,
) -> AppIdentityResolver:
    """Load app identity config and return a populated resolver.

    Args:
        path: Filesystem path to ``app_identity.json``.
        data: Pre-parsed config dict (takes precedence over path).

    Returns:
        Configured AppIdentityResolver.

    Raises:
        IdentityConfigError: If config cannot be loaded or is malformed.
    """
    if data is None:
        data = _load_json(path)

    return _build_resolver(data)


def _load_json(path: str | Path | None) -> dict:
    """Load and parse the JSON config file."""
    resolved = path
    if resolved is None:
        resolved = os.environ.get(_ENV_VAR, '').strip() or None
    if resolved is None:
        resolved = _DEFAULT_CONFIG_PATH

    config_path = Path(resolved)
    if not config_path.exists():
        raise IdentityConfigError(
            f'App identity config not found at {config_path}. '
            f'Set {_ENV_VAR} or provide a path argument.'
        )

    try:
        text = config_path.read_text(encoding='utf-8')
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise IdentityConfigError(
            f'Invalid JSON in {config_path}: {exc}'
        ) from exc


def _build_resolver(data: dict) -> AppIdentityResolver:
    """Build an AppIdentityResolver from parsed config data."""
    if not isinstance(data, dict):
        raise IdentityConfigError(
            f'Expected dict at top level, got {type(data).__name__}'
        )

    host_mapping = data.get('host_mapping', {})
    if not isinstance(host_mapping, dict):
        raise IdentityConfigError(
            f'host_mapping must be a dict, got {type(host_mapping).__name__}'
        )

    apps_raw = data.get('apps', {})
    if not isinstance(apps_raw, dict):
        raise IdentityConfigError(
            f'apps must be a dict, got {type(apps_raw).__name__}'
        )

    app_configs: dict[str, AppConfig] = {}
    for app_id, app_data in apps_raw.items():
        if not isinstance(app_data, dict):
            raise IdentityConfigError(
                f'App config for {app_id!r} must be a dict'
            )
        app_configs[app_id] = AppConfig(
            app_id=app_data.get('app_id', app_id),
            name=app_data.get('name', app_id),
            logo=app_data.get('logo', ''),
            default_release_id=app_data.get('default_release_id', ''),
        )

    default_app_id = data.get('default_app_id')

    return AppIdentityResolver(
        host_map=host_mapping,
        app_configs=app_configs,
        default_app_id=default_app_id,
    )
