"""HTTP Contract Baseline for boring-ui API.

This module defines the canonical request/response contracts for every HTTP
endpoint consumed by the frontend.  It serves as:

  1. A machine-readable reference for contract test generation (bd-ptl.1.1.3).
  2. A specification gate for sandbox delegation (V0 Phase 3+): any proxy or
     delegation layer MUST preserve these contracts byte-for-byte in semantics.

Schema convention
-----------------
Each contract is a dict with:
  method      - HTTP method
  path        - URL path (with {param} placeholders for path params)
  query       - dict of query parameter names -> {required, type, default, description}
  request     - request body schema (None for GET/DELETE without body)
  responses   - dict of status_code -> {description, schema}
  edge_cases  - list of known tolerated behaviors and failure semantics
  frontend_callers - list of frontend files that call this endpoint

Response schemas use a minimal DSL:
  "string"     - JSON string
  "bool"       - JSON boolean
  "int"        - JSON integer
  "object"     - JSON object (shape described in nested dict)
  "array"      - JSON array (element shape described)
  "string|null"- nullable string
  "any"        - any JSON value
"""

# ---------------------------------------------------------------------------
# 1. Capabilities & Discovery
# ---------------------------------------------------------------------------

CAPABILITIES = {
    "method": "GET",
    "path": "/api/capabilities",
    "query": {},
    "request": None,
    "responses": {
        200: {
            "description": "API capabilities and available features",
            "schema": {
                "version": "string",  # semver, currently "0.1.0"
                "features": {
                    "files": "bool",
                    "git": "bool",
                    "pty": "bool",
                    "chat_claude_code": "bool",
                    "stream": "bool",  # backward-compat alias for chat_claude_code
                    "approval": "bool",
                },
                "routers": [  # present when registry provided (always in default app)
                    {
                        "name": "string",
                        "prefix": "string",
                        "description": "string",
                        "tags": ["string"],
                        "enabled": "bool",
                    }
                ],
            },
        },
    },
    "edge_cases": [
        "stream and chat_claude_code always have the same boolean value",
        "routers array includes all registered routers, not just enabled ones",
        "routers array may include the 'stream' alias entry alongside 'chat_claude_code'",
    ],
    "frontend_callers": [
        "src/front/hooks/useCapabilities.js",
        "src/front/registry/panes.js (documentation reference)",
    ],
}

HEALTH = {
    "method": "GET",
    "path": "/health",
    "query": {},
    "request": None,
    "responses": {
        200: {
            "description": "Health check with workspace info",
            "schema": {
                "status": "string",  # always "ok"
                "workspace": "string",  # absolute path to workspace_root
                "workspace_mode": "string",  # "local" or "sandbox"
                "features": {
                    "files": "bool",
                    "git": "bool",
                    "pty": "bool",
                    "chat_claude_code": "bool",
                    "stream": "bool",
                    "approval": "bool",
                },
            },
        },
    },
    "edge_cases": [
        "Always returns 200 if the app is running (no deep health checks)",
        "workspace_mode reflects RuntimeConfig, not APIConfig",
    ],
    "frontend_callers": [],  # backend-only / ops
}

CONFIG = {
    "method": "GET",
    "path": "/api/config",
    "query": {},
    "request": None,
    "responses": {
        200: {
            "description": "API configuration info",
            "schema": {
                "workspace_root": "string",  # absolute path
                "workspace_mode": "string",  # "local" or "sandbox"
                "pty_providers": ["string"],  # list of provider names
                "paths": {
                    "files": "string",  # always "." currently
                },
                # Optional sandbox block (only present when workspace_mode == "sandbox")
                "sandbox?": {
                    "base_url": "string",
                    "sprite_name": "string",
                    "service_target": {
                        "host": "string",
                        "port": "int",
                        "path": "string",
                    },
                    "multi_tenant": "bool",
                    "routing_mode": "string",
                    "auth_identity_binding": "bool",
                },
            },
        },
    },
    "edge_cases": [
        "sandbox key absent in local mode, present in sandbox mode",
        "pty_providers lists names only (not commands) for security",
    ],
    "frontend_callers": [
        "src/front/components/FileTree.jsx",
    ],
}

PROJECT = {
    "method": "GET",
    "path": "/api/project",
    "query": {},
    "request": None,
    "responses": {
        200: {
            "description": "Project root path for frontend",
            "schema": {
                "root": "string",  # absolute path to workspace_root
            },
        },
    },
    "edge_cases": [
        "Always returns workspace_root as string, even if directory doesn't exist",
    ],
    "frontend_callers": [
        "src/front/App.jsx",
    ],
}


# ---------------------------------------------------------------------------
# 2. File Operations (router prefix: /api, requires 'files' feature)
# ---------------------------------------------------------------------------

FILE_TREE = {
    "method": "GET",
    "path": "/api/tree",
    "query": {
        "path": {
            "required": False,
            "type": "string",
            "default": ".",
            "description": "Directory path relative to workspace root",
        },
    },
    "request": None,
    "responses": {
        200: {
            "description": "Directory listing",
            "schema": {
                "entries": [
                    {
                        "name": "string",       # filename/dirname
                        "path": "string",        # relative to workspace root
                        "is_dir": "bool",
                        "size?": "int",          # present for files, absent for dirs
                    }
                ],
                "path": "string",  # echoes the input path
            },
        },
        400: {
            "description": "Path traversal detected",
            "schema": {"detail": "string"},
        },
    },
    "edge_cases": [
        "Non-existent directory returns 200 with empty entries (not 404)",
        "Entries sorted: directories first, then alphabetical case-insensitive",
        "size field present only for files (via stat), 0 on OSError",
        "path field echoes the raw input, not the resolved path",
        "Default path is '.' (workspace root) when query param omitted",
    ],
    "frontend_callers": [
        "src/front/components/FileTree.jsx",
        "src/front/components/chat/ClaudeStreamChat.jsx",
    ],
}

FILE_READ = {
    "method": "GET",
    "path": "/api/file",
    "query": {
        "path": {
            "required": True,
            "type": "string",
            "default": None,
            "description": "File path relative to workspace root",
        },
    },
    "request": None,
    "responses": {
        200: {
            "description": "File contents",
            "schema": {
                "content": "string",  # file content as UTF-8 text
                "path": "string",     # echoes input path
            },
        },
        400: {
            "description": "Path traversal or path is a directory",
            "schema": {"detail": "string"},
        },
        404: {
            "description": "File not found",
            "schema": {"detail": "string"},
        },
    },
    "edge_cases": [
        "Reading a directory returns 400 (not 404) with 'Path is a directory' message",
        "Binary files read as UTF-8 may produce garbled content (no binary detection)",
        "Empty files return content: '' (empty string)",
        "path field echoes the raw input path",
    ],
    "frontend_callers": [
        "src/front/panels/EditorPanel.jsx",
        "src/front/App.jsx",
    ],
}

FILE_WRITE = {
    "method": "PUT",
    "path": "/api/file",
    "query": {
        "path": {
            "required": True,
            "type": "string",
            "default": None,
            "description": "File path relative to workspace root",
        },
    },
    "request": {
        "content_type": "application/json",
        "schema": {
            "content": "string",  # required, file content to write
        },
    },
    "responses": {
        200: {
            "description": "File written successfully",
            "schema": {
                "success": "bool",  # always True on success
                "path": "string",   # echoes input path
            },
        },
        400: {
            "description": "Path traversal detected",
            "schema": {"detail": "string"},
        },
        422: {
            "description": "Validation error (missing content field)",
            "schema": {"detail": "array"},  # FastAPI validation error format
        },
        500: {
            "description": "Write failed (OS error)",
            "schema": {"detail": "string"},
        },
    },
    "edge_cases": [
        "Creates parent directories automatically if they don't exist",
        "Overwrites existing files without warning or conflict check",
        "No content-length or size limit enforced at API level",
        "success is always True when status is 200",
    ],
    "frontend_callers": [
        "src/front/panels/EditorPanel.jsx",
        "src/front/components/FileTree.jsx (new file creation)",
    ],
}

FILE_DELETE = {
    "method": "DELETE",
    "path": "/api/file",
    "query": {
        "path": {
            "required": True,
            "type": "string",
            "default": None,
            "description": "File path relative to workspace root",
        },
    },
    "request": None,
    "responses": {
        200: {
            "description": "File deleted",
            "schema": {
                "success": "bool",  # always True
                "path": "string",   # echoes input path
            },
        },
        400: {
            "description": "Path traversal detected",
            "schema": {"detail": "string"},
        },
        404: {
            "description": "File not found",
            "schema": {"detail": "string"},
        },
    },
    "edge_cases": [
        "Deleting a directory performs recursive rmtree (not just single file)",
        "No confirmation or soft-delete - immediate permanent removal",
    ],
    "frontend_callers": [
        "src/front/components/FileTree.jsx",
    ],
}

FILE_RENAME = {
    "method": "POST",
    "path": "/api/file/rename",
    "query": {},
    "request": {
        "content_type": "application/json",
        "schema": {
            "old_path": "string",  # required, current file path
            "new_path": "string",  # required, target file path
        },
    },
    "responses": {
        200: {
            "description": "File renamed",
            "schema": {
                "success": "bool",     # always True
                "old_path": "string",  # echoes input old_path
                "new_path": "string",  # echoes input new_path
            },
        },
        400: {
            "description": "Path traversal detected",
            "schema": {"detail": "string"},
        },
        404: {
            "description": "Source file not found",
            "schema": {"detail": "string"},
        },
        409: {
            "description": "Target path already exists",
            "schema": {"detail": "string"},
        },
    },
    "edge_cases": [
        "Both old_path and new_path are validated against workspace_root",
        "Rename is atomic on the same filesystem (os rename)",
        "Can rename directories, not just files",
    ],
    "frontend_callers": [
        "src/front/components/FileTree.jsx",
    ],
}

FILE_MOVE = {
    "method": "POST",
    "path": "/api/file/move",
    "query": {},
    "request": {
        "content_type": "application/json",
        "schema": {
            "src_path": "string",  # required, source file path
            "dest_dir": "string",  # required, destination directory
        },
    },
    "responses": {
        200: {
            "description": "File moved",
            "schema": {
                "success": "bool",     # always True
                "old_path": "string",  # echoes input src_path
                "dest_path": "string", # new path (relative to workspace)
            },
        },
        400: {
            "description": "Path traversal or destination not a directory",
            "schema": {"detail": "string"},
        },
        404: {
            "description": "Source file not found",
            "schema": {"detail": "string"},
        },
    },
    "edge_cases": [
        "dest_dir must be an existing directory (not auto-created)",
        "Filename preserved from source (dest_path = dest_dir/src_name)",
        "Raises FileExistsError if dest already has file with same name (not exposed as HTTP error - returns 500)",
        "Uses shutil.move (cross-filesystem safe)",
    ],
    "frontend_callers": [
        "src/front/components/FileTree.jsx",
    ],
}

FILE_SEARCH = {
    "method": "GET",
    "path": "/api/search",
    "query": {
        "q": {
            "required": True,
            "type": "string",
            "default": None,
            "description": "Search pattern (glob-style, e.g. *.py, test_*)",
        },
        "path": {
            "required": False,
            "type": "string",
            "default": ".",
            "description": "Directory to search in",
        },
    },
    "request": None,
    "responses": {
        200: {
            "description": "Search results",
            "schema": {
                "results": [
                    {
                        "name": "string",  # filename
                        "path": "string",  # relative path from workspace root
                        "dir": "string",   # parent directory ('' for root)
                    }
                ],
                "pattern": "string",  # echoes input q
                "path": "string",     # echoes input path
            },
        },
        400: {
            "description": "Path traversal detected",
            "schema": {"detail": "string"},
        },
        422: {
            "description": "Empty search pattern",
            "schema": {"detail": "array"},
        },
    },
    "edge_cases": [
        "Search is case-insensitive (fnmatch with lower())",
        "Recursion depth capped at 10 levels",
        "Matches files AND directories by name",
        "dir field is '' (empty string) for root-level matches, else parent dirname",
        "No result limit - returns all matches up to depth 10",
        "PermissionError and FileNotFoundError silently skipped during recursion",
    ],
    "frontend_callers": [
        "src/front/components/FileTree.jsx",
        "src/front/components/chat/ClaudeStreamChat.jsx",
    ],
}


# ---------------------------------------------------------------------------
# 3. Git Operations (router prefix: /api/git, requires 'git' feature)
# ---------------------------------------------------------------------------

GIT_STATUS = {
    "method": "GET",
    "path": "/api/git/status",
    "query": {},
    "request": None,
    "responses": {
        200: {
            "description": "Git repository status",
            "schema": {
                "is_repo": "bool",
                "available?": "bool",    # present when is_repo=True, always True
                "files": "dict|array",   # dict when is_repo=True, empty array when False
                # When is_repo=True, files is: { "path/to/file": "M"|"A"|"D"|"U"|"C" }
            },
        },
    },
    "edge_cases": [
        "Non-git workspace returns {is_repo: false, files: []} (empty array, not dict)",
        "When is_repo=True, files is a dict mapping path -> single-char status",
        "Status codes: M=Modified, A=Added, D=Deleted, U=Untracked, C=Conflict",
        "Rename (R*) normalized to M, Copy (C*) normalized to A",
        "Higher-priority status wins when file appears in multiple states",
        "Priority order: C(5) > D(4) > A(3) > M(2) > U(1)",
        "available field always True when is_repo=True (frontend compatibility)",
        "Uses porcelain v1 format (not v2 despite comment mentioning v2)",
        "Git command timeout is 30 seconds",
    ],
    "frontend_callers": [
        "src/front/components/FileTree.jsx",
        "src/front/components/GitChangesView.jsx",
    ],
}

GIT_DIFF = {
    "method": "GET",
    "path": "/api/git/diff",
    "query": {
        "path": {
            "required": True,
            "type": "string",
            "default": None,
            "description": "File path relative to workspace root",
        },
    },
    "request": None,
    "responses": {
        200: {
            "description": "Git diff for file",
            "schema": {
                "diff": "string",       # unified diff output (may be empty)
                "path": "string",       # echoes input path
                "error?": "string",     # present on git command failure
            },
        },
        400: {
            "description": "Path traversal detected",
            "schema": {"detail": "string"},
        },
    },
    "edge_cases": [
        "Untracked files return {diff: '', error: 'Git error: ...'} with 200 (not 4xx/5xx)",
        "Empty diff (no changes) returns diff: '' without error field",
        "Diffs against HEAD (includes both staged and unstaged changes)",
        "error field only present when git command fails",
    ],
    "frontend_callers": [
        "src/front/panels/EditorPanel.jsx",
    ],
}

GIT_SHOW = {
    "method": "GET",
    "path": "/api/git/show",
    "query": {
        "path": {
            "required": True,
            "type": "string",
            "default": None,
            "description": "File path relative to workspace root",
        },
    },
    "request": None,
    "responses": {
        200: {
            "description": "File content at HEAD",
            "schema": {
                "content": "string|null",  # null if file not tracked at HEAD
                "path": "string",          # echoes input path
                "error?": "string",        # present when not in HEAD
            },
        },
        400: {
            "description": "Path traversal detected",
            "schema": {"detail": "string"},
        },
    },
    "edge_cases": [
        "Untracked files return {content: null, error: 'Not in HEAD'} with 200",
        "Never returns 404 - always 200 with content=null for missing files",
        "Shows content at HEAD commit specifically (not index/worktree)",
    ],
    "frontend_callers": [
        "src/front/panels/EditorPanel.jsx",
    ],
}


# ---------------------------------------------------------------------------
# 4. Session Management (inline routes in app.py)
# ---------------------------------------------------------------------------

SESSIONS_LIST = {
    "method": "GET",
    "path": "/api/sessions",
    "query": {},
    "request": None,
    "responses": {
        200: {
            "description": "List active PTY and stream sessions",
            "schema": {
                "sessions": [
                    {
                        "id": "string",            # session UUID
                        "type": "string",           # "pty" or "stream"
                        "alive": "bool",            # is subprocess alive
                        "clients": "int",           # connected websocket count
                        "history_count": "int",     # cached history line count
                    }
                ],
            },
        },
    },
    "edge_cases": [
        "Returns combined list of PTY + stream sessions in that order",
        "Sessions with no clients may still be alive (background processes)",
        "Session list is ephemeral - resets on server restart",
        "Empty list when no sessions exist: {sessions: []}",
    ],
    "frontend_callers": [
        "src/front/components/chat/ClaudeStreamChat.jsx",
    ],
}

SESSIONS_CREATE = {
    "method": "POST",
    "path": "/api/sessions",
    "query": {},
    "request": None,  # no body required
    "responses": {
        200: {
            "description": "New session ID generated",
            "schema": {
                "session_id": "string",  # UUID v4
            },
        },
    },
    "edge_cases": [
        "Does NOT create an actual session - just generates a UUID",
        "Actual session created on first WebSocket connect with this ID",
        "No validation or rate limiting on session creation",
    ],
    "frontend_callers": [
        "src/front/components/chat/ClaudeStreamChat.jsx",
    ],
}


# ---------------------------------------------------------------------------
# 5. Approval Workflow (router prefix: /api, requires 'approval' feature)
# ---------------------------------------------------------------------------

APPROVAL_CREATE = {
    "method": "POST",
    "path": "/api/approval/request",
    "query": {},
    "request": {
        "content_type": "application/json",
        "schema": {
            "tool_name": "string",           # required
            "description": "string",         # required
            "command": "string|null",         # optional
            "metadata": "object|null",        # optional dict
        },
    },
    "responses": {
        200: {
            "description": "Approval request created",
            "schema": {
                "request_id": "string",  # UUID v4
                "status": "string",      # always "pending"
            },
        },
        422: {
            "description": "Validation error (missing required fields)",
            "schema": {"detail": "array"},
        },
    },
    "edge_cases": [
        "request_id is server-generated UUID, not client-provided",
        "metadata can be any JSON object (no schema validation)",
        "status always 'pending' on creation",
    ],
    "frontend_callers": [
        # Created by stream bridge, not frontend directly
    ],
}

APPROVAL_PENDING = {
    "method": "GET",
    "path": "/api/approval/pending",
    "query": {},
    "request": None,
    "responses": {
        200: {
            "description": "List pending approval requests",
            "schema": {
                "pending": [
                    {
                        "id": "string",
                        "status": "string",           # always "pending"
                        "tool_name": "string",
                        "description": "string",
                        "command": "string|null",
                        "metadata": "object|null",
                        "created_at": "string",       # ISO 8601 UTC
                    }
                ],
                "count": "int",
            },
        },
    },
    "edge_cases": [
        "Only returns requests with status='pending' (not decided ones)",
        "count matches len(pending)",
        "Empty list returns {pending: [], count: 0}",
        "In-memory store: resets on server restart",
    ],
    "frontend_callers": [
        "src/front/App.jsx",
        "src/front/components/chat/ClaudeStreamChat.jsx",
    ],
}

APPROVAL_DECISION = {
    "method": "POST",
    "path": "/api/approval/decision",
    "query": {},
    "request": {
        "content_type": "application/json",
        "schema": {
            "request_id": "string",     # required, UUID of the approval request
            "decision": "string",       # required, "approve" or "deny"
            "reason": "string|null",    # optional
        },
    },
    "responses": {
        200: {
            "description": "Decision submitted",
            "schema": {
                "success": "bool",       # always True
                "request_id": "string",  # echoes input
                "decision": "string",    # echoes input
            },
        },
        400: {
            "description": "Invalid decision value (not 'approve' or 'deny')",
            "schema": {"detail": "string"},
        },
        404: {
            "description": "Approval request not found",
            "schema": {"detail": "string"},
        },
        409: {
            "description": "Request already decided (not pending)",
            "schema": {"detail": "string"},
        },
    },
    "edge_cases": [
        "Decision must be exactly 'approve' or 'deny' (case-sensitive)",
        "Double-deciding returns 409 with previous decision in message",
        "reason is stored but not returned in the decision response",
    ],
    "frontend_callers": [
        "src/front/App.jsx",
        "src/front/components/chat/ClaudeStreamChat.jsx",
    ],
}

APPROVAL_STATUS = {
    "method": "GET",
    "path": "/api/approval/status/{request_id}",
    "query": {},
    "request": None,
    "responses": {
        200: {
            "description": "Full approval request data",
            "schema": {
                "id": "string",
                "status": "string",           # "pending", "approve", or "deny"
                "tool_name": "string",
                "description": "string",
                "command": "string|null",
                "metadata": "object|null",
                "created_at": "string",       # ISO 8601 UTC
                "reason?": "string|null",     # present after decision
                "decided_at?": "string",      # present after decision, ISO 8601 UTC
            },
        },
        404: {
            "description": "Approval request not found",
            "schema": {"detail": "string"},
        },
    },
    "edge_cases": [
        "reason and decided_at fields only present after a decision is made",
        "status value after decision is the literal decision string ('approve'/'deny'), not 'approved'/'denied'",
    ],
    "frontend_callers": [],
}

APPROVAL_DELETE = {
    "method": "DELETE",
    "path": "/api/approval/{request_id}",
    "query": {},
    "request": None,
    "responses": {
        200: {
            "description": "Approval request deleted",
            "schema": {
                "success": "bool",       # always True
                "request_id": "string",  # echoes input
            },
        },
        404: {
            "description": "Approval request not found",
            "schema": {"detail": "string"},
        },
    },
    "edge_cases": [
        "Permanently removes the request (no soft delete)",
        "Can delete requests in any status (pending, approved, denied)",
    ],
    "frontend_callers": [],
}


# ---------------------------------------------------------------------------
# Cross-cutting contracts
# ---------------------------------------------------------------------------

ERROR_FORMAT = {
    "description": "Standard FastAPI error response format used across all endpoints",
    "schemas": {
        "validation_error_422": {
            "detail": [
                {
                    "type": "string",
                    "loc": ["string|int"],  # field location path
                    "msg": "string",
                    "input": "any",
                }
            ],
        },
        "http_error_4xx_5xx": {
            "detail": "string",  # human-readable error message
        },
    },
    "notes": [
        "All 4xx/5xx errors use FastAPI's HTTPException format: {detail: string}",
        "422 Validation errors use FastAPI/Pydantic format: {detail: [{type, loc, msg, input}]}",
        "Path traversal errors always return 400 with 'traversal' in detail (case-insensitive)",
        "No structured error codes - only human-readable strings in detail",
    ],
}

PATH_VALIDATION = {
    "description": "Path validation contract applied to all file/git endpoints",
    "rules": [
        "All paths resolved relative to workspace_root",
        "Path traversal (../) outside workspace_root returns HTTP 400",
        "Absolute paths outside workspace return HTTP 400",
        "Symlinks resolved before boundary check (prevents symlink escape)",
        "Empty path defaults to '.' (workspace root) where applicable",
    ],
    "affected_endpoints": [
        "/api/tree", "/api/file", "/api/search",
        "/api/file/rename", "/api/file/move",
        "/api/git/diff", "/api/git/show",
    ],
}


# ---------------------------------------------------------------------------
# Master registry: all HTTP contracts indexed by identifier
# ---------------------------------------------------------------------------

ALL_CONTRACTS = {
    "capabilities": CAPABILITIES,
    "health": HEALTH,
    "config": CONFIG,
    "project": PROJECT,
    "file_tree": FILE_TREE,
    "file_read": FILE_READ,
    "file_write": FILE_WRITE,
    "file_delete": FILE_DELETE,
    "file_rename": FILE_RENAME,
    "file_move": FILE_MOVE,
    "file_search": FILE_SEARCH,
    "git_status": GIT_STATUS,
    "git_diff": GIT_DIFF,
    "git_show": GIT_SHOW,
    "sessions_list": SESSIONS_LIST,
    "sessions_create": SESSIONS_CREATE,
    "approval_create": APPROVAL_CREATE,
    "approval_pending": APPROVAL_PENDING,
    "approval_decision": APPROVAL_DECISION,
    "approval_status": APPROVAL_STATUS,
    "approval_delete": APPROVAL_DELETE,
}

CROSS_CUTTING = {
    "error_format": ERROR_FORMAT,
    "path_validation": PATH_VALIDATION,
}
