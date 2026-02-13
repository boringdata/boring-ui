#!/usr/bin/env python3
"""Clean-state guardrail: detect legacy routes and orphan modules.

Bead: bd-20u3.7

Checks:
  1. Legacy route references in runtime and test code.
  2. Orphan modules in src/back/boring_ui/api/ not registered in capabilities.
  3. Canonical route surface inventory.

Exit codes:
  0 = all checks pass (known issues in allowlist only)
  1 = new regressions found (unknown legacy refs or orphan modules)

Usage:
  python3 scripts/check_clean_state.py            # Full check
  python3 scripts/check_clean_state.py --strict    # Fail on ALL issues (including allowlisted)
  python3 scripts/check_clean_state.py --inventory # Print route surface inventory and exit
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

# ── Project root ────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
FRONT_SRC = ROOT / "src" / "front"
BACK_API = ROOT / "src" / "back" / "boring_ui" / "api"
TESTS = ROOT / "tests"

# ── Legacy route patterns ───────────────────────────────────────────
# These patterns detect non-v1 API paths in code. Utility routes
# (/api/config, /api/project, /api/sessions, /api/capabilities,
# /api/approval, /health, /metrics) are excluded.

LEGACY_ROUTE_RE = re.compile(
    r"""(?:['"`/])"""           # Leading quote or slash
    r"""(/api/(?:"""
    r"""tree|"""                # /api/tree -> /api/v1/files/list
    r"""file(?:/rename|/move)?|"""  # /api/file, /api/file/rename, /api/file/move
    r"""search|"""             # /api/search -> /api/v1/files/search
    r"""git/(?:status|diff|show)"""  # /api/git/* -> /api/v1/git/*
    r"""))"""
    r"""(?:[?'"`/\s]|$)""",    # Trailing delimiter
    re.VERBOSE,
)

# Files with known legacy references (pre-existing, tracked for cleanup).
# When a file is migrated, remove it from this allowlist.
LEGACY_ALLOWLIST: dict[str, str] = {
    # Backend observability examples/patterns (not actual route handlers)
    "src/back/boring_ui/observability/middleware.py": "route normalization pattern",
    "src/back/boring_ui/observability/metrics.py": "metric label example",
    "src/back/boring_ui/observability/logging.py": "log path example",
}

# ── Orphan module detection ─────────────────────────────────────────
# Modules in src/back/boring_ui/api/ that are NOT imported by the
# app factory or capabilities registry. These are dead code.

ORPHAN_ALLOWLIST: dict[str, str] = {
    # Legacy routers superseded by modules/*/ equivalents
    "file_routes.py": "superseded by modules/files/router.py",
    "git_routes.py": "superseded by modules/git/router.py",
    "pty_bridge.py": "superseded by modules/pty/router.py",
    "stream_bridge.py": "superseded by modules/stream/router.py",
}

# Files in api/ that are NOT routers (infrastructure, not orphans).
API_INFRASTRUCTURE = {
    "__init__.py",
    "app.py",
    "capabilities.py",
    "config.py",
    "storage.py",
    "utility_routes.py",
    "approval.py",
}


# ── Check: legacy route references ─────────────────────────────────


def check_legacy_routes(strict: bool = False) -> list[str]:
    """Scan runtime and test code for legacy route references.

    Returns list of error messages for unknown (non-allowlisted) files.
    """
    errors: list[str] = []
    warnings: list[str] = []

    scan_dirs = [
        FRONT_SRC,
        ROOT / "src" / "back",
        TESTS,
    ]

    skip_dirs = {"node_modules", "__pycache__", ".git", "dist", "build"}
    code_exts = {".js", ".jsx", ".ts", ".tsx", ".py"}

    for scan_dir in scan_dirs:
        if not scan_dir.exists():
            continue
        for fpath in scan_dir.rglob("*"):
            if fpath.suffix not in code_exts:
                continue
            if any(part in skip_dirs for part in fpath.parts):
                continue

            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
            except (OSError, UnicodeDecodeError):
                continue

            matches = LEGACY_ROUTE_RE.findall(content)
            if not matches:
                continue

            rel = str(fpath.relative_to(ROOT))
            unique_matches = sorted(set(matches))

            if rel in LEGACY_ALLOWLIST and not strict:
                warnings.append(
                    f"  [KNOWN] {rel}: {unique_matches} ({LEGACY_ALLOWLIST[rel]})"
                )
            else:
                errors.append(
                    f"  [NEW] {rel}: legacy routes {unique_matches}"
                )

    return errors, warnings


# ── Check: orphan modules ───────────────────────────────────────────


def check_orphan_modules(strict: bool = False) -> tuple[list[str], list[str]]:
    """Detect .py files in api/ that aren't registered or infrastructure.

    Returns (errors, warnings).
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not BACK_API.exists():
        return errors, warnings

    # Get all .py files directly in api/ (not in subdirectories)
    api_files = {
        f.name for f in BACK_API.iterdir()
        if f.is_file() and f.suffix == ".py"
    }

    # Known infrastructure + registered routers = expected files
    expected = API_INFRASTRUCTURE.copy()

    # Anything not in expected is potentially orphaned
    orphans = api_files - expected

    for orphan in sorted(orphans):
        if orphan in ORPHAN_ALLOWLIST and not strict:
            warnings.append(
                f"  [KNOWN] {orphan} ({ORPHAN_ALLOWLIST[orphan]})"
            )
        else:
            errors.append(
                f"  [NEW] {orphan}: not registered in capabilities or utility_routes"
            )

    return errors, warnings


# ── Inventory: canonical route surface ──────────────────────────────


ROUTE_DECORATOR_RE = re.compile(
    r"""@router\.(get|post|put|delete|patch|websocket)\(['"]([^'"]+)['"]"""
)


def print_route_inventory() -> None:
    """Print the canonical route surface as structured inventory."""
    print("\n=== Canonical Route Surface Inventory ===\n")

    # Registered routers (from capabilities.py registry)
    registry_entries = [
        ("files", "/api", "modules/files/router.py"),
        ("git", "/api/git", "modules/git/router.py"),
        ("pty", "/ws", "modules/pty/router.py"),
        ("chat_claude_code", "/ws", "modules/stream/router.py"),
        ("approval", "/api", "approval.py"),
    ]

    for name, prefix, router_file in registry_entries:
        fpath = BACK_API / router_file
        if not fpath.exists():
            print(f"  [{name}] ({prefix}) -- FILE NOT FOUND: {router_file}")
            continue

        content = fpath.read_text()
        routes = ROUTE_DECORATOR_RE.findall(content)

        print(f"  [{name}] prefix={prefix}")
        for method, path in routes:
            full = f"{prefix}{path}"
            print(f"    {method.upper():8s} {full}")
        print()

    # Utility routes (no prefix)
    utility = BACK_API / "utility_routes.py"
    if utility.exists():
        content = utility.read_text()
        routes = ROUTE_DECORATOR_RE.findall(content)
        print("  [utility] prefix=(root)")
        for method, path in routes:
            print(f"    {method.upper():8s} {path}")
        print()

    # Capabilities endpoint
    print("  [capabilities] prefix=/api")
    print("    GET      /api/capabilities")
    print()


# ── Main ────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clean-state guardrail: detect legacy routes and orphan modules."
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on ALL issues including allowlisted known items.",
    )
    parser.add_argument(
        "--inventory",
        action="store_true",
        help="Print canonical route surface inventory and exit.",
    )
    args = parser.parse_args()

    if args.inventory:
        print_route_inventory()
        return 0

    print("=== Clean-State Guardrail Checks ===\n")
    all_errors: list[str] = []
    all_warnings: list[str] = []

    # Check 1: Legacy route references
    print("1. Checking for legacy route references...")
    route_errors, route_warnings = check_legacy_routes(strict=args.strict)
    all_errors.extend(route_errors)
    all_warnings.extend(route_warnings)

    if route_errors:
        print(f"   FAIL: {len(route_errors)} new legacy route reference(s)")
        for e in route_errors:
            print(e)
    if route_warnings:
        print(f"   KNOWN: {len(route_warnings)} allowlisted item(s)")
        for w in route_warnings:
            print(w)
    if not route_errors and not route_warnings:
        print("   PASS: no legacy route references found")
    print()

    # Check 2: Orphan modules
    print("2. Checking for orphan modules...")
    orphan_errors, orphan_warnings = check_orphan_modules(strict=args.strict)
    all_errors.extend(orphan_errors)
    all_warnings.extend(orphan_warnings)

    if orphan_errors:
        print(f"   FAIL: {len(orphan_errors)} new orphan module(s)")
        for e in orphan_errors:
            print(e)
    if orphan_warnings:
        print(f"   KNOWN: {len(orphan_warnings)} allowlisted item(s)")
        for w in orphan_warnings:
            print(w)
    if not orphan_errors and not orphan_warnings:
        print("   PASS: no orphan modules found")
    print()

    # Check 3: Route inventory
    print("3. Route surface inventory:")
    print_route_inventory()

    # Summary
    print("=" * 50)
    if all_errors:
        print(
            f"FAILED: {len(all_errors)} new regression(s) found.\n"
            f"  {len(all_warnings)} known issue(s) in allowlist.\n"
            f"\n"
            f"To fix:\n"
            f"  - Migrate legacy routes to /api/v1/* canonical paths\n"
            f"  - Register new modules in capabilities.py registry\n"
            f"  - Or add to allowlist with justification if intentional"
        )
        return 1
    elif all_warnings:
        print(
            f"PASSED (with {len(all_warnings)} known allowlisted item(s)).\n"
            f"Run with --strict to fail on allowlisted items too."
        )
        return 0
    else:
        print("PASSED: clean state verified.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
