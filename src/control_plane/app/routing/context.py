"""Workspace context resolution and mismatch detection.

Implements the workspace resolution precedence from Feature 3 design doc
section 11 (session context rules):

  1. workspace_id from URL path (``/w/{workspace_id}/...``)
  2. ``X-Workspace-ID`` header (only on endpoints that allow it)
  3. active workspace in user session

Conflict rule: if multiple sources provide a workspace_id and they
disagree, return 400 ``workspace_context_mismatch``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkspaceContext:
    """Resolved workspace identity for a single request.

    Attributes:
        workspace_id: The resolved workspace identifier.
        source: Which source provided the value (``path``, ``header``,
                ``session``).
    """

    workspace_id: str
    source: str  # 'path' | 'header' | 'session'


class WorkspaceContextMismatch(Exception):
    """Raised when multiple workspace sources disagree.

    Attributes:
        sources: Mapping of source name to provided workspace_id.
    """

    def __init__(self, sources: dict[str, str]) -> None:
        self.sources = sources
        conflicting = ', '.join(f'{k}={v}' for k, v in sorted(sources.items()))
        super().__init__(f'workspace_context_mismatch: {conflicting}')


def resolve_workspace_context(
    *,
    path_workspace_id: str | None = None,
    header_workspace_id: str | None = None,
    session_workspace_id: str | None = None,
) -> WorkspaceContext | None:
    """Resolve the effective workspace context for a request.

    Follows the precedence rules in the design contract:

    1. URL path ``workspace_id`` (highest priority).
    2. ``X-Workspace-ID`` header.
    3. Active workspace in user session.

    If multiple sources provide a value and they disagree,
    raises ``WorkspaceContextMismatch``.

    Args:
        path_workspace_id: Workspace ID extracted from the URL path.
        header_workspace_id: Value of the ``X-Workspace-ID`` header.
        session_workspace_id: Active workspace from the user session.

    Returns:
        Resolved ``WorkspaceContext`` or ``None`` if no source provides
        a workspace_id.

    Raises:
        WorkspaceContextMismatch: When provided sources disagree.
    """
    sources: dict[str, str] = {}
    if path_workspace_id is not None:
        sources['path'] = path_workspace_id
    if header_workspace_id is not None:
        sources['header'] = header_workspace_id
    if session_workspace_id is not None:
        sources['session'] = session_workspace_id

    if not sources:
        return None

    # Check for conflicts — all provided values must agree.
    unique_ids = set(sources.values())
    if len(unique_ids) > 1:
        raise WorkspaceContextMismatch(sources)

    # Determine which source wins by precedence.
    resolved_id = unique_ids.pop()
    if 'path' in sources:
        source = 'path'
    elif 'header' in sources:
        source = 'header'
    else:
        source = 'session'

    return WorkspaceContext(workspace_id=resolved_id, source=source)
