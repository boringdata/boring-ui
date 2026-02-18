"""Guards for bd-3g1g.6.3 agent-pi runtime-only surface.

PI is allowed to own its session/history/stream lifecycle endpoints, but must not
expose direct workspace-core or PTY ownership endpoints.
"""

from __future__ import annotations

from pathlib import Path


def test_pi_service_surface_is_canonical_and_runtime_only() -> None:
    source = Path("src/pi_service/server.mjs").read_text(encoding="utf-8")

    # Canonical PI runtime family.
    assert "/api/v1/agent/pi/sessions" in source

    # Legacy PI family must not be present after cutover.
    assert "/api/sessions" not in source

    # Agent services must not directly own workspace-core or PTY surfaces.
    forbidden = [
        "/api/v1/files",
        "/api/v1/git",
        "/api/v1/pty",
        "/ws/pty",
        "/api/fs",
        "/api/git",
        "/api/envs",
    ]
    for needle in forbidden:
        assert needle not in source

