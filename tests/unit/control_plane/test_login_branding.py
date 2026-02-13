"""Login branding precedence chain tests.

Bead: bd-223o.8.4 (I4)

Tests:
  - Level 3: No workspace or app → hardcoded fallback
  - Level 2: App config only → app branding
  - Level 1: Workspace branding only → workspace branding
  - Precedence: workspace overrides app overrides default
  - Partial override: workspace name + app logo
  - Empty strings in workspace don't override
  - Source tracking
"""

from __future__ import annotations

import pytest

from control_plane.app.identity.branding import (
    DEFAULT_BRANDING_LOGO,
    DEFAULT_BRANDING_NAME,
    LoginBranding,
    WorkspaceBranding,
    resolve_login_branding,
)
from control_plane.app.identity.resolver import AppConfig

# ── Fixtures ──────────────────────────────────────────────────────────

APP_CONFIG = AppConfig(
    app_id='boring-ui',
    name='Boring UI',
    logo='/assets/boring-ui-logo.svg',
    default_release_id='2026-02-13.1',
)

WS_BRANDING = WorkspaceBranding(
    name='Acme Portal',
    logo='/ws/acme-logo.png',
)


# =====================================================================
# Level 3: Hardcoded fallback (no workspace, no app)
# =====================================================================


class TestHardcodedFallback:
    def test_no_inputs_returns_defaults(self):
        result = resolve_login_branding()
        assert result.name == DEFAULT_BRANDING_NAME
        assert result.logo == DEFAULT_BRANDING_LOGO
        assert result.source == 'default'

    def test_default_name_is_app(self):
        assert DEFAULT_BRANDING_NAME == 'App'


# =====================================================================
# Level 2: App config
# =====================================================================


class TestAppConfigBranding:
    def test_app_config_provides_branding(self):
        result = resolve_login_branding(app_config=APP_CONFIG)
        assert result.name == 'Boring UI'
        assert result.logo == '/assets/boring-ui-logo.svg'
        assert result.source == 'app'

    def test_app_config_empty_name_falls_to_default(self):
        config = AppConfig(app_id='x', name='', logo='/logo.svg')
        result = resolve_login_branding(app_config=config)
        assert result.name == DEFAULT_BRANDING_NAME
        assert result.logo == '/logo.svg'

    def test_app_config_empty_logo_falls_to_default(self):
        config = AppConfig(app_id='x', name='MyApp', logo='')
        result = resolve_login_branding(app_config=config)
        assert result.name == 'MyApp'
        assert result.logo == DEFAULT_BRANDING_LOGO


# =====================================================================
# Level 1: Workspace branding
# =====================================================================


class TestWorkspaceBranding:
    def test_workspace_overrides_all(self):
        result = resolve_login_branding(
            workspace_branding=WS_BRANDING,
            app_config=APP_CONFIG,
        )
        assert result.name == 'Acme Portal'
        assert result.logo == '/ws/acme-logo.png'
        assert result.source == 'workspace'

    def test_workspace_overrides_without_app(self):
        result = resolve_login_branding(workspace_branding=WS_BRANDING)
        assert result.name == 'Acme Portal'
        assert result.logo == '/ws/acme-logo.png'
        assert result.source == 'workspace'


# =====================================================================
# Partial overrides
# =====================================================================


class TestPartialOverrides:
    def test_workspace_name_only_fills_logo_from_app(self):
        ws = WorkspaceBranding(name='Custom Name', logo='')
        result = resolve_login_branding(
            workspace_branding=ws,
            app_config=APP_CONFIG,
        )
        assert result.name == 'Custom Name'
        assert result.logo == '/assets/boring-ui-logo.svg'

    def test_workspace_logo_only_fills_name_from_app(self):
        ws = WorkspaceBranding(name='', logo='/ws/logo.png')
        result = resolve_login_branding(
            workspace_branding=ws,
            app_config=APP_CONFIG,
        )
        assert result.name == 'Boring UI'
        assert result.logo == '/ws/logo.png'

    def test_workspace_empty_falls_through_to_app(self):
        ws = WorkspaceBranding(name='', logo='')
        result = resolve_login_branding(
            workspace_branding=ws,
            app_config=APP_CONFIG,
        )
        assert result.name == 'Boring UI'
        assert result.logo == '/assets/boring-ui-logo.svg'
        assert result.source == 'app'

    def test_workspace_name_only_fills_logo_from_default(self):
        ws = WorkspaceBranding(name='Custom', logo='')
        result = resolve_login_branding(workspace_branding=ws)
        assert result.name == 'Custom'
        assert result.logo == DEFAULT_BRANDING_LOGO


# =====================================================================
# Source tracking
# =====================================================================


class TestSourceTracking:
    def test_source_default(self):
        assert resolve_login_branding().source == 'default'

    def test_source_app(self):
        assert resolve_login_branding(app_config=APP_CONFIG).source == 'app'

    def test_source_workspace(self):
        result = resolve_login_branding(
            workspace_branding=WS_BRANDING,
            app_config=APP_CONFIG,
        )
        assert result.source == 'workspace'


# =====================================================================
# Result structure
# =====================================================================


class TestLoginBrandingResult:
    def test_is_frozen(self):
        result = resolve_login_branding()
        with pytest.raises(AttributeError):
            result.name = 'changed'
