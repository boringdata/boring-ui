"""Control plane configuration settings.

Bead: bd-1joj.1 (CP0)

ControlPlaneSettings is the single configuration object accepted by create_app().
It is intentionally a plain dataclass (not env-coupled) so tests can inject config
without touching os.environ.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True, slots=True)
class ControlPlaneSettings:
    """Configuration for the control-plane FastAPI application.

    All fields have sensible defaults for local development.
    Non-local environments must supply real values for supabase_url,
    supabase_service_role_key, and session_secret.
    """

    # ── Environment ────────────────────────────────────────────────
    environment: str = "local"
    """One of: local, dev, staging, production."""

    # ── Supabase ───────────────────────────────────────────────────
    supabase_url: str = ""
    """Supabase project URL (e.g. https://xyz.supabase.co)."""

    supabase_service_role_key: str = ""
    """Supabase service-role key for PostgREST calls. Never log this."""

    supabase_publishable_key: str = ""
    """Supabase anon/publishable key (safe for /auth/login UI redirect)."""

    # ── Session / Auth ─────────────────────────────────────────────
    session_secret: str = ""
    """Secret used to sign session cookies. Must be >=32 chars in non-local."""

    # ── Sprite ─────────────────────────────────────────────────────
    sprite_bearer_token: str = ""
    """Static bearer token for Sprite API calls."""

    # ── CORS ───────────────────────────────────────────────────────
    cors_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://localhost:3000",
    )
    """Allowed CORS origins."""

    # ── Host / App identity ────────────────────────────────────────
    host_app_id_map: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))
    """Immutable mapping of hostname -> app_id for multi-tenant host resolution."""

    @property
    def is_local(self) -> bool:
        return self.environment == "local"

    def validate(self) -> list[str]:
        """Return a list of configuration errors. Empty means valid."""
        errors: list[str] = []
        if not self.is_local:
            if not self.supabase_url:
                errors.append(f"{self.environment}: supabase_url is required")
            if not self.supabase_service_role_key:
                errors.append(
                    f"{self.environment}: supabase_service_role_key is required"
                )
            if not self.session_secret or len(self.session_secret) < 32:
                errors.append(
                    f"{self.environment}: session_secret must be >= 32 characters"
                )
        return errors

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> ControlPlaneSettings:
        """Build settings from environment variables.

        This is a convenience factory for production use. Tests should
        construct ControlPlaneSettings directly.
        """
        if env is None:
            env = dict(os.environ)

        cors_raw = env.get("CORS_ORIGINS", "")
        cors = tuple(o.strip() for o in cors_raw.split(",") if o.strip()) if cors_raw else cls.cors_origins

        host_map_raw = env.get("HOST_APP_ID_MAP", "")
        host_map: dict[str, str] = {}
        if host_map_raw:
            for pair in host_map_raw.split(","):
                if "=" in pair:
                    host, app_id = pair.split("=", 1)
                    host_map[host.strip()] = app_id.strip()

        return cls(
            environment=env.get("ENVIRONMENT", "local"),
            supabase_url=env.get("SUPABASE_URL", ""),
            supabase_service_role_key=env.get("SUPABASE_SERVICE_ROLE_KEY", ""),
            supabase_publishable_key=env.get("SUPABASE_PUBLISHABLE_KEY", ""),
            session_secret=env.get("SESSION_SECRET", ""),
            sprite_bearer_token=env.get("SPRITE_BEARER_TOKEN", ""),
            cors_origins=cors,
            host_app_id_map=MappingProxyType(host_map),
        )
