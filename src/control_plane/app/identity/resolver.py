"""Deterministic host → app_id resolver.

Bead: bd-223o.8.1 (I1)

Resolves app identity from the request hostname using an explicit
mapping table.  This is the first step in the app-config resolution
chain (design doc sections 10 and 12):

    request host → app_id → AppConfig (name, logo, default_release_id)

Design decisions:
  - Mapping is an ordered dict of ``host_pattern → app_id``.
  - Exact hostname match (case-insensitive, port stripped).
  - Fallback ``*`` wildcard entry for single-app deployments.
  - No regex/glob — deterministic and auditable.
  - Resolution result carries the matched source for diagnostics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import NamedTuple


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Branding and release metadata for a registered app.

    Corresponds to the ``GET /api/v1/app-config`` response shape
    from design doc section 11.
    """

    app_id: str
    name: str
    logo: str = ''
    default_release_id: str = ''


class AppResolution(NamedTuple):
    """Result of resolving a request host to an app identity."""

    app_id: str
    source: str  # 'exact' | 'wildcard' | 'default'
    config: AppConfig | None


class AppIdentityResolver:
    """Resolve request hostname to ``app_id`` and ``AppConfig``.

    Args:
        host_map: Mapping of hostname → app_id.  The special key ``*``
            acts as a wildcard fallback for single-app deployments.
        app_configs: Mapping of app_id → AppConfig with branding metadata.
        default_app_id: Fallback app_id when no host matches and no
            wildcard is configured.  If ``None``, unmatched hosts
            raise ``KeyError``.
    """

    def __init__(
        self,
        host_map: dict[str, str],
        app_configs: dict[str, AppConfig] | None = None,
        default_app_id: str | None = None,
    ) -> None:
        # Normalise keys to lower-case.
        self._host_map: dict[str, str] = {
            k.lower(): v for k, v in host_map.items()
        }
        self._app_configs: dict[str, AppConfig] = app_configs or {}
        self._default_app_id = default_app_id

    # ── Public API ────────────────────────────────────────────────

    def resolve(self, host: str) -> AppResolution:
        """Resolve a request host to an app identity.

        Args:
            host: The ``Host`` header value (may include port).

        Returns:
            An ``AppResolution`` with the resolved ``app_id``, the
            match source, and the ``AppConfig`` (if registered).

        Raises:
            KeyError: If no mapping matches and no default is configured.
        """
        normalised = self._strip_port(host).lower()

        # 1. Exact host match.
        app_id = self._host_map.get(normalised)
        if app_id is not None:
            return AppResolution(
                app_id=app_id,
                source='exact',
                config=self._app_configs.get(app_id),
            )

        # 2. Wildcard fallback.
        app_id = self._host_map.get('*')
        if app_id is not None:
            return AppResolution(
                app_id=app_id,
                source='wildcard',
                config=self._app_configs.get(app_id),
            )

        # 3. Default app_id (last resort).
        if self._default_app_id is not None:
            return AppResolution(
                app_id=self._default_app_id,
                source='default',
                config=self._app_configs.get(self._default_app_id),
            )

        raise KeyError(
            f'No app_id mapping for host {host!r} and no default configured'
        )

    def get_config(self, app_id: str) -> AppConfig | None:
        """Look up branding config by app_id."""
        return self._app_configs.get(app_id)

    @property
    def registered_hosts(self) -> dict[str, str]:
        """Return a copy of the host → app_id mapping."""
        return dict(self._host_map)

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _strip_port(host: str) -> str:
        """Remove port suffix from a host string.

        Handles IPv6 bracket notation (``[::1]:8080``).
        """
        if host.startswith('['):
            # IPv6 bracket notation: [::1]:port
            bracket_end = host.find(']')
            if bracket_end >= 0:
                return host[1:bracket_end]
            return host.strip('[]')

        colon = host.rfind(':')
        if colon >= 0:
            # Only strip if what follows looks like a port number.
            maybe_port = host[colon + 1:]
            if maybe_port.isdigit():
                return host[:colon]

        return host
