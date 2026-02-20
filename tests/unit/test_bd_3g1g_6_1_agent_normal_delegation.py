"""Guards for bd-3g1g.6.1 agent-normal canonical routes and delegation split."""

from boring_ui.api import create_app


def test_agent_normal_exposes_canonical_routes_and_removes_legacy_families() -> None:
    app = create_app()
    paths = [route.path for route in app.routes if hasattr(route, "path")]

    # Canonical agent-normal runtime-only families.
    assert "/api/v1/agent/normal/sessions" in paths
    assert "/api/v1/agent/normal/attachments" in paths
    assert "/ws/agent/normal/stream" in paths

    # Canonical pty-service lifecycle family (agent-normal must delegate).
    assert "/api/v1/pty/sessions" in paths

    # Legacy families must not be mounted after cutover.
    assert "/api/sessions" not in paths
    assert "/api/attachments" not in paths
    assert "/ws/claude-stream" not in paths
