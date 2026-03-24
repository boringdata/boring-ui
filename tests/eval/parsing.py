"""Response extraction and URL discovery for the eval harness.

Extracts structured data from the agent's raw output: JSON report block,
deployed URL, resource IDs, and Neon project ID.

Agent-reported values are advisory. The harness should independently discover
the deployed URL from provider state when possible. Discrepancies between
agent-reported and harness-discovered values feed into report truthfulness checks.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Protocol

from tests.eval.contracts import RunManifest
from tests.eval.report_schema import extract_report_from_text


# ---------------------------------------------------------------------------
# Report extraction (delegates to report_schema)
# ---------------------------------------------------------------------------

def extract_report_json(text: str) -> dict[str, Any] | None:
    """Extract the machine-readable report JSON from agent output.

    Delegates to ``report_schema.extract_report_from_text`` which tries:
    1. Explicit BEGIN/END markers
    2. Fenced JSON code block
    3. Bare JSON fallback

    Returns the parsed dict or None.
    """
    return extract_report_from_text(text)


# ---------------------------------------------------------------------------
# URL extraction
# ---------------------------------------------------------------------------

# Fly.io URL patterns
_FLY_URL_RE = re.compile(
    r"https://([a-z0-9][a-z0-9-]*[a-z0-9])\.fly\.dev",
    re.IGNORECASE,
)

# Generic deployed URL (https with common app-hosting domains)
_DEPLOYED_URL_RE = re.compile(
    r"https://([a-z0-9][a-z0-9.-]*)\.(fly\.dev|onrender\.com|railway\.app|herokuapp\.com)",
    re.IGNORECASE,
)


def extract_deployed_url(
    text: str,
    manifest: RunManifest | None = None,
) -> str | None:
    """Extract the deployed URL from agent output.

    Strategy:
    1. Check extracted JSON report for ``deployed_url`` field.
    2. Regex for Fly.io URLs matching the expected app slug.
    3. Regex for any Fly.io URL.

    Returns the URL string or None.
    """
    # Strategy 1: from JSON report
    report = extract_report_from_text(text)
    if report:
        url = report.get("deployed_url")
        if url and isinstance(url, str) and url.startswith("https://"):
            return url

    # Strategy 2: Fly URL matching manifest app_slug
    if manifest:
        expected = f"https://{manifest.app_slug}.fly.dev"
        if expected in text:
            return expected

    # Strategy 3: any Fly URL
    m = _FLY_URL_RE.search(text)
    if m:
        return m.group(0)

    # Strategy 4: any deployed URL
    m = _DEPLOYED_URL_RE.search(text)
    if m:
        return m.group(0)

    return None


# ---------------------------------------------------------------------------
# Fly app name extraction
# ---------------------------------------------------------------------------

def extract_fly_app_name(
    text: str,
    manifest: RunManifest | None = None,
) -> str | None:
    """Extract the Fly app name from agent output or manifest.

    Tries:
    1. JSON report ``fly_app_name`` field
    2. JSON report ``resource_inventory.fly_app_name``
    3. Manifest-derived app_slug
    """
    report = extract_report_from_text(text)
    if report:
        name = report.get("fly_app_name")
        if name and isinstance(name, str):
            return name
        inv = report.get("resource_inventory", {})
        if isinstance(inv, dict):
            name = inv.get("fly_app_name")
            if name and isinstance(name, str):
                return name

    if manifest:
        return manifest.app_slug

    return None


# ---------------------------------------------------------------------------
# Neon project ID extraction
# ---------------------------------------------------------------------------

def extract_neon_project_id(
    project_root: str | Path,
    text: str = "",
) -> str | None:
    """Extract Neon project ID from the generated app config or agent output.

    Tries:
    1. Read ``boring.app.toml`` from project_root and look for Neon project config.
    2. Check extracted JSON report.
    """
    # Strategy 1: from boring.app.toml
    toml_path = Path(project_root) / "boring.app.toml"
    if toml_path.exists():
        content = toml_path.read_text(encoding="utf-8")
        # Look for neon project_id in TOML
        m = re.search(r'project(?:_id)?\s*=\s*"([^"]+)"', content)
        if m:
            val = m.group(1)
            # Heuristic: Neon project IDs look like alphanumeric with dashes
            if not val.startswith("/") and not val.startswith("http"):
                return val

    # Strategy 2: from .boring/neon-config.env
    neon_env = Path(project_root) / ".boring" / "neon-config.env"
    if neon_env.exists():
        content = neon_env.read_text(encoding="utf-8")
        m = re.search(r'NEON_PROJECT_ID=(.+)', content)
        if m:
            return m.group(1).strip().strip('"')

    # Strategy 3: from agent text/report
    if text:
        report = extract_report_from_text(text)
        if report:
            nid = report.get("neon_project_id")
            if nid and isinstance(nid, str):
                return nid

    return None


# ---------------------------------------------------------------------------
# Provider-independent URL discovery
# ---------------------------------------------------------------------------

class FlyAdapter(Protocol):
    """Protocol for Fly provider adapter (for URL discovery)."""

    def app_exists(self, app_name: str) -> bool: ...
    def app_url(self, app_name: str) -> str | None: ...


def discover_url_from_provider(
    fly_adapter: FlyAdapter,
    app_name: str,
) -> str | None:
    """Independently discover the deployed URL from the Fly API.

    Returns the discovered URL or None if the app doesn't exist.
    """
    if not fly_adapter.app_exists(app_name):
        return None
    return fly_adapter.app_url(app_name)


# ---------------------------------------------------------------------------
# Command extraction
# ---------------------------------------------------------------------------

_BUI_CMD_RE = re.compile(r"bui\s+(init|doctor|deploy|neon\s+setup|dev)\b[^\n]*")


def extract_bui_commands(text: str) -> list[str]:
    """Extract bui CLI commands from agent output text."""
    return [m.group(0).strip() for m in _BUI_CMD_RE.finditer(text)]


# ---------------------------------------------------------------------------
# Vault ref extraction
# ---------------------------------------------------------------------------

def extract_vault_refs_from_report(
    text: str,
) -> list[dict[str, str]]:
    """Extract Vault secret references from the agent's report JSON."""
    report = extract_report_from_text(text)
    if not report:
        return []
    refs = report.get("vault_secret_refs", [])
    if not isinstance(refs, list):
        return []
    return [r for r in refs if isinstance(r, dict) and "name" in r]
