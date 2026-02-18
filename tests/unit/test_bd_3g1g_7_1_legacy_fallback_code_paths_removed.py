from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_FRONT = REPO_ROOT / "src" / "front"
SRC_BACK = REPO_ROOT / "src" / "back" / "boring_ui"


def _iter_source_files(root: Path, *, suffixes: tuple[str, ...], skip_parts: set[str]) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in suffixes:
            continue
        if skip_parts.intersection(path.parts):
            continue
        files.append(path)
    return files


def _find_forbidden_literals(files: list[Path], forbidden: list[str]) -> list[str]:
    hits: list[str] = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        for literal in forbidden:
            if literal in text:
                hits.append(f"{path.relative_to(REPO_ROOT)}: contains {literal!r}")
    return hits


def test_legacy_routes_and_stream_permission_fallbacks_removed_from_active_code() -> None:
    # Legacy, deprecated route families that should not exist in active product code.
    forbidden_route_literals = [
        "/api/tree",
        "/api/file",
        "/api/file/rename",
        "/api/file/move",
        "/api/search",
        "/api/git/status",
        "/api/git/diff",
        "/api/git/show",
    ]
    forbidden_stream_permission_literals = [
        # Legacy stream-based permission flow (replaced by native control_request/control_response).
        "approval_response",
        "event?.type === 'permission'",
        "source: 'stream'",
        "stream-based permissions (legacy)",
    ]

    front_files = _iter_source_files(
        SRC_FRONT,
        suffixes=(".js", ".jsx", ".ts", ".tsx"),
        skip_parts={"__tests__", "e2e", "node_modules", "dist"},
    )
    back_files = _iter_source_files(
        SRC_BACK,
        suffixes=(".py",),
        skip_parts={"__pycache__", "node_modules", "dist"},
    )

    hits = []
    hits.extend(_find_forbidden_literals(front_files, forbidden_route_literals))
    hits.extend(_find_forbidden_literals(back_files, forbidden_route_literals))
    hits.extend(_find_forbidden_literals(front_files, forbidden_stream_permission_literals))
    hits.extend(_find_forbidden_literals(back_files, forbidden_stream_permission_literals))

    assert hits == [], "Forbidden legacy fallback literals found:\n" + "\n".join(hits)

