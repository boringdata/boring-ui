"""Cross-cutting routing, proxy security, context resolution, and stream lifecycle tests.

Bead: bd-s7iy (E6)

Validates integration across:
  - Route ownership dispatch → workspace context resolution → proxy header sanitization
  - Dispatcher middleware request-id propagation end-to-end
  - Workspace context mismatch detection through dispatcher
  - Proxy security: strip headers + inject bearer + redact response (full pipeline)
  - Stream registry lifecycle: register → activate → close → cleanup
  - Stream per-workspace limit enforcement
  - Cross-component invariants: control routes never proxied, workspace routes always proxied
  - Request correlation: X-Request-ID flows from dispatcher through proxy headers
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from control_plane.app.routing.ownership import (
    Plane,
    RouteEntry,
    RouteMatch,
    ROUTE_TABLE,
    resolve_owner,
)
from control_plane.app.routing.context import (
    WorkspaceContext,
    WorkspaceContextMismatch,
    resolve_workspace_context,
)
from control_plane.app.routing.proxy_security import (
    ProxyHeaderConfig,
    build_proxy_config,
    redact_response_headers,
    sanitize_proxy_headers,
)
from control_plane.app.routing.stream_lifecycle import (
    StreamLifecycleError,
    StreamRegistry,
    StreamSession,
    StreamState,
    stream_proxy_sse,
)


# =====================================================================
# 1. Route ownership → context resolution pipeline
# =====================================================================


class TestOwnershipContextPipeline:
    """Route resolution feeds workspace context resolution correctly."""

    def test_workspace_route_extracts_workspace_id(self):
        match = resolve_owner('/w/ws_abc/api/v1/files/list')
        assert match is not None
        assert match.entry.plane == Plane.WORKSPACE
        assert match.workspace_id == 'ws_abc'

    def test_workspace_id_feeds_context_resolution(self):
        match = resolve_owner('/w/ws_123/app/editor')
        ctx = resolve_workspace_context(path_workspace_id=match.workspace_id)
        assert ctx.workspace_id == 'ws_123'
        assert ctx.source == 'path'

    def test_control_route_has_no_workspace_id(self):
        match = resolve_owner('/api/v1/me')
        assert match is not None
        assert match.entry.plane == Plane.CONTROL
        assert match.workspace_id is None

    def test_control_route_context_is_none(self):
        match = resolve_owner('/api/v1/me')
        ctx = resolve_workspace_context(
            path_workspace_id=match.workspace_id,
        )
        assert ctx is None

    def test_path_and_header_agree(self):
        match = resolve_owner('/w/ws_123/api/v1/files/read')
        ctx = resolve_workspace_context(
            path_workspace_id=match.workspace_id,
            header_workspace_id='ws_123',
        )
        assert ctx.workspace_id == 'ws_123'
        assert ctx.source == 'path'

    def test_path_and_header_disagree_raises(self):
        match = resolve_owner('/w/ws_123/api/v1/files/read')
        with pytest.raises(WorkspaceContextMismatch) as exc_info:
            resolve_workspace_context(
                path_workspace_id=match.workspace_id,
                header_workspace_id='ws_OTHER',
            )
        assert 'ws_123' in str(exc_info.value)
        assert 'ws_OTHER' in str(exc_info.value)


# =====================================================================
# 2. Route ownership contract invariants
# =====================================================================


class TestRouteOwnershipInvariants:
    """Cross-cutting invariants on the route table."""

    def test_all_workspace_routes_are_proxied(self):
        for entry in ROUTE_TABLE:
            if entry.plane == Plane.WORKSPACE:
                assert entry.proxied, (
                    f'Workspace route {entry.pattern!r} must be proxied'
                )

    def test_no_control_routes_are_proxied(self):
        for entry in ROUTE_TABLE:
            if entry.plane == Plane.CONTROL:
                assert not entry.proxied, (
                    f'Control route {entry.pattern!r} must not be proxied'
                )

    def test_all_workspace_routes_have_workspace_id(self):
        for entry in ROUTE_TABLE:
            if entry.plane == Plane.WORKSPACE:
                assert '{workspace_id}' in entry.pattern, (
                    f'Workspace route {entry.pattern!r} must contain '
                    '{{workspace_id}}'
                )

    def test_auth_routes_are_control_plane(self):
        match = resolve_owner('/auth/callback')
        assert match is not None
        assert match.entry.plane == Plane.CONTROL

    def test_workspaces_api_is_control_plane(self):
        match = resolve_owner('/api/v1/workspaces')
        assert match is not None
        assert match.entry.plane == Plane.CONTROL

    def test_agent_sessions_are_workspace_plane(self):
        match = resolve_owner('/w/ws_1/api/v1/agent/sessions/create')
        assert match is not None
        assert match.entry.plane == Plane.WORKSPACE
        assert match.entry.proxied

    def test_unknown_path_returns_none(self):
        match = resolve_owner('/some/unknown/path')
        assert match is None


# =====================================================================
# 3. Proxy security full pipeline
# =====================================================================


class TestProxySecurityPipeline:
    """Full proxy header pipeline: strip → inject → propagate → redact."""

    def test_full_sanitize_and_redact_cycle(self):
        config = build_proxy_config(sprite_bearer_token='secret-sprite-token')

        # Browser sends untrusted headers.
        incoming = {
            'content-type': 'application/json',
            'authorization': 'Bearer user-jwt-token',
            'x-sprite-bearer': 'should-be-stripped',
            'x-forwarded-user': 'attacker@evil.com',
            'accept': 'text/html',
        }

        sanitized = sanitize_proxy_headers(
            incoming_headers=incoming,
            config=config,
            request_id='req-001',
            session_id='sess-001',
            workspace_id='ws_abc',
        )

        # Untrusted headers stripped (browser's auth replaced by server injection).
        assert 'x-sprite-bearer' not in {k.lower() for k in sanitized}
        assert 'x-forwarded-user' not in {k.lower() for k in sanitized}

        # Safe headers preserved.
        assert sanitized.get('content-type') == 'application/json'
        assert sanitized.get('accept') == 'text/html'

        # Server-side injection replaces browser Authorization.
        assert sanitized['Authorization'] == 'Bearer secret-sprite-token'
        # The browser's JWT should NOT be present.
        assert 'Bearer user-jwt-token' not in sanitized.values()

        # Context propagation.
        assert sanitized['X-Request-ID'] == 'req-001'
        assert sanitized['X-Session-ID'] == 'sess-001'
        assert sanitized['X-Workspace-ID'] == 'ws_abc'

        # Now simulate runtime response with leaked headers.
        runtime_response = {
            'content-type': 'application/json',
            'authorization': 'Bearer secret-sprite-token',
            'x-sprite-bearer': 'leaked-token',
            'x-runtime-token': 'internal-token',
            'x-request-id': 'req-001',
        }

        redacted = redact_response_headers(runtime_response, config)

        # Sensitive headers removed.
        assert 'authorization' not in {k.lower() for k in redacted}
        assert 'x-sprite-bearer' not in {k.lower() for k in redacted}
        assert 'x-runtime-token' not in {k.lower() for k in redacted}

        # Safe headers preserved.
        assert redacted['content-type'] == 'application/json'
        assert redacted['x-request-id'] == 'req-001'

    def test_no_sprite_token_means_no_injection(self):
        config = build_proxy_config(sprite_bearer_token=None)
        sanitized = sanitize_proxy_headers(
            incoming_headers={'accept': '*/*'},
            config=config,
        )
        assert 'Authorization' not in sanitized

    def test_extra_strip_headers_applied(self):
        config = build_proxy_config(
            sprite_bearer_token='token',
            extra_strip_headers=frozenset({'x-custom-evil'}),
        )
        sanitized = sanitize_proxy_headers(
            incoming_headers={
                'accept': '*/*',
                'x-custom-evil': 'bad',
            },
            config=config,
        )
        assert 'x-custom-evil' not in {k.lower() for k in sanitized}

    def test_case_insensitive_strip(self):
        config = build_proxy_config(sprite_bearer_token='token')
        sanitized = sanitize_proxy_headers(
            incoming_headers={
                'Authorization': 'Bearer attacker-token',
                'X-Sprite-Bearer': 'injected',
            },
            config=config,
        )
        # The injected one comes from config, not browser.
        assert sanitized['Authorization'] == 'Bearer token'


# =====================================================================
# 4. Request-ID correlation across components
# =====================================================================


class TestRequestIdCorrelation:
    """X-Request-ID propagates through routing and proxy pipeline."""

    def test_request_id_propagated_to_proxy_headers(self):
        config = build_proxy_config(sprite_bearer_token='tok')
        sanitized = sanitize_proxy_headers(
            incoming_headers={'accept': '*/*'},
            config=config,
            request_id='corr-id-123',
        )
        assert sanitized['X-Request-ID'] == 'corr-id-123'

    def test_request_id_survives_response_redaction(self):
        config = build_proxy_config()
        response = {
            'x-request-id': 'corr-id-123',
            'x-sprite-bearer': 'secret',
        }
        redacted = redact_response_headers(response, config)
        assert redacted['x-request-id'] == 'corr-id-123'

    def test_request_id_absent_when_not_provided(self):
        config = build_proxy_config()
        sanitized = sanitize_proxy_headers(
            incoming_headers={},
            config=config,
        )
        assert 'X-Request-ID' not in sanitized


# =====================================================================
# 5. Workspace context precedence and conflicts
# =====================================================================


class TestWorkspaceContextPrecedence:
    """Context resolution precedence: path > header > session."""

    def test_path_wins_over_header_when_same(self):
        ctx = resolve_workspace_context(
            path_workspace_id='ws_1',
            header_workspace_id='ws_1',
        )
        assert ctx.source == 'path'

    def test_path_wins_over_session_when_same(self):
        ctx = resolve_workspace_context(
            path_workspace_id='ws_1',
            session_workspace_id='ws_1',
        )
        assert ctx.source == 'path'

    def test_header_wins_over_session_when_same(self):
        ctx = resolve_workspace_context(
            header_workspace_id='ws_1',
            session_workspace_id='ws_1',
        )
        assert ctx.source == 'header'

    def test_session_only(self):
        ctx = resolve_workspace_context(session_workspace_id='ws_1')
        assert ctx.source == 'session'

    def test_all_three_agree(self):
        ctx = resolve_workspace_context(
            path_workspace_id='ws_1',
            header_workspace_id='ws_1',
            session_workspace_id='ws_1',
        )
        assert ctx.workspace_id == 'ws_1'
        assert ctx.source == 'path'

    def test_header_and_session_disagree_raises(self):
        with pytest.raises(WorkspaceContextMismatch):
            resolve_workspace_context(
                header_workspace_id='ws_1',
                session_workspace_id='ws_2',
            )

    def test_all_three_disagree_raises(self):
        with pytest.raises(WorkspaceContextMismatch):
            resolve_workspace_context(
                path_workspace_id='ws_1',
                header_workspace_id='ws_2',
                session_workspace_id='ws_3',
            )

    def test_mismatch_includes_source_details(self):
        with pytest.raises(WorkspaceContextMismatch) as exc_info:
            resolve_workspace_context(
                path_workspace_id='ws_A',
                header_workspace_id='ws_B',
            )
        assert exc_info.value.sources == {'path': 'ws_A', 'header': 'ws_B'}

    def test_no_sources_returns_none(self):
        ctx = resolve_workspace_context()
        assert ctx is None


# =====================================================================
# 6. Stream registry lifecycle
# =====================================================================


class TestStreamRegistryLifecycle:
    """Stream sessions follow register → activate → close → cleanup."""

    def test_full_lifecycle(self):
        registry = StreamRegistry()
        session = StreamSession(workspace_id='ws_1', request_id='req-1')

        # Register.
        registry.register(session)
        assert registry.total_count == 1
        assert registry.active_count == 1
        assert session.state == StreamState.CONNECTING

        # Activate.
        session.activate()
        assert session.state == StreamState.ACTIVE
        assert session.is_active

        # Close.
        session.request_close()
        assert session.state == StreamState.CLOSING

        # Mark closed.
        session.mark_closed()
        assert session.state == StreamState.CLOSED
        assert not session.is_active

        # Cleanup.
        cleaned = registry.cleanup_closed()
        assert cleaned == 1
        assert registry.total_count == 0

    def test_unregister_marks_closed(self):
        registry = StreamRegistry()
        session = StreamSession(workspace_id='ws_1', request_id='req-1')
        registry.register(session)
        session.activate()

        removed = registry.unregister('req-1')
        assert removed is session
        assert removed.state == StreamState.CLOSED

    def test_unregister_nonexistent_returns_none(self):
        registry = StreamRegistry()
        assert registry.unregister('nonexistent') is None

    def test_workspace_stream_count(self):
        registry = StreamRegistry()
        for i in range(3):
            registry.register(StreamSession(
                workspace_id='ws_1', request_id=f'req-{i}',
            ))
        registry.register(StreamSession(
            workspace_id='ws_2', request_id='req-other',
        ))

        assert registry.workspace_count('ws_1') == 3
        assert registry.workspace_count('ws_2') == 1
        assert registry.workspace_count('ws_3') == 0


# =====================================================================
# 7. Stream per-workspace limit
# =====================================================================


class TestStreamWorkspaceLimit:
    """Registry enforces per-workspace stream limits."""

    def test_limit_enforced(self):
        registry = StreamRegistry(max_streams_per_workspace=3)
        for i in range(3):
            registry.register(StreamSession(
                workspace_id='ws_1', request_id=f'req-{i}',
            ))

        with pytest.raises(StreamLifecycleError, match='stream limit'):
            registry.register(StreamSession(
                workspace_id='ws_1', request_id='req-overflow',
            ))

    def test_different_workspace_not_affected(self):
        registry = StreamRegistry(max_streams_per_workspace=2)
        for i in range(2):
            registry.register(StreamSession(
                workspace_id='ws_1', request_id=f'ws1-{i}',
            ))

        # ws_2 should not be affected by ws_1 limit.
        registry.register(StreamSession(
            workspace_id='ws_2', request_id='ws2-0',
        ))
        assert registry.workspace_count('ws_2') == 1

    def test_unregister_frees_capacity(self):
        registry = StreamRegistry(max_streams_per_workspace=2)
        for i in range(2):
            registry.register(StreamSession(
                workspace_id='ws_1', request_id=f'req-{i}',
            ))

        registry.unregister('req-0')
        # Should now have room.
        registry.register(StreamSession(
            workspace_id='ws_1', request_id='req-new',
        ))
        assert registry.workspace_count('ws_1') == 2

    def test_duplicate_request_id_raises(self):
        registry = StreamRegistry()
        registry.register(StreamSession(
            workspace_id='ws_1', request_id='req-dup',
        ))
        with pytest.raises(StreamLifecycleError, match='already registered'):
            registry.register(StreamSession(
                workspace_id='ws_1', request_id='req-dup',
            ))


# =====================================================================
# 8. Stream state machine transitions
# =====================================================================


class TestStreamStateMachine:
    """StreamSession enforces valid state transitions."""

    def test_activate_from_connecting(self):
        session = StreamSession(workspace_id='ws_1', request_id='r')
        session.activate()
        assert session.state == StreamState.ACTIVE

    def test_activate_from_active_raises(self):
        session = StreamSession(workspace_id='ws_1', request_id='r')
        session.activate()
        with pytest.raises(StreamLifecycleError, match='Cannot activate'):
            session.activate()

    def test_request_close_idempotent_on_closed(self):
        session = StreamSession(workspace_id='ws_1', request_id='r')
        session.mark_closed()
        # Should not raise.
        session.request_close()
        assert session.state == StreamState.CLOSED

    def test_duration_is_positive(self):
        session = StreamSession(workspace_id='ws_1', request_id='r')
        assert session.duration_seconds >= 0

    @pytest.mark.asyncio
    async def test_wait_for_cancel_returns_true_when_cancelled(self):
        session = StreamSession(workspace_id='ws_1', request_id='r')
        session.request_close()
        result = await session.wait_for_cancel(timeout=1.0)
        assert result is True

    @pytest.mark.asyncio
    async def test_wait_for_cancel_timeout(self):
        session = StreamSession(workspace_id='ws_1', request_id='r')
        result = await session.wait_for_cancel(timeout=0.01)
        assert result is False


# =====================================================================
# 9. Close workspace streams
# =====================================================================


class TestCloseWorkspaceStreams:
    """close_workspace_streams signals all streams for a workspace."""

    def test_close_signals_active_streams(self):
        registry = StreamRegistry()
        sessions = []
        for i in range(3):
            s = StreamSession(workspace_id='ws_1', request_id=f'req-{i}')
            registry.register(s)
            s.activate()
            sessions.append(s)

        count = registry.close_workspace_streams('ws_1')
        assert count == 3
        for s in sessions:
            assert s.state == StreamState.CLOSING

    def test_close_ignores_other_workspaces(self):
        registry = StreamRegistry()
        s1 = StreamSession(workspace_id='ws_1', request_id='r1')
        s2 = StreamSession(workspace_id='ws_2', request_id='r2')
        registry.register(s1)
        registry.register(s2)
        s1.activate()
        s2.activate()

        count = registry.close_workspace_streams('ws_1')
        assert count == 1
        assert s1.state == StreamState.CLOSING
        assert s2.state == StreamState.ACTIVE

    def test_close_skips_already_closed(self):
        registry = StreamRegistry()
        s = StreamSession(workspace_id='ws_1', request_id='r1')
        registry.register(s)
        s.mark_closed()

        count = registry.close_workspace_streams('ws_1')
        assert count == 0


# =====================================================================
# 10. SSE proxy stream integration
# =====================================================================


class TestSSEProxyStream:
    """stream_proxy_sse yields chunks and handles lifecycle."""

    @pytest.mark.asyncio
    async def test_yields_upstream_chunks(self):
        session = StreamSession(workspace_id='ws_1', request_id='r1')
        chunks = [b'data: hello\n\n', b'data: world\n\n']

        async def upstream():
            for c in chunks:
                yield c

        collected = []
        async for chunk in stream_proxy_sse(upstream(), session):
            collected.append(chunk)

        assert collected == chunks
        assert session.state == StreamState.CLOSED

    @pytest.mark.asyncio
    async def test_session_activated_during_proxy(self):
        session = StreamSession(workspace_id='ws_1', request_id='r1')

        async def upstream():
            yield b'data: test\n\n'

        async for _ in stream_proxy_sse(upstream(), session):
            pass

        # Session should have been activated then closed.
        assert session.state == StreamState.CLOSED

    @pytest.mark.asyncio
    async def test_stops_when_session_closed(self):
        session = StreamSession(workspace_id='ws_1', request_id='r1')
        yielded = 0

        async def upstream():
            nonlocal yielded
            for i in range(100):
                yielded += 1
                if i == 2:
                    session.request_close()
                yield f'data: chunk-{i}\n\n'.encode()

        collected = []
        async for chunk in stream_proxy_sse(upstream(), session):
            collected.append(chunk)

        # Should have stopped after close was requested.
        assert len(collected) <= 4  # May get a few before is_active check.
        assert session.state == StreamState.CLOSED

    @pytest.mark.asyncio
    async def test_empty_upstream(self):
        session = StreamSession(workspace_id='ws_1', request_id='r1')

        async def upstream():
            return
            yield  # Make it an async generator.

        collected = []
        async for chunk in stream_proxy_sse(upstream(), session):
            collected.append(chunk)

        assert collected == []
        assert session.state == StreamState.CLOSED


# =====================================================================
# 11. Proxy config frozen invariants
# =====================================================================


class TestProxyConfigInvariants:

    def test_proxy_config_frozen(self):
        config = build_proxy_config(sprite_bearer_token='tok')
        with pytest.raises(AttributeError):
            config.strip_headers = frozenset()

    def test_route_entry_frozen(self):
        entry = ROUTE_TABLE[0]
        with pytest.raises(AttributeError):
            entry.plane = Plane.WORKSPACE

    def test_workspace_context_frozen(self):
        ctx = WorkspaceContext(workspace_id='ws_1', source='path')
        with pytest.raises(AttributeError):
            ctx.workspace_id = 'ws_2'


# =====================================================================
# 12. Proxy security → ownership integration
# =====================================================================


class TestProxySecurityOwnership:
    """Proxy headers are only needed for workspace-plane routes."""

    def test_workspace_route_needs_proxy_headers(self):
        match = resolve_owner('/w/ws_abc/api/v1/files/list')
        assert match.entry.proxied
        # Proxy headers should be built for this route.
        config = build_proxy_config(sprite_bearer_token='sprite-tok')
        headers = sanitize_proxy_headers(
            incoming_headers={'accept': '*/*'},
            config=config,
            request_id='req-001',
            workspace_id=match.workspace_id,
        )
        assert headers['Authorization'] == 'Bearer sprite-tok'
        assert headers['X-Workspace-ID'] == 'ws_abc'
        assert headers['X-Request-ID'] == 'req-001'

    def test_control_route_should_not_use_proxy_headers(self):
        match = resolve_owner('/api/v1/me')
        assert not match.entry.proxied
        # Control routes don't need Sprite bearer injection.

    def test_all_identity_headers_stripped_from_proxy(self):
        config = build_proxy_config(sprite_bearer_token='tok')
        attack_headers = {
            'authorization': 'Bearer stolen-jwt',
            'x-forwarded-user': 'admin@corp.com',
            'x-forwarded-email': 'admin@corp.com',
            'x-forwarded-groups': 'superadmin',
            'x-workspace-owner': 'attacker',
            'x-runtime-token': 'stolen-runtime',
            'x-sprite-bearer': 'stolen-sprite',
            'x-service-role': 'service_role',
            'x-supabase-auth': 'stolen-supabase',
            'accept': '*/*',
        }
        sanitized = sanitize_proxy_headers(
            incoming_headers=attack_headers,
            config=config,
        )
        # Only safe headers and injected auth remain.
        lower_keys = {k.lower() for k in sanitized}
        assert 'x-forwarded-user' not in lower_keys
        assert 'x-forwarded-email' not in lower_keys
        assert 'x-forwarded-groups' not in lower_keys
        assert 'x-workspace-owner' not in lower_keys
        assert 'x-runtime-token' not in lower_keys
        assert 'x-sprite-bearer' not in lower_keys
        assert 'x-service-role' not in lower_keys
        assert 'x-supabase-auth' not in lower_keys
        # The only authorization is the server-injected one.
        assert sanitized['Authorization'] == 'Bearer tok'
        assert sanitized['accept'] == '*/*'
