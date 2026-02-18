"""Shared delegated-policy enforcement helpers.

This module implements the deny-by-default validation contract defined in:
- docs/bd-3g1g.2.2-scope-capability-claim-model.md
- docs/bd-3g1g.2.3-api-standards-note.md

Important: enforcement is only triggered when the request carries an explicit
delegation envelope header (`X-Scope-Context`). Direct UI calls (no header) are
left unchanged to preserve local/dev workflows while the service split is in
progress.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from fastapi import Request
from starlette.responses import JSONResponse

SCOPE_CONTEXT_HEADER = "X-Scope-Context"

KNOWN_CAPABILITY_CLAIMS: frozenset[str] = frozenset(
    {
        "workspace.files.read",
        "workspace.files.write",
        "workspace.git.read",
        "workspace.git.write",
        "pty.session.start",
        "pty.session.attach",
    }
)


@dataclass(frozen=True)
class ScopeContext:
    request_id: str
    workspace_id: str
    actor: Mapping[str, Any]
    capability_claims: tuple[str, ...]
    cwd_or_worktree: str
    session_id: str | None


@dataclass(frozen=True)
class PolicyDeny(Exception):
    code: str
    message: str
    http_status: int
    request_id: str = ""
    workspace_id: str = ""

    def __str__(self) -> str:  # pragma: no cover
        # Keep logs readable if a PolicyDeny ever escapes local handling.
        return f"{self.code}: {self.message}"


def _error_envelope(
    *,
    code: str,
    message: str,
    request_id: str,
    workspace_id: str,
    retryable: bool = False,
) -> dict[str, Any]:
    # Keep the contract shape stable even when correlation fields are absent.
    return {
        "code": code,
        "message": message,
        "retryable": retryable,
        "details": {
            "request_id": request_id,
            "workspace_id": workspace_id,
        },
    }


def parse_scope_context_header_value(value: str) -> ScopeContext:
    """Parse and validate the scope/capability claim envelope.

    Raises PolicyDeny with `invalid_scope_context` or `capability_denied` when
    the envelope is malformed or the claim set is invalid.
    """
    raw = (value or "").strip()
    if not raw:
        raise PolicyDeny(
            code="invalid_scope_context",
            message="Scope context header is missing or empty.",
            http_status=400,
        )

    try:
        payload = json.loads(raw)
    except Exception:
        raise PolicyDeny(
            code="invalid_scope_context",
            message="Scope context header is not valid JSON.",
            http_status=400,
        )

    if not isinstance(payload, dict):
        raise PolicyDeny(
            code="invalid_scope_context",
            message="Scope context must be a JSON object.",
            http_status=400,
        )

    request_id = payload.get("request_id")
    workspace_id = payload.get("workspace_id")
    actor = payload.get("actor")
    claims = payload.get("capability_claims")
    cwd = payload.get("cwd_or_worktree")
    session_id = payload.get("session_id")

    # Correlation fields: if present but malformed, treat as invalid context.
    if not isinstance(request_id, str) or not request_id.strip():
        raise PolicyDeny(
            code="invalid_scope_context",
            message="Missing required scope field: request_id.",
            http_status=400,
            request_id=str(request_id) if request_id is not None else "",
            workspace_id=str(workspace_id) if isinstance(workspace_id, str) else "",
        )

    if not isinstance(workspace_id, str) or not workspace_id.strip():
        raise PolicyDeny(
            code="invalid_scope_context",
            message="Missing required scope field: workspace_id.",
            http_status=400,
            request_id=request_id,
            workspace_id=str(workspace_id) if workspace_id is not None else "",
        )

    if not isinstance(actor, dict):
        raise PolicyDeny(
            code="invalid_scope_context",
            message="Missing required scope field: actor.",
            http_status=400,
            request_id=request_id,
            workspace_id=workspace_id,
        )

    for key in ("user_id", "service", "role"):
        val = actor.get(key)
        if not isinstance(val, str) or not val.strip():
            raise PolicyDeny(
                code="invalid_scope_context",
                message=f"Missing required actor field: {key}.",
                http_status=400,
                request_id=request_id,
                workspace_id=workspace_id,
            )

    if not isinstance(cwd, str) or not cwd.strip():
        raise PolicyDeny(
            code="invalid_scope_context",
            message="Missing required scope field: cwd_or_worktree.",
            http_status=400,
            request_id=request_id,
            workspace_id=workspace_id,
        )

    if not isinstance(claims, list) or not all(isinstance(item, str) for item in claims):
        raise PolicyDeny(
            code="invalid_scope_context",
            message="Scope context capability_claims must be a list of strings.",
            http_status=400,
            request_id=request_id,
            workspace_id=workspace_id,
        )

    if len(claims) == 0:
        raise PolicyDeny(
            code="capability_denied",
            message="Capability claims are empty.",
            http_status=403,
            request_id=request_id,
            workspace_id=workspace_id,
        )

    unknown = sorted({claim for claim in claims if claim not in KNOWN_CAPABILITY_CLAIMS})
    if unknown:
        raise PolicyDeny(
            code="capability_denied",
            message="Capability claims include unknown entries.",
            http_status=403,
            request_id=request_id,
            workspace_id=workspace_id,
        )

    normalized_session_id: str | None = None
    if session_id is not None:
        if not isinstance(session_id, str):
            raise PolicyDeny(
                code="invalid_scope_context",
                message="Scope context session_id must be a string when present.",
                http_status=400,
                request_id=request_id,
                workspace_id=workspace_id,
            )
        if session_id.strip():
            normalized_session_id = session_id.strip()

    return ScopeContext(
        request_id=request_id,
        workspace_id=workspace_id,
        actor=actor,
        capability_claims=tuple(claims),
        cwd_or_worktree=cwd,
        session_id=normalized_session_id,
    )


def enforce_delegated_policy_or_none(
    request: Request,
    required_claims: Iterable[str],
    *,
    operation: str,
    require_session_id: bool = False,
    expected_session_id: str | None = None,
) -> JSONResponse | None:
    """Enforce deny-by-default policy for delegated requests.

    Returns a JSONResponse for policy denials, or None when:
    - the request is not delegated (no scope header), or
    - the delegated scope/claims satisfy the required contract.
    """
    header_value = request.headers.get(SCOPE_CONTEXT_HEADER)
    if header_value is None:
        return None

    try:
        scope = parse_scope_context_header_value(header_value)
    except PolicyDeny as deny:
        return JSONResponse(
            status_code=deny.http_status,
            content=_error_envelope(
                code=deny.code,
                message=deny.message,
                request_id=deny.request_id,
                workspace_id=deny.workspace_id,
            ),
        )

    required = set(required_claims)
    if required and not required.issubset(set(scope.capability_claims)):
        return JSONResponse(
            status_code=403,
            content=_error_envelope(
                code="capability_denied",
                message=f"Delegated operation denied: missing claim(s) for {operation}.",
                request_id=scope.request_id,
                workspace_id=scope.workspace_id,
            ),
        )

    if require_session_id and not scope.session_id:
        return JSONResponse(
            status_code=400,
            content=_error_envelope(
                code="invalid_scope_context",
                message=f"Delegated operation denied: session_id is required for {operation}.",
                request_id=scope.request_id,
                workspace_id=scope.workspace_id,
            ),
        )

    if expected_session_id is not None and scope.session_id != expected_session_id:
        return JSONResponse(
            status_code=403,
            content=_error_envelope(
                code="session_mismatch",
                message=f"Delegated operation denied: session scope mismatch for {operation}.",
                request_id=scope.request_id,
                workspace_id=scope.workspace_id,
            ),
        )

    return None


def enforce_delegated_policy_ws_reason_or_none(
    headers: Mapping[str, str],
    required_claims: Iterable[str],
    *,
    operation: str,
    require_session_id: bool = False,
    expected_session_id: str | None = None,
) -> str | None:
    """WS variant of delegated policy enforcement.

    WebSocket handlers cannot return HTTP JSON envelopes, so this returns a
    stable close reason string like `policy:capability_denied` when a delegated
    request must be denied. Non-delegated WS connections return None.
    """
    # Starlette Headers are case-insensitive, but some callers may pass a plain
    # dict; be tolerant there as well.
    header_value = headers.get(SCOPE_CONTEXT_HEADER) or headers.get(SCOPE_CONTEXT_HEADER.lower())
    if header_value is None:
        return None

    try:
        scope = parse_scope_context_header_value(header_value)
    except PolicyDeny as deny:
        return f"policy:{deny.code}"

    required = set(required_claims)
    if required and not required.issubset(set(scope.capability_claims)):
        return "policy:capability_denied"

    if require_session_id and not scope.session_id:
        return "policy:invalid_scope_context"

    if expected_session_id is not None and scope.session_id != expected_session_id:
        return "policy:session_mismatch"

    return None
