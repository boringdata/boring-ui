"""Login branding precedence chain.

Bead: bd-223o.8.4 (I4)

Resolves branding parameters (name, logo) for the login page using
a three-level precedence chain (design doc section 10, point 7):

    1. Workspace runtime config ``login_branding`` (if workspace context)
    2. App default config from ``AppConfig``
    3. Hardcoded fallback (``name="App"``, empty logo)

Each level is checked in order; the first non-empty value wins
for each individual field (name, logo).  This allows partial
overrides at any level.
"""

from __future__ import annotations

from dataclasses import dataclass

from control_plane.app.identity.resolver import AppConfig

# ── Hardcoded fallback (level 3) ──────────────────────────────────────

DEFAULT_BRANDING_NAME = 'App'
DEFAULT_BRANDING_LOGO = ''


@dataclass(frozen=True, slots=True)
class LoginBranding:
    """Resolved branding for the login page."""

    name: str
    logo: str
    source: str  # 'workspace' | 'app' | 'default'


@dataclass(frozen=True, slots=True)
class WorkspaceBranding:
    """Branding overrides from workspace runtime config.

    Stored in ``cloud.workspace_runtime.config.login_branding``.
    Fields may be empty to indicate "no override at this level".
    """

    name: str = ''
    logo: str = ''


def resolve_login_branding(
    *,
    workspace_branding: WorkspaceBranding | None = None,
    app_config: AppConfig | None = None,
) -> LoginBranding:
    """Resolve login branding using the three-level precedence chain.

    Args:
        workspace_branding: Optional branding from workspace runtime config.
        app_config: Optional app-level branding from ``AppConfig``.

    Returns:
        A ``LoginBranding`` with the resolved name, logo, and source.
    """
    # Level 1: Workspace runtime config.
    if workspace_branding is not None:
        name = workspace_branding.name
        logo = workspace_branding.logo
        if name and logo:
            return LoginBranding(name=name, logo=logo, source='workspace')
        # Partial override — fill gaps from lower levels.
        if not name:
            name = _app_name(app_config)
        if not logo:
            logo = _app_logo(app_config)
        return LoginBranding(
            name=name, logo=logo,
            source='workspace' if workspace_branding.name or workspace_branding.logo else _source(app_config),
        )

    # Level 2: App default config.
    if app_config is not None:
        name = app_config.name or DEFAULT_BRANDING_NAME
        logo = app_config.logo or DEFAULT_BRANDING_LOGO
        return LoginBranding(
            name=name, logo=logo,
            source='app' if app_config.name or app_config.logo else 'default',
        )

    # Level 3: Hardcoded fallback.
    return LoginBranding(
        name=DEFAULT_BRANDING_NAME,
        logo=DEFAULT_BRANDING_LOGO,
        source='default',
    )


def _app_name(config: AppConfig | None) -> str:
    if config and config.name:
        return config.name
    return DEFAULT_BRANDING_NAME


def _app_logo(config: AppConfig | None) -> str:
    if config and config.logo:
        return config.logo
    return DEFAULT_BRANDING_LOGO


def _source(config: AppConfig | None) -> str:
    if config and (config.name or config.logo):
        return 'app'
    return 'default'
