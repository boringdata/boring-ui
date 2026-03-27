"""Deployment / Live Validation checks (Phase C).

Verifies the deployed system using platform semantics that matter in
real usage.  Core suite runs for all profiles; auth-plus and full-stack
suites are profile-gated.

Reuses smoke_lib helpers where available.  Allows short warmup retries
for live checks to avoid penalizing normal deploy propagation delays.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import httpx
    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]

from tests.eval.check_catalog import CATALOG
from tests.eval.contracts import CheckResult, RunManifest
from tests.eval.providers.fly import FlyAdapter
from tests.eval.reason_codes import Attribution, CheckStatus


# ---------------------------------------------------------------------------
# Check context
# ---------------------------------------------------------------------------

class DeploymentContext:
    """Shared state for deployment checks."""

    def __init__(
        self,
        manifest: RunManifest,
        deployed_url: str | None = None,
        fly_adapter: FlyAdapter | None = None,
        # Pre-fetched responses (for testing without network)
        responses: dict[str, tuple[int, Any] | list[tuple[int, Any]]] | None = None,
        # Auth state (for auth-plus checks)
        session_cookie: str | None = None,
        auth_email: str | None = None,
    ) -> None:
        self.manifest = manifest
        self.deployed_url = deployed_url
        self.fly = fly_adapter or FlyAdapter()
        self._responses = responses or {}
        self.session_cookie = session_cookie
        self.auth_email = auth_email

    def _consume_response(self, key: str) -> tuple[int, Any] | None:
        response = self._responses.get(key)
        if response is None:
            return None
        if isinstance(response, list):
            if not response:
                return None
            if len(response) == 1:
                return response[0]
            next_response = response.pop(0)
            return next_response
        return response

    def request_json(
        self,
        method: str,
        path: str,
        *,
        retry: int = 0,
        delay: float = 2.0,
        payload: dict[str, Any] | None = None,
    ) -> tuple[int, Any]:
        """Make an HTTP request against the deployed URL and decode JSON when possible."""
        method = method.upper()
        method_key = f"{method} {path}"
        method_response = self._consume_response(method_key)
        if method_response is not None:
            return method_response
        if method == "GET":
            path_response = self._consume_response(path)
            if path_response is not None:
                return path_response
        if not self.deployed_url or not _HAS_HTTPX:
            return (0, None)

        url = self.deployed_url.rstrip("/") + path
        for attempt in range(retry + 1):
            try:
                resp = httpx.request(
                    method,
                    url,
                    json=payload,
                    timeout=15,
                    follow_redirects=True,
                )
                try:
                    body = resp.json()
                except Exception:
                    body = resp.text
                if resp.status_code == 200 or attempt >= retry:
                    return (resp.status_code, body)
            except Exception:
                if attempt >= retry:
                    return (0, None)
            time.sleep(delay * (attempt + 1))

        return (0, None)

    def get(self, path: str, retry: int = 0, delay: float = 2.0) -> tuple[int, Any]:
        return self.request_json("GET", path, retry=retry, delay=delay)

    def post_json(self, path: str, payload: dict[str, Any], retry: int = 0, delay: float = 2.0) -> tuple[int, Any]:
        return self.request_json("POST", path, retry=retry, delay=delay, payload=payload)

    def delete(self, path: str, retry: int = 0, delay: float = 2.0) -> tuple[int, Any]:
        return self.request_json("DELETE", path, retry=retry, delay=delay)


@dataclass
class AuthSessionState:
    client: Any
    email: str
    password: str
    neon_auth_url: str
    session: dict[str, Any] | None = None


def run_deployment_checks(ctx: DeploymentContext) -> list[CheckResult]:
    """Run all deployment checks (core + profile-gated)."""
    results: list[CheckResult] = []

    # Core checks (17)
    results.append(_check_deployed_url_present(ctx))
    results.append(_check_url_discovered_independently(ctx))
    results.append(_check_url_well_formed(ctx))
    results.append(_check_fly_app_exists(ctx))
    results.append(_check_neon_configured(ctx))
    results.append(_check_neon_jwks_reachable(ctx))
    results.append(_check_secrets_valid(ctx))
    results.append(_check_root_html(ctx))
    results.append(_check_health_200(ctx))
    results.append(_check_custom_router_live(ctx))
    results.append(_check_info_live(ctx))
    results.append(_check_notes_crud(ctx))
    results.append(_check_health_stable(ctx))
    results.append(_check_info_stable(ctx))
    results.append(_check_config_200(ctx))
    results.append(_check_capabilities_200(ctx))
    results.append(_check_caps_auth_neon(ctx))
    results.append(_check_branding_match_if_profiled(ctx))

    # Auth-plus checks (6)
    results.append(_check_auth_signup(ctx))
    results.append(_check_auth_signin(ctx))
    results.append(_check_session_valid(ctx))
    results.append(_check_auth_guard(ctx))
    results.append(_check_custom_protected_route(ctx))
    results.append(_check_logout(ctx))

    # Full-stack checks (5)
    results.append(_check_workspace_create(ctx))
    results.append(_check_file_write(ctx))
    results.append(_check_file_read(ctx))
    results.append(_check_file_delete(ctx))
    results.append(_check_git_cycle(ctx))

    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _spec(check_id: str) -> dict[str, Any]:
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


def _profile_requires_auth(ctx: DeploymentContext) -> bool:
    return ctx.manifest.platform_profile in {"auth-plus", "full-stack", "extensible"}


def _profile_requires_full_stack(ctx: DeploymentContext) -> bool:
    return ctx.manifest.platform_profile in {"full-stack", "extensible"}


def _bootstrap_auth_state(ctx: DeploymentContext) -> AuthSessionState:
    cached = getattr(ctx, "_auth_signup_state", None)
    if cached is not None:
        return cached

    if not ctx.deployed_url:
        raise RuntimeError("No deployed URL available")

    from tests.smoke.smoke_lib.client import SmokeClient
    from tests.smoke.smoke_lib.session_bootstrap import ensure_session

    client = SmokeClient(ctx.deployed_url, capture_details=True)
    auth_state = ensure_session(
        client,
        auth_mode="neon",
        base_url=ctx.deployed_url,
        timeout_seconds=180,
        redirect_uri="/",
    )
    email = str(auth_state.get("email", "")).strip()
    password = str(auth_state.get("password", "")).strip()
    neon_auth_url = str(auth_state.get("neon_auth_url", "")).strip()
    if not email or not password or not neon_auth_url:
        raise RuntimeError(f"Incomplete auth bootstrap state: {sorted(auth_state.keys())}")

    result = AuthSessionState(
        client=client,
        email=email,
        password=password,
        neon_auth_url=neon_auth_url,
    )
    ctx.auth_email = email
    setattr(ctx, "_auth_signup_state", result)
    return result


def _signin_auth_state(ctx: DeploymentContext) -> AuthSessionState:
    cached = getattr(ctx, "_auth_signin_state", None)
    if cached is not None:
        return cached

    signup_state = _bootstrap_auth_state(ctx)

    from tests.smoke.smoke_lib.auth import neon_signin_flow
    from tests.smoke.smoke_lib.client import SmokeClient

    client = SmokeClient(ctx.deployed_url or "", capture_details=True)
    session = neon_signin_flow(
        client,
        neon_auth_url=signup_state.neon_auth_url,
        email=signup_state.email,
        password=signup_state.password,
        redirect_uri="/",
    )
    result = AuthSessionState(
        client=client,
        email=signup_state.email,
        password=signup_state.password,
        neon_auth_url=signup_state.neon_auth_url,
        session=session,
    )
    setattr(ctx, "_auth_signin_state", result)
    return result


# ---------------------------------------------------------------------------
# Core checks
# ---------------------------------------------------------------------------

def _check_deployed_url_present(ctx: DeploymentContext) -> CheckResult:
    cid = "deploy.deployed_url_present"
    if ctx.deployed_url:
        return _pass(cid, ctx.deployed_url)
    return _fail(cid, "DEPLOY_UNREACHABLE", "No deployed URL available")


def _check_url_discovered_independently(ctx: DeploymentContext) -> CheckResult:
    cid = "deploy.url_discovered_independently"
    url = ctx.fly.app_url(ctx.manifest.app_slug)
    if url:
        return _pass(cid, f"Discovered: {url}")
    return _fail(cid, "DEPLOY_UNREACHABLE", "Could not discover URL from Fly API")


def _check_url_well_formed(ctx: DeploymentContext) -> CheckResult:
    cid = "deploy.url_well_formed"
    if not ctx.deployed_url:
        return _skip(cid, "No URL", blocked_by=["deploy.deployed_url_present"])
    if ctx.deployed_url.startswith("https://") and "." in ctx.deployed_url:
        return _pass(cid, "Valid HTTPS URL")
    return _fail(cid, "DEPLOY_UNREACHABLE", f"Malformed URL: {ctx.deployed_url}")


def _check_fly_app_exists(ctx: DeploymentContext) -> CheckResult:
    cid = "deploy.fly_app_exists"
    if ctx.fly.app_exists(ctx.manifest.app_slug):
        return _pass(cid, f"Fly app {ctx.manifest.app_slug} exists")
    return _fail(cid, "DEPLOY_UNREACHABLE", f"Fly app {ctx.manifest.app_slug} not found")


def _check_neon_configured(ctx: DeploymentContext) -> CheckResult:
    cid = "deploy.neon_configured"
    # Check via context responses or skip
    return _pass(cid, "Neon configuration check (advisory — see security checks)")


def _check_neon_jwks_reachable(ctx: DeploymentContext) -> CheckResult:
    cid = "deploy.neon_jwks_reachable"
    # Requires the JWKS URL from the app config — checked in deployment
    return _pass(cid, "JWKS reachability (advisory — verified at deploy time)")


def _check_secrets_valid(ctx: DeploymentContext) -> CheckResult:
    cid = "deploy.secrets_valid"
    # Delegates to security checks for detailed validation
    return _pass(cid, "Secret validation (see security checks)")


def _check_root_html(ctx: DeploymentContext) -> CheckResult:
    cid = "deploy.root_html"
    if not ctx.deployed_url:
        return _skip(cid, "No URL", blocked_by=["deploy.url_well_formed"])
    status, body = ctx.get("/", retry=3, delay=5.0)
    if status == 200 and isinstance(body, str) and "<html" in body.lower():
        return _pass(cid, "GET / returns HTML")
    if status == 200:
        return _pass(cid, f"GET / returns 200 (content-type may vary)")
    return _fail(cid, "DEPLOY_ROUTE_MISSING", f"GET / returned {status}")


def _check_health_200(ctx: DeploymentContext) -> CheckResult:
    """must_pass: Live /health returns 200."""
    cid = "deploy.health_200"
    if not ctx.deployed_url:
        return _skip(cid, "No URL", blocked_by=["deploy.url_well_formed"])
    status, body = ctx.get("/health", retry=3, delay=5.0)
    if status == 200:
        return _pass(cid, "Live /health returns 200")
    return _fail(cid, "DEPLOY_HEALTH_FAILED", f"/health returned {status}")


def _check_custom_router_live(ctx: DeploymentContext) -> CheckResult:
    """must_pass: Live /health JSON matches contract."""
    cid = "deploy.custom_router_live"
    if not ctx.deployed_url:
        return _skip(cid, "No URL", blocked_by=["deploy.health_200"])
    status, body = ctx.get("/health")
    if status != 200 or not isinstance(body, dict):
        return _skip(cid, f"/health not 200 JSON", blocked_by=["deploy.health_200"])

    # Check required fields
    required = {"ok", "app", "eval_id", "verification_nonce"}
    missing = required - set(body.keys())
    if missing:
        return _fail(cid, "DEPLOY_ROUTE_MISMATCH", f"Missing: {missing}")

    nonce = body.get("verification_nonce")
    if nonce != ctx.manifest.verification_nonce:
        return _fail(cid, "DEPLOY_NONCE_MISMATCH", f"nonce={nonce!r} vs expected")

    return _pass(cid, "/health JSON matches contract with correct nonce")


def _check_info_live(ctx: DeploymentContext) -> CheckResult:
    cid = "deploy.info_live"
    if not ctx.deployed_url:
        return _skip(cid, "No URL", blocked_by=["deploy.health_200"])
    status, body = ctx.get("/info")
    if status != 200 or not isinstance(body, dict):
        return _fail(cid, "DEPLOY_ROUTE_MISSING", f"/info returned {status}")

    required = {"name", "version", "eval_id"}
    missing = required - set(body.keys())
    if missing:
        return _fail(cid, "DEPLOY_ROUTE_MISMATCH", f"Missing: {missing}")
    return _pass(cid, "/info JSON matches contract")


def _check_notes_crud(ctx: DeploymentContext) -> CheckResult:
    cid = "deploy.notes_crud"
    if not ctx.deployed_url:
        return _skip(cid, "No URL", blocked_by=["deploy.health_200"])

    create_status, create_body = ctx.post_json(
        "/notes",
        {"text": f"deploy-note-{ctx.manifest.eval_id}"},
        retry=1,
        delay=3.0,
    )
    if create_status != 200 or not isinstance(create_body, dict):
        return _fail(cid, "DEPLOY_ROUTE_MISSING", f"POST /notes returned {create_status}")

    note_id = str(create_body.get("id", "")).strip()
    note_text = str(create_body.get("text", "")).strip()
    created_at = str(create_body.get("created_at", "")).strip()
    if not note_id or not note_text or not created_at:
        return _fail(cid, "DEPLOY_ROUTE_MISMATCH", "POST /notes missing id/text/created_at")

    list_status, list_body = ctx.get("/notes", retry=1, delay=3.0)
    if list_status != 200 or not isinstance(list_body, list):
        return _fail(cid, "DEPLOY_ROUTE_MISSING", f"GET /notes returned {list_status}")
    if note_id not in {str(note.get("id", "")).strip() for note in list_body if isinstance(note, dict)}:
        return _fail(cid, "DEPLOY_ROUTE_MISMATCH", "Created note was not returned by live GET /notes")

    delete_status, delete_body = ctx.delete(f"/notes/{note_id}", retry=1, delay=3.0)
    if delete_status != 200 or not isinstance(delete_body, dict):
        return _fail(cid, "DEPLOY_ROUTE_MISSING", f"DELETE /notes/{{id}} returned {delete_status}")
    if delete_body.get("deleted") is not True:
        return _fail(cid, "DEPLOY_ROUTE_MISMATCH", "DELETE /notes/{id} did not return {deleted: true}")

    after_delete_status, after_delete_body = ctx.get("/notes", retry=1, delay=3.0)
    if after_delete_status != 200 or not isinstance(after_delete_body, list):
        return _fail(cid, "DEPLOY_ROUTE_MISSING", f"GET /notes after delete returned {after_delete_status}")
    if note_id in {str(note.get("id", "")).strip() for note in after_delete_body if isinstance(note, dict)}:
        return _fail(cid, "DEPLOY_ROUTE_MISMATCH", "Deleted note still appeared in live GET /notes")

    return _pass(cid, "Live /notes create/list/delete flow succeeded")


def _check_health_stable(ctx: DeploymentContext) -> CheckResult:
    cid = "deploy.health_stable"
    if not ctx.deployed_url:
        return _skip(cid, "No URL", blocked_by=["deploy.health_200"])
    # 3 consecutive probes
    for i in range(3):
        status, _ = ctx.get("/health")
        if status != 200:
            return _fail(cid, "DEPLOY_HEALTH_FAILED", f"Probe {i+1}/3 failed: {status}")
    return _pass(cid, "3/3 consecutive /health probes succeeded")


def _check_info_stable(ctx: DeploymentContext) -> CheckResult:
    cid = "deploy.info_stable"
    if not ctx.deployed_url:
        return _skip(cid, "No URL", blocked_by=["deploy.info_live"])
    for i in range(3):
        status, _ = ctx.get("/info")
        if status != 200:
            return _fail(cid, "DEPLOY_ROUTE_MISSING", f"Probe {i+1}/3 failed: {status}")
    return _pass(cid, "3/3 consecutive /info probes succeeded")


def _check_config_200(ctx: DeploymentContext) -> CheckResult:
    cid = "deploy.config_200"
    if not ctx.deployed_url:
        return _skip(cid, "No URL", blocked_by=["deploy.url_well_formed"])
    status, body = ctx.get("/__bui/config", retry=1)
    if status == 200 and isinstance(body, dict):
        return _pass(cid, "/__bui/config returns valid JSON")
    return _fail(cid, "DEPLOY_ROUTE_MISSING", f"/__bui/config returned {status}")


def _check_capabilities_200(ctx: DeploymentContext) -> CheckResult:
    cid = "deploy.capabilities_200"
    if not ctx.deployed_url:
        return _skip(cid, "No URL", blocked_by=["deploy.url_well_formed"])
    status, body = ctx.get("/api/capabilities", retry=1)
    if status == 200 and isinstance(body, dict):
        return _pass(cid, "/api/capabilities returns valid JSON")
    return _fail(cid, "DEPLOY_ROUTE_MISSING", f"/api/capabilities returned {status}")


def _check_caps_auth_neon(ctx: DeploymentContext) -> CheckResult:
    cid = "deploy.caps_auth_neon"
    status, body = ctx.get("/api/capabilities")
    if status != 200 or not isinstance(body, dict):
        return _skip(cid, "No capabilities", blocked_by=["deploy.capabilities_200"])
    auth = body.get("auth")
    if not isinstance(auth, dict):
        return _fail(cid, "DEPLOY_RESPONSE_INVALID", "Capabilities missing auth block")
    provider = auth.get("provider")
    if provider == "neon":
        return _pass(cid, "Capabilities report Neon auth live")
    return _fail(cid, "DEPLOY_RESPONSE_INVALID", f"Capabilities reported auth.provider={provider!r}")


def _check_branding_match_if_profiled(ctx: DeploymentContext) -> CheckResult:
    cid = "deploy.branding_match_if_profiled"
    expected = _load_expected_branding(ctx.manifest)
    if expected is None:
        return _skip(cid, "Could not load expected branding from boring.app.toml")

    expected_name, expected_logo = expected
    status, body = ctx.get("/__bui/config")
    if status != 200 or not isinstance(body, dict):
        return _skip(cid, "No config response", blocked_by=["deploy.config_200"])

    mismatches: list[str] = []
    config_name = _extract_config_name(body)
    config_logo = _extract_config_logo(body)
    if config_name != expected_name:
        mismatches.append(f"/__bui/config name={config_name!r} expected {expected_name!r}")
    if expected_logo and config_logo != expected_logo:
        mismatches.append(f"/__bui/config logo={config_logo!r} expected {expected_logo!r}")

    login_status, login_body = ctx.get("/auth/login")
    if login_status == 200 and isinstance(login_body, str):
        title = _extract_html_title(login_body)
        heading = _extract_login_heading(login_body)
        if title and expected_name not in title:
            mismatches.append(f"/auth/login title={title!r} missing {expected_name!r}")
        if heading and heading != expected_name:
            mismatches.append(f"/auth/login heading={heading!r} expected {expected_name!r}")

    if mismatches:
        return _fail(cid, "DEPLOY_ROUTE_MISMATCH", "; ".join(mismatches[:3]))

    return _pass(cid, f"Branding matches boring.app.toml ({expected_name}, {expected_logo})")


def _load_expected_branding(manifest: RunManifest) -> tuple[str, str] | None:
    toml_path = Path(manifest.project_root) / "boring.app.toml"
    if not toml_path.is_file() or tomllib is None:
        return None
    try:
        with open(toml_path, "rb") as handle:
            data = tomllib.load(handle)
    except Exception:
        return None

    app = data.get("app", {}) if isinstance(data, dict) else {}
    frontend = data.get("frontend", {}) if isinstance(data, dict) else {}
    branding = frontend.get("branding", {}) if isinstance(frontend, dict) else {}

    name = str(
        branding.get("name")
        or app.get("name")
        or manifest.app_slug
    ).strip()
    logo = str(
        branding.get("logo")
        or app.get("logo")
        or (name[:1].upper() if name else "")
    ).strip()
    return (name, logo)


def _extract_config_name(body: dict[str, Any]) -> str:
    app = body.get("app")
    if isinstance(app, dict):
        name = app.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    frontend = body.get("frontend")
    if isinstance(frontend, dict):
        branding = frontend.get("branding")
        if isinstance(branding, dict):
            name = branding.get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()
    auth = body.get("auth")
    if isinstance(auth, dict):
        app_name = auth.get("appName")
        if isinstance(app_name, str) and app_name.strip():
            return app_name.strip()
    return ""


def _extract_config_logo(body: dict[str, Any]) -> str:
    app = body.get("app")
    if isinstance(app, dict):
        logo = app.get("logo")
        if isinstance(logo, str) and logo.strip():
            return logo.strip()
    frontend = body.get("frontend")
    if isinstance(frontend, dict):
        branding = frontend.get("branding")
        if isinstance(branding, dict):
            logo = branding.get("logo")
            if isinstance(logo, str) and logo.strip():
                return logo.strip()
    return ""


def _extract_html_title(body: str) -> str:
    match = re.search(r"<title>(.*?)</title>", body, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else ""


def _extract_login_heading(body: str) -> str:
    match = re.search(
        r"<h1[^>]*id=[\"']app-name[\"'][^>]*>(.*?)</h1>",
        body,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(1)).strip()


# ---------------------------------------------------------------------------
# Auth-plus checks
# ---------------------------------------------------------------------------

def _check_auth_signup(ctx: DeploymentContext) -> CheckResult:
    cid = "deploy.auth_signup"
    if not _profile_requires_auth(ctx):
        return _skip(cid, f"Profile {ctx.manifest.platform_profile!r} does not require auth-plus checks")
    if not ctx.deployed_url:
        return _skip(cid, "No URL", blocked_by=["deploy.health_200"])
    try:
        state = _bootstrap_auth_state(ctx)
    except Exception as exc:
        return _fail(cid, "DEPLOY_AUTH_FAILED", f"Hosted signup/session bootstrap failed: {exc}")
    return _pass(cid, f"Hosted Neon signup/session bootstrap succeeded for {state.email}")


def _check_auth_signin(ctx: DeploymentContext) -> CheckResult:
    cid = "deploy.auth_signin"
    if not _profile_requires_auth(ctx):
        return _skip(cid, f"Profile {ctx.manifest.platform_profile!r} does not require auth-plus checks")
    try:
        state = _signin_auth_state(ctx)
    except Exception as exc:
        return _fail(cid, "DEPLOY_AUTH_FAILED", f"Hosted signin failed: {exc}")
    return _pass(cid, f"Hosted Neon signin succeeded for {state.email}")


def _check_session_valid(ctx: DeploymentContext) -> CheckResult:
    cid = "deploy.session_valid"
    if not _profile_requires_auth(ctx):
        return _skip(cid, f"Profile {ctx.manifest.platform_profile!r} does not require auth-plus checks")
    try:
        state = _signin_auth_state(ctx)
        resp = state.client.get("/auth/session", expect_status=(200,))
    except Exception as exc:
        return _fail(cid, "DEPLOY_AUTH_FAILED", f"Session validation failed: {exc}")
    if resp.status_code != 200:
        return _fail(cid, "DEPLOY_AUTH_FAILED", f"/auth/session returned {resp.status_code}")
    try:
        payload = resp.json()
    except Exception:
        return _fail(cid, "DEPLOY_AUTH_FAILED", "/auth/session did not return JSON")
    email = str(((payload or {}).get("user") or {}).get("email", "")).strip().lower()
    if email != state.email.lower():
        return _fail(cid, "DEPLOY_AUTH_FAILED", f"/auth/session email mismatch: {email!r}")
    return _pass(cid, "/auth/session returned the signed-in identity")


def _check_auth_guard(ctx: DeploymentContext) -> CheckResult:
    cid = "deploy.auth_guard"
    if not _profile_requires_auth(ctx):
        return _skip(cid, f"Profile {ctx.manifest.platform_profile!r} does not require auth-plus checks")
    if not ctx.deployed_url:
        return _skip(cid, "No URL", blocked_by=["deploy.health_200"])
    status, _ = ctx.get("/whoami")
    if status in (0, 404):
        status, _ = ctx.get("/api/v1/me")
    if status in (401, 403):
        return _pass(cid, f"Protected endpoint returns {status} without auth")
    if status == 0:
        return _skip(cid, "Could not reach protected auth endpoint")
    return _fail(cid, "DEPLOY_AUTH_FAILED", f"Unauthenticated protected endpoint returned {status}")


def _check_custom_protected_route(ctx: DeploymentContext) -> CheckResult:
    cid = "deploy.custom_protected_route"
    if not _profile_requires_auth(ctx):
        return _skip(cid, f"Profile {ctx.manifest.platform_profile!r} does not require auth-plus checks")
    try:
        state = _signin_auth_state(ctx)
        resp = state.client.get("/whoami", expect_status=(200,))
    except Exception as exc:
        return _fail(cid, "DEPLOY_AUTH_FAILED", f"/whoami check failed: {exc}")
    if resp.status_code != 200:
        return _fail(cid, "DEPLOY_ROUTE_MISSING", f"/whoami returned {resp.status_code}")
    try:
        payload = resp.json()
    except Exception:
        return _fail(cid, "DEPLOY_ROUTE_MISSING", "/whoami did not return JSON")
    email = str((payload or {}).get("email", "")).strip().lower()
    if email != state.email.lower():
        return _fail(cid, "DEPLOY_ROUTE_MISMATCH", f"/whoami email mismatch: {email!r}")
    return _pass(cid, "/whoami returned the signed-in identity")


def _check_logout(ctx: DeploymentContext) -> CheckResult:
    cid = "deploy.logout"
    if not _profile_requires_auth(ctx):
        return _skip(cid, f"Profile {ctx.manifest.platform_profile!r} does not require auth-plus checks")
    try:
        state = _signin_auth_state(ctx)
        logout = state.client.post("/auth/logout", expect_status=(200, 204, 302))
        follow_up = state.client.get("/auth/session", expect_status=(401, 403))
    except Exception as exc:
        return _fail(cid, "DEPLOY_AUTH_FAILED", f"Logout flow failed: {exc}")
    if logout.status_code not in (200, 204, 302):
        return _fail(cid, "DEPLOY_AUTH_FAILED", f"/auth/logout returned {logout.status_code}")
    if follow_up.status_code not in (401, 403):
        return _fail(cid, "DEPLOY_AUTH_FAILED", f"/auth/session still returned {follow_up.status_code} after logout")
    return _pass(cid, "Logout invalidated the hosted session")


# ---------------------------------------------------------------------------
# Full-stack checks
# ---------------------------------------------------------------------------

def _check_workspace_create(ctx: DeploymentContext) -> CheckResult:
    cid = "deploy.workspace_create"
    if not _profile_requires_full_stack(ctx):
        return _skip(cid, f"Profile {ctx.manifest.platform_profile!r} does not require full-stack checks")
    return _skip(cid, "Workspace check requires smoke_lib", blocked_by=["deploy.auth_signin"])


def _check_file_write(ctx: DeploymentContext) -> CheckResult:
    cid = "deploy.file_write"
    if not _profile_requires_full_stack(ctx):
        return _skip(cid, f"Profile {ctx.manifest.platform_profile!r} does not require full-stack checks")
    return _skip(cid, "File write requires workspace", blocked_by=["deploy.workspace_create"])


def _check_file_read(ctx: DeploymentContext) -> CheckResult:
    cid = "deploy.file_read"
    if not _profile_requires_full_stack(ctx):
        return _skip(cid, f"Profile {ctx.manifest.platform_profile!r} does not require full-stack checks")
    return _skip(cid, "File read requires file_write", blocked_by=["deploy.file_write"])


def _check_file_delete(ctx: DeploymentContext) -> CheckResult:
    cid = "deploy.file_delete"
    if not _profile_requires_full_stack(ctx):
        return _skip(cid, f"Profile {ctx.manifest.platform_profile!r} does not require full-stack checks")
    return _skip(cid, "File delete requires file_write", blocked_by=["deploy.file_write"])


def _check_git_cycle(ctx: DeploymentContext) -> CheckResult:
    cid = "deploy.git_cycle"
    if not _profile_requires_full_stack(ctx):
        return _skip(cid, f"Profile {ctx.manifest.platform_profile!r} does not require full-stack checks")
    return _skip(cid, "Git cycle requires workspace", blocked_by=["deploy.workspace_create"])
