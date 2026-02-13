"""Unit tests for control-plane app factory.

Bead: bd-1joj.1 (CP0)

Tests:
  1. create_app() with test config returns working ASGI app
  2. Key routers are registered (auth/me/app-config/workspaces/members/session/provisioning/shares)
  3. Middleware ordering (auth guard before dispatch/proxy)
  4. InMemory mode selected for ENVIRONMENT=local
  5. Supabase mode required for ENVIRONMENT=staging/production
  6. Request-ID generation and propagation
  7. Auth guard blocks unauthenticated requests
  8. Auth guard allows allowlisted paths
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure src is on path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from control_plane.app.main import create_app, AUTH_ALLOWLIST_EXACT, AUTH_ALLOWLIST_PREFIX
from control_plane.app.settings import ControlPlaneSettings
from control_plane.app.inmemory import (
    InMemoryWorkspaceRepository,
    InMemoryMemberRepository,
    InMemorySessionRepository,
    InMemoryShareRepository,
    InMemoryAuditEmitter,
    InMemoryJobRepository,
    InMemoryRuntimeMetadataStore,
    InMemorySandboxProvider,
)


def _local_settings(**overrides) -> ControlPlaneSettings:
    defaults = {"environment": "local"}
    defaults.update(overrides)
    return ControlPlaneSettings(**defaults)


def _staging_settings(**overrides) -> ControlPlaneSettings:
    defaults = {
        "environment": "staging",
        "supabase_url": "https://test.supabase.co",
        "supabase_service_role_key": "test-key-not-real",
        "session_secret": "a" * 32,
    }
    defaults.update(overrides)
    return ControlPlaneSettings(**defaults)


def _all_inmemory_repos():
    return dict(
        workspace_repo=InMemoryWorkspaceRepository(),
        member_repo=InMemoryMemberRepository(),
        session_repo=InMemorySessionRepository(),
        share_repo=InMemoryShareRepository(),
        audit_emitter=InMemoryAuditEmitter(),
        job_repo=InMemoryJobRepository(),
        runtime_store=InMemoryRuntimeMetadataStore(),
        sandbox_provider=InMemorySandboxProvider(),
    )


# ── Test 1: create_app returns working ASGI app ────────────────


class TestCreateApp:
    def test_returns_fastapi_app(self):
        app = create_app(_local_settings())
        assert app is not None
        assert app.title == "Boring UI Control Plane"

    def test_health_endpoint(self):
        app = create_app(_local_settings())
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["environment"] == "local"

    def test_settings_stored_on_state(self):
        settings = _local_settings()
        app = create_app(settings)
        assert app.state.settings is settings

    def test_deps_stored_on_state(self):
        app = create_app(_local_settings())
        deps = app.state.deps
        assert deps is not None
        assert deps.workspace_repo is not None


# ── Test 2: Key routers are registered ──────────────────────────


class TestRouterRegistration:
    """Verify all section 5.3 + 11 routes are present."""

    EXPECTED_ROUTES = [
        ("POST", "/auth/login"),
        ("GET", "/auth/callback"),
        ("GET", "/api/v1/app-config"),
        ("GET", "/api/v1/me"),
        ("GET", "/api/v1/workspaces"),
        ("POST", "/api/v1/workspaces"),
        ("GET", "/api/v1/workspaces/{workspace_id}"),
        ("PATCH", "/api/v1/workspaces/{workspace_id}"),
        ("POST", "/api/v1/workspaces/{workspace_id}/members"),
        ("GET", "/api/v1/workspaces/{workspace_id}/members"),
        ("DELETE", "/api/v1/workspaces/{workspace_id}/members/{member_id}"),
        ("POST", "/api/v1/session/workspace"),
        ("GET", "/api/v1/workspaces/{workspace_id}/runtime"),
        ("POST", "/api/v1/workspaces/{workspace_id}/retry"),
        ("POST", "/api/v1/workspaces/{workspace_id}/shares"),
        ("DELETE", "/api/v1/workspaces/{workspace_id}/shares/{share_id}"),
        ("GET", "/api/v1/shares/{token}"),
        ("PUT", "/api/v1/shares/{token}"),
        ("GET", "/health"),
    ]

    def test_all_expected_routes_registered(self):
        app = create_app(_local_settings())
        registered = set()
        for route in app.routes:
            if hasattr(route, "methods") and hasattr(route, "path"):
                for method in route.methods:
                    registered.add((method, route.path))

        for method, path in self.EXPECTED_ROUTES:
            assert (method, path) in registered, (
                f"Route {method} {path} not registered. "
                f"Registered routes: {sorted(registered)}"
            )


# ── Test 3: Middleware ordering ─────────────────────────────────


class TestMiddlewareOrdering:
    """Auth guard must run after request-ID (so 401 includes request_id)."""

    def test_unauthenticated_request_includes_request_id(self):
        app = create_app(_local_settings())
        client = TestClient(app)
        resp = client.get("/api/v1/me")
        assert resp.status_code == 401
        data = resp.json()
        # request_id should be present because RequestIDMiddleware ran first
        assert "request_id" in data
        assert data["request_id"] != "unknown"
        # X-Request-ID header should also be set
        assert "x-request-id" in resp.headers

    def test_request_id_propagated_on_success(self):
        app = create_app(_local_settings())
        client = TestClient(app)
        custom_id = "test-req-12345"
        resp = client.get("/health", headers={"X-Request-ID": custom_id})
        assert resp.headers["x-request-id"] == custom_id


# ── Test 4: InMemory mode for ENVIRONMENT=local ────────────────


class TestLocalMode:
    def test_local_uses_inmemory_by_default(self):
        app = create_app(_local_settings())
        deps = app.state.deps
        assert isinstance(deps.workspace_repo, InMemoryWorkspaceRepository)
        assert isinstance(deps.member_repo, InMemoryMemberRepository)
        assert isinstance(deps.session_repo, InMemorySessionRepository)
        assert isinstance(deps.share_repo, InMemoryShareRepository)
        assert isinstance(deps.audit_emitter, InMemoryAuditEmitter)
        assert isinstance(deps.job_repo, InMemoryJobRepository)
        assert isinstance(deps.runtime_store, InMemoryRuntimeMetadataStore)
        assert isinstance(deps.sandbox_provider, InMemorySandboxProvider)

    def test_local_allows_custom_repo_override(self):
        custom_repo = InMemoryWorkspaceRepository()
        app = create_app(_local_settings(), workspace_repo=custom_repo)
        assert app.state.deps.workspace_repo is custom_repo

    def test_default_settings_is_local(self):
        app = create_app()
        assert app.state.settings.is_local


# ── Test 5: Supabase required for non-local ─────────────────────


class TestNonLocalMode:
    def test_staging_requires_all_repos(self):
        settings = _staging_settings()
        with pytest.raises(ValueError, match="Non-local environment"):
            create_app(settings)

    def test_staging_with_all_repos_succeeds(self):
        settings = _staging_settings()
        app = create_app(settings, **_all_inmemory_repos())
        assert app is not None
        assert app.state.settings.environment == "staging"

    def test_staging_missing_single_repo_names_it(self):
        settings = _staging_settings()
        repos = _all_inmemory_repos()
        del repos["job_repo"]
        with pytest.raises(ValueError, match="job_repo"):
            create_app(settings, **repos)

    def test_production_requires_long_session_secret(self):
        with pytest.raises(ValueError, match="session_secret"):
            create_app(ControlPlaneSettings(
                environment="production",
                supabase_url="https://x.supabase.co",
                supabase_service_role_key="key",
                session_secret="short",
            ))

    def test_staging_requires_supabase_url(self):
        with pytest.raises(ValueError, match="supabase_url"):
            create_app(ControlPlaneSettings(
                environment="staging",
                supabase_url="",
                supabase_service_role_key="key",
                session_secret="a" * 32,
            ))


# ── Test 6: Request-ID middleware ────────────────────────────────


class TestRequestIDMiddleware:
    def test_generates_request_id(self):
        app = create_app(_local_settings())
        client = TestClient(app)
        resp = client.get("/health")
        assert "x-request-id" in resp.headers
        # Should be a valid UUID
        rid = resp.headers["x-request-id"]
        assert len(rid) == 36  # UUID format

    def test_propagates_existing_request_id(self):
        app = create_app(_local_settings())
        client = TestClient(app)
        resp = client.get("/health", headers={"X-Request-ID": "my-trace-123"})
        assert resp.headers["x-request-id"] == "my-trace-123"


# ── Test 7: Auth guard blocks unauthenticated ────────────────────


class TestAuthGuard:
    def test_blocks_protected_route_without_auth(self):
        app = create_app(_local_settings())
        client = TestClient(app)
        resp = client.get("/api/v1/me")
        assert resp.status_code == 401
        data = resp.json()
        assert data["code"] == "AUTH_REQUIRED"

    def test_allows_with_bearer_token(self):
        app = create_app(_local_settings())
        client = TestClient(app)
        resp = client.get(
            "/api/v1/me",
            headers={"Authorization": "Bearer test-token"},
        )
        # Should pass auth guard (501 from stub, not 401)
        assert resp.status_code == 501

    def test_allows_with_cookie(self):
        app = create_app(_local_settings())
        client = TestClient(app, cookies={"sb-access-token": "test"})
        resp = client.get("/api/v1/me")
        assert resp.status_code == 501  # Passes guard, hits stub


# ── Test 8: Auth guard allows allowlisted paths ──────────────────


class TestAuthGuardAllowlist:
    def test_health_allowed_without_auth(self):
        app = create_app(_local_settings())
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_auth_login_allowed_without_auth(self):
        app = create_app(_local_settings())
        client = TestClient(app)
        resp = client.post("/auth/login")
        # 501 from stub, not 401 from guard
        assert resp.status_code == 501

    def test_auth_callback_allowed_without_auth(self):
        app = create_app(_local_settings())
        client = TestClient(app)
        resp = client.get("/auth/callback")
        assert resp.status_code == 501

    def test_app_config_allowed_without_auth(self):
        app = create_app(_local_settings())
        client = TestClient(app)
        resp = client.get("/api/v1/app-config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["environment"] == "local"


# ── Settings tests ───────────────────────────────────────────────


class TestControlPlaneSettings:
    def test_is_local_property(self):
        assert ControlPlaneSettings(environment="local").is_local
        assert not ControlPlaneSettings(environment="staging").is_local

    def test_validate_local_always_passes(self):
        settings = ControlPlaneSettings(environment="local")
        assert settings.validate() == []

    def test_validate_staging_missing_fields(self):
        settings = ControlPlaneSettings(environment="staging")
        errors = settings.validate()
        assert len(errors) >= 2  # supabase_url + supabase_service_role_key + session_secret

    def test_from_env(self):
        env = {
            "ENVIRONMENT": "staging",
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "secret",
            "SUPABASE_PUBLISHABLE_KEY": "pub",
            "SESSION_SECRET": "x" * 32,
            "SPRITE_BEARER_TOKEN": "sprite-token",
            "CORS_ORIGINS": "https://app.example.com,https://dev.example.com",
            "HOST_APP_ID_MAP": "app.example.com=boring-ui,dev.example.com=boring-ui-dev",
        }
        settings = ControlPlaneSettings.from_env(env)
        assert settings.environment == "staging"
        assert settings.supabase_url == "https://test.supabase.co"
        assert settings.cors_origins == ("https://app.example.com", "https://dev.example.com")
        assert settings.host_app_id_map["app.example.com"] == "boring-ui"
        assert settings.host_app_id_map["dev.example.com"] == "boring-ui-dev"

    def test_host_app_id_map_is_immutable(self):
        """H3: host_app_id_map should not allow mutation after construction."""
        settings = ControlPlaneSettings.from_env({
            "HOST_APP_ID_MAP": "a.com=app1",
        })
        with pytest.raises(TypeError):
            settings.host_app_id_map["evil.com"] = "hijack"  # type: ignore[index]


# ── Protocol conformance tests ───────────────────────────────────


class TestProtocolConformance:
    """T7: Verify InMemory classes satisfy their runtime-checkable protocols."""

    def test_workspace_repo_protocol(self):
        from control_plane.app.protocols import WorkspaceRepository
        assert isinstance(InMemoryWorkspaceRepository(), WorkspaceRepository)

    def test_member_repo_protocol(self):
        from control_plane.app.protocols import MemberRepository
        assert isinstance(InMemoryMemberRepository(), MemberRepository)

    def test_session_repo_protocol(self):
        from control_plane.app.protocols import SessionRepository
        assert isinstance(InMemorySessionRepository(), SessionRepository)

    def test_share_repo_protocol(self):
        from control_plane.app.protocols import ShareRepository
        assert isinstance(InMemoryShareRepository(), ShareRepository)

    def test_audit_emitter_protocol(self):
        from control_plane.app.protocols import AuditEmitter
        assert isinstance(InMemoryAuditEmitter(), AuditEmitter)

    def test_job_repo_protocol(self):
        from control_plane.app.protocols import JobRepository
        assert isinstance(InMemoryJobRepository(), JobRepository)

    def test_runtime_store_protocol(self):
        from control_plane.app.protocols import RuntimeMetadataStore
        assert isinstance(InMemoryRuntimeMetadataStore(), RuntimeMetadataStore)

    def test_sandbox_provider_protocol(self):
        from control_plane.app.protocols import SandboxProvider
        assert isinstance(InMemorySandboxProvider(), SandboxProvider)


# ── Auth guard boundary tests ────────────────────────────────────


class TestAuthGuardBoundary:
    """M1: Ensure allowlist doesn't leak to similar-prefix paths."""

    def test_app_config_suffix_requires_auth(self):
        """Exact-match: /api/v1/app-config-internal should NOT be allowlisted."""
        app = create_app(_local_settings())
        client = TestClient(app)
        resp = client.get("/api/v1/app-config-internal")
        # Should be blocked by auth guard (401), not allowlisted
        assert resp.status_code == 401

    def test_health_suffix_requires_auth(self):
        """Exact-match: /healthz or /health/debug should NOT be allowlisted."""
        app = create_app(_local_settings())
        client = TestClient(app)
        resp = client.get("/healthz")
        assert resp.status_code in (401, 404)  # blocked or not found

    def test_options_preflight_always_allowed(self):
        """T1: OPTIONS requests bypass auth guard."""
        app = create_app(_local_settings())
        client = TestClient(app)
        resp = client.options("/api/v1/workspaces")
        # Should not be 401
        assert resp.status_code != 401


# ── AppDependencies immutability test ────────────────────────────


class TestAppDependenciesImmutable:
    """L5: AppDependencies should be frozen."""

    def test_cannot_reassign_repo(self):
        app = create_app(_local_settings())
        with pytest.raises(AttributeError):
            app.state.deps.workspace_repo = "malicious"  # type: ignore
