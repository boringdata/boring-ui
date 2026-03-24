"""Scaffolding / Build Correctness checks (Phase A).

Verifies the agent produced a real app structure matching the naming
contract.  All checks are filesystem reads — no network, no processes.

Anti-brittleness: Use semantic checks (does create_app exist somewhere?)
rather than exact path matching. The outcome matters more than the layout.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from tests.eval.check_catalog import CATALOG
from tests.eval.contracts import CheckResult, RunManifest
from tests.eval.reason_codes import Attribution, CheckStatus

# Try tomllib (3.11+), fall back to tomli
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Check context
# ---------------------------------------------------------------------------

class ScaffoldingContext:
    """Shared state for scaffolding checks within a single run."""

    def __init__(self, manifest: RunManifest) -> None:
        self.manifest = manifest
        self.project_root = Path(manifest.project_root)
        self.toml_data: dict[str, Any] | None = None
        self.toml_error: str = ""


# ---------------------------------------------------------------------------
# Check implementations
# ---------------------------------------------------------------------------

def run_scaffolding_checks(manifest: RunManifest) -> list[CheckResult]:
    """Run all 13 scaffolding checks and return results."""
    ctx = ScaffoldingContext(manifest)
    results: list[CheckResult] = []

    results.append(_check_dir_exists(ctx))
    results.append(_check_toml_exists(ctx))
    results.append(_check_toml_valid(ctx))
    results.append(_check_name_matches(ctx))
    results.append(_check_id_matches(ctx))
    results.append(_check_pyproject_valid(ctx))
    results.append(_check_backend_entry_exists(ctx))
    results.append(_check_app_factory_or_entrypoint(ctx))
    results.append(_check_routers_dir_or_equivalent(ctx))
    results.append(_check_custom_router_impl(ctx))
    results.append(_check_custom_router_mounted(ctx))
    results.append(_check_frontend_present_if_profiled(ctx))
    results.append(_check_deploy_platform_fly(ctx))

    return results


def _spec(check_id: str) -> dict[str, Any]:
    """Get weight and category from catalog."""
    s = CATALOG[check_id]
    return {"id": check_id, "category": s.category, "weight": s.weight}


def _pass(check_id: str, detail: str = "") -> CheckResult:
    return CheckResult(**_spec(check_id), status=CheckStatus.PASS, detail=detail)


def _fail(check_id: str, reason_code: str, detail: str = "") -> CheckResult:
    return CheckResult(
        **_spec(check_id),
        status=CheckStatus.FAIL,
        reason_code=reason_code,
        attribution=Attribution.AGENT,
        detail=detail,
    )


def _skip(check_id: str, detail: str, blocked_by: list[str] | None = None) -> CheckResult:
    return CheckResult(
        **_spec(check_id),
        status=CheckStatus.SKIP,
        detail=detail,
        skipped=True,
        blocked_by=blocked_by or [],
    )


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def _check_dir_exists(ctx: ScaffoldingContext) -> CheckResult:
    cid = "scaff.dir_exists"
    if ctx.project_root.is_dir():
        return _pass(cid, f"Found: {ctx.project_root}")
    return _fail(cid, "SCAFF_DIR_MISSING", f"Not found: {ctx.project_root}")


def _check_toml_exists(ctx: ScaffoldingContext) -> CheckResult:
    cid = "scaff.toml_exists"
    toml_path = ctx.project_root / "boring.app.toml"
    if toml_path.is_file():
        return _pass(cid, str(toml_path))
    return _fail(cid, "SCAFF_TOML_MISSING", f"Not found: {toml_path}")


def _check_toml_valid(ctx: ScaffoldingContext) -> CheckResult:
    cid = "scaff.toml_valid"
    toml_path = ctx.project_root / "boring.app.toml"
    if not toml_path.is_file():
        return _skip(cid, "No boring.app.toml", blocked_by=["scaff.toml_exists"])

    if tomllib is None:
        return _skip(cid, "tomllib/tomli not available")

    try:
        with open(toml_path, "rb") as f:
            ctx.toml_data = tomllib.load(f)
        return _pass(cid, f"Parsed {len(ctx.toml_data)} top-level keys")
    except Exception as e:
        ctx.toml_error = str(e)
        return _fail(cid, "SCAFF_TOML_INVALID", f"Parse error: {e}")


def _check_name_matches(ctx: ScaffoldingContext) -> CheckResult:
    cid = "scaff.name_matches"
    if ctx.toml_data is None:
        return _skip(cid, "TOML not parsed", blocked_by=["scaff.toml_valid"])

    app = ctx.toml_data.get("app", {})
    name = app.get("name", "")
    expected = ctx.manifest.app_slug

    if not name:
        return _fail(cid, "SCAFF_TOML_FIELD_MISSING", "[app].name is missing")

    # Semantic match: allow case-insensitive, allow hyphens/underscores interchangeably
    if _normalize(name) == _normalize(expected):
        return _pass(cid, f"name={name!r} matches {expected!r}")
    return _fail(
        cid, "SCAFF_TOML_FIELD_MISMATCH",
        f"name={name!r} does not match expected {expected!r}",
    )


def _check_id_matches(ctx: ScaffoldingContext) -> CheckResult:
    cid = "scaff.id_matches"
    if ctx.toml_data is None:
        return _skip(cid, "TOML not parsed", blocked_by=["scaff.toml_valid"])

    app = ctx.toml_data.get("app", {})
    app_id = app.get("id", "")
    expected = ctx.manifest.app_slug

    if not app_id:
        # ID is optional in some scaffolds
        return _pass(cid, "[app].id not set (acceptable)")

    if _normalize(app_id) == _normalize(expected):
        return _pass(cid, f"id={app_id!r} matches {expected!r}")
    return _fail(
        cid, "SCAFF_TOML_FIELD_MISMATCH",
        f"id={app_id!r} does not match expected {expected!r}",
    )


def _check_pyproject_valid(ctx: ScaffoldingContext) -> CheckResult:
    cid = "scaff.pyproject_valid"
    pyproject = ctx.project_root / "pyproject.toml"
    if not pyproject.is_file():
        # pyproject.toml is not strictly required for all scaffolds
        return _pass(cid, "No pyproject.toml (acceptable for some scaffolds)")

    if tomllib is None:
        return _skip(cid, "tomllib/tomli not available")

    try:
        with open(pyproject, "rb") as f:
            tomllib.load(f)
        return _pass(cid, "pyproject.toml parses successfully")
    except Exception as e:
        return _fail(cid, "SCAFF_TOML_INVALID", f"pyproject.toml parse error: {e}")


def _check_backend_entry_exists(ctx: ScaffoldingContext) -> CheckResult:
    cid = "scaff.backend_entry_exists"
    if ctx.toml_data is None:
        return _skip(cid, "TOML not parsed", blocked_by=["scaff.toml_valid"])

    backend = ctx.toml_data.get("backend", {})
    entry = backend.get("entry", "")

    if not entry:
        return _fail(cid, "SCAFF_ENTRY_MISSING", "[backend].entry not set")

    # entry format: "module.path:factory" — resolve module path
    module_path = entry.split(":")[0]
    file_path = ctx.project_root / "src" / module_path.replace(".", "/")

    # Check as package (__init__.py) or module (.py)
    candidates = [
        file_path.with_suffix(".py"),
        file_path / "__init__.py",
    ]
    # Also check without src/ prefix
    alt_path = ctx.project_root / module_path.replace(".", "/")
    candidates.extend([
        alt_path.with_suffix(".py"),
        alt_path / "__init__.py",
    ])

    for candidate in candidates:
        if candidate.is_file():
            return _pass(cid, f"Entry module found: {candidate.relative_to(ctx.project_root)}")

    return _fail(
        cid, "SCAFF_ENTRY_MISSING",
        f"Entry {entry!r} does not resolve to a file under {ctx.project_root}",
    )


def _check_app_factory_or_entrypoint(ctx: ScaffoldingContext) -> CheckResult:
    cid = "scaff.app_factory_or_entrypoint"
    if ctx.toml_data is None:
        return _skip(cid, "TOML not parsed", blocked_by=["scaff.toml_valid"])

    # Search for create_app in Python files
    for py_file in ctx.project_root.rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8", errors="replace")
            if "def create_app" in content or "create_app" in content:
                return _pass(
                    cid,
                    f"create_app found in {py_file.relative_to(ctx.project_root)}",
                )
        except OSError:
            continue

    return _fail(cid, "SCAFF_ENTRY_MISSING", "No create_app function found in project")


def _check_routers_dir_or_equivalent(ctx: ScaffoldingContext) -> CheckResult:
    cid = "scaff.routers_dir_or_equivalent"
    # Look for routers/, routes/, or any directory with route-like files
    for pattern in ["routers", "routes", "api"]:
        matches = list(ctx.project_root.rglob(pattern))
        if any(m.is_dir() for m in matches):
            return _pass(cid, f"Found routing directory: {pattern}")

    # Fallback: any .py file with FastAPI/Flask router patterns
    for py_file in ctx.project_root.rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8", errors="replace")
            if "APIRouter" in content or "Blueprint" in content or "@app.route" in content:
                return _pass(
                    cid,
                    f"Router pattern found in {py_file.relative_to(ctx.project_root)}",
                )
        except OSError:
            continue

    return _fail(cid, "SCAFF_ROUTER_MISSING", "No routing directory or router pattern found")


def _check_custom_router_impl(ctx: ScaffoldingContext) -> CheckResult:
    """must_pass: Verify /health and /info routes exist with nonce."""
    cid = "scaff.custom_router_impl"
    m = ctx.manifest

    found_health = False
    found_info = False
    found_nonce = False

    for py_file in ctx.project_root.rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        # Check for /health route
        if re.search(r'["\'/]health["\']', content):
            found_health = True
        # Check for /info route
        if re.search(r'["\'/]info["\']', content):
            found_info = True
        # Check for verification nonce
        if m.verification_nonce in content:
            found_nonce = True

    if found_health and found_info and found_nonce:
        return _pass(cid, "/health + /info routes with verification nonce found")

    missing = []
    if not found_health:
        missing.append("/health")
    if not found_info:
        missing.append("/info")
    if not found_nonce:
        missing.append("verification_nonce")

    return _fail(
        cid, "SCAFF_ROUTE_MISSING",
        f"Missing: {', '.join(missing)}",
    )


def _check_custom_router_mounted(ctx: ScaffoldingContext) -> CheckResult:
    cid = "scaff.custom_router_mounted"
    if ctx.toml_data is None:
        return _skip(cid, "TOML not parsed", blocked_by=["scaff.toml_valid"])

    # Check if routes are mentioned in TOML config
    toml_text = (ctx.project_root / "boring.app.toml").read_text(
        encoding="utf-8", errors="replace"
    ) if (ctx.project_root / "boring.app.toml").exists() else ""

    # Look for router registration in Python
    for py_file in ctx.project_root.rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        # Common mounting patterns
        if any(pattern in content for pattern in [
            "include_router",
            "add_api_route",
            "mount(",
            ".include(",
            "app.router",
        ]):
            return _pass(
                cid,
                f"Router mounting found in {py_file.relative_to(ctx.project_root)}",
            )

    # TOML-based routing
    if "routers" in toml_text or "routes" in toml_text:
        return _pass(cid, "Router config found in boring.app.toml")

    return _fail(
        cid, "SCAFF_ROUTE_MISSING",
        "No router mounting pattern found in Python or TOML",
    )


def _check_frontend_present_if_profiled(ctx: ScaffoldingContext) -> CheckResult:
    cid = "scaff.frontend_present_if_profiled"
    profile = ctx.manifest.platform_profile

    # Only check if profile requires frontend
    if profile not in ("full-stack", "extensible"):
        return _pass(cid, f"Profile {profile!r} does not require frontend")

    # Look for frontend artifacts
    for pattern in ["index.html", "package.json", "src/front", "frontend"]:
        if list(ctx.project_root.glob(f"**/{pattern}")):
            return _pass(cid, f"Frontend artifact found: {pattern}")

    return _fail(
        cid, "SCAFF_DIR_MISSING",
        "No frontend artifact found (required for full-stack/extensible)",
    )


def _check_deploy_platform_fly(ctx: ScaffoldingContext) -> CheckResult:
    cid = "scaff.deploy_platform_fly"
    if ctx.toml_data is None:
        return _skip(cid, "TOML not parsed", blocked_by=["scaff.toml_valid"])

    deploy = ctx.toml_data.get("deploy", {})
    platform = deploy.get("platform", "")

    if platform.lower() == "fly":
        return _pass(cid, "deploy.platform = fly")

    # Also check for fly-specific config
    if "fly" in deploy:
        return _pass(cid, "deploy.fly section present")

    # Check for fly.toml in project
    fly_toml = list(ctx.project_root.rglob("fly.toml"))
    if fly_toml:
        return _pass(cid, f"fly.toml found: {fly_toml[0].relative_to(ctx.project_root)}")

    if not platform:
        return _fail(cid, "SCAFF_TOML_FIELD_MISSING", "[deploy].platform not set")

    return _fail(
        cid, "SCAFF_TOML_FIELD_MISMATCH",
        f"[deploy].platform = {platform!r}, expected 'fly'",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize(s: str) -> str:
    """Normalize a name for comparison (lowercase, replace hyphens with underscores)."""
    return s.lower().replace("-", "_").replace(" ", "_")
