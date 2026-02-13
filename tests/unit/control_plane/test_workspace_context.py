"""Tests for workspace context resolution and mismatch detection.

Validates precedence rules and conflict handling from Feature 3 design doc
section 11 (session context rules).
"""

import pytest

from control_plane.app.routing.context import (
    WorkspaceContext,
    WorkspaceContextMismatch,
    resolve_workspace_context,
)


class TestResolvePrecedence:
    """Workspace context precedence: path > header > session."""

    def test_path_wins_over_header_and_session(self):
        ctx = resolve_workspace_context(
            path_workspace_id='ws_path',
            header_workspace_id='ws_path',
            session_workspace_id='ws_path',
        )
        assert ctx is not None
        assert ctx.workspace_id == 'ws_path'
        assert ctx.source == 'path'

    def test_header_wins_over_session(self):
        ctx = resolve_workspace_context(
            header_workspace_id='ws_header',
            session_workspace_id='ws_header',
        )
        assert ctx is not None
        assert ctx.workspace_id == 'ws_header'
        assert ctx.source == 'header'

    def test_session_used_when_alone(self):
        ctx = resolve_workspace_context(session_workspace_id='ws_session')
        assert ctx is not None
        assert ctx.workspace_id == 'ws_session'
        assert ctx.source == 'session'

    def test_path_only(self):
        ctx = resolve_workspace_context(path_workspace_id='ws_123')
        assert ctx is not None
        assert ctx.workspace_id == 'ws_123'
        assert ctx.source == 'path'

    def test_header_only(self):
        ctx = resolve_workspace_context(header_workspace_id='ws_456')
        assert ctx is not None
        assert ctx.workspace_id == 'ws_456'
        assert ctx.source == 'header'


class TestNoContext:
    """When no sources provide a workspace_id, result is None."""

    def test_all_none_returns_none(self):
        ctx = resolve_workspace_context()
        assert ctx is None

    def test_explicit_none_returns_none(self):
        ctx = resolve_workspace_context(
            path_workspace_id=None,
            header_workspace_id=None,
            session_workspace_id=None,
        )
        assert ctx is None


class TestMismatchDetection:
    """Multiple sources with different workspace_ids must raise."""

    def test_path_header_mismatch(self):
        with pytest.raises(WorkspaceContextMismatch) as exc_info:
            resolve_workspace_context(
                path_workspace_id='ws_a',
                header_workspace_id='ws_b',
            )
        assert 'ws_a' in str(exc_info.value)
        assert 'ws_b' in str(exc_info.value)
        assert exc_info.value.sources == {'path': 'ws_a', 'header': 'ws_b'}

    def test_path_session_mismatch(self):
        with pytest.raises(WorkspaceContextMismatch):
            resolve_workspace_context(
                path_workspace_id='ws_a',
                session_workspace_id='ws_c',
            )

    def test_header_session_mismatch(self):
        with pytest.raises(WorkspaceContextMismatch):
            resolve_workspace_context(
                header_workspace_id='ws_x',
                session_workspace_id='ws_y',
            )

    def test_triple_mismatch(self):
        with pytest.raises(WorkspaceContextMismatch) as exc_info:
            resolve_workspace_context(
                path_workspace_id='ws_1',
                header_workspace_id='ws_2',
                session_workspace_id='ws_3',
            )
        assert len(exc_info.value.sources) == 3

    def test_two_agree_one_disagrees(self):
        with pytest.raises(WorkspaceContextMismatch):
            resolve_workspace_context(
                path_workspace_id='ws_same',
                header_workspace_id='ws_same',
                session_workspace_id='ws_different',
            )


class TestAgreementAcrossSources:
    """All sources agree — no mismatch, highest precedence source wins."""

    def test_path_and_header_agree(self):
        ctx = resolve_workspace_context(
            path_workspace_id='ws_ok',
            header_workspace_id='ws_ok',
        )
        assert ctx is not None
        assert ctx.workspace_id == 'ws_ok'
        assert ctx.source == 'path'

    def test_all_three_agree(self):
        ctx = resolve_workspace_context(
            path_workspace_id='ws_all',
            header_workspace_id='ws_all',
            session_workspace_id='ws_all',
        )
        assert ctx is not None
        assert ctx.workspace_id == 'ws_all'
        assert ctx.source == 'path'
