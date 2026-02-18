"""Startup health and compatibility checks for sandbox mode.

When WORKSPACE_MODE=sandbox, these checks validate that the workspace
service is reachable, healthy, and version-compatible before the control
plane accepts traffic.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from .config import SandboxConfig
from .internal_auth import generate_auth_token
from .workspace_contract import (
    WORKSPACE_API_VERSION_HEADER,
    CURRENT_VERSION,
    is_compatible,
)

logger = logging.getLogger(__name__)


class StartupCheckError(RuntimeError):
    """Raised when a startup health check fails."""

    def __init__(self, failures: list[str]):
        self.failures = failures
        formatted = '\n'.join(f'- {f}' for f in failures)
        super().__init__(f'Startup checks failed:\n{formatted}')


@dataclass(frozen=True)
class CheckResult:
    """Result of a single startup check."""
    name: str
    passed: bool
    detail: str = ''


def build_workspace_service_url(sandbox: SandboxConfig) -> str:
    """Build the base URL for the workspace service."""
    target = sandbox.service_target
    path = target.path.rstrip('/')
    return f'http://{target.host}:{target.port}{path}'


def build_startup_headers(sandbox: SandboxConfig) -> dict[str, str]:
    """Build headers used for startup probes."""
    return {
        'X-Workspace-Internal-Auth': generate_auth_token(sandbox.api_token),
        WORKSPACE_API_VERSION_HEADER: CURRENT_VERSION,
    }


async def check_healthz(
    base_url: str,
    timeout: float = 5.0,
    *,
    headers: dict[str, str] | None = None,
) -> CheckResult:
    """Check workspace service /healthz endpoint."""
    url = f'{base_url}/healthz'
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, headers=headers or {})
        if resp.status_code != 200:
            return CheckResult('healthz', False, f'Status {resp.status_code}')
        data = resp.json()
        status = data.get('status', 'unknown')
        if status not in ('ok', 'degraded'):
            return CheckResult('healthz', False, f'Unexpected status: {status}')
        return CheckResult('healthz', True, f'status={status}')
    except httpx.ConnectError:
        return CheckResult('healthz', False, f'Connection refused: {url}')
    except httpx.TimeoutException:
        return CheckResult('healthz', False, f'Timeout after {timeout}s: {url}')
    except Exception as exc:
        return CheckResult('healthz', False, f'Unexpected error: {exc}')


async def check_version(
    base_url: str,
    timeout: float = 5.0,
    *,
    headers: dict[str, str] | None = None,
) -> CheckResult:
    """Check workspace service version compatibility."""
    url = f'{base_url}/__meta/version'
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, headers=headers or {})
        if resp.status_code != 200:
            return CheckResult('version', False, f'Status {resp.status_code}')
        data = resp.json()
        upstream_version = data.get('version', '')
        if not upstream_version:
            return CheckResult('version', False, 'Missing version field')
        if not is_compatible(upstream_version):
            return CheckResult(
                'version', False,
                f'Incompatible: upstream={upstream_version}, '
                f'control_plane={CURRENT_VERSION}',
            )
        return CheckResult('version', True, f'version={upstream_version}')
    except httpx.ConnectError:
        return CheckResult('version', False, f'Connection refused: {url}')
    except httpx.TimeoutException:
        return CheckResult('version', False, f'Timeout after {timeout}s: {url}')
    except Exception as exc:
        return CheckResult('version', False, f'Unexpected error: {exc}')


async def run_startup_checks(
    sandbox: SandboxConfig,
    *,
    timeout: float = 5.0,
    fail_fast: bool = True,
) -> list[CheckResult]:
    """Run all startup health and compatibility checks.

    Args:
        sandbox: Sandbox configuration with service target
        timeout: HTTP timeout per check in seconds
        fail_fast: If True, raise StartupCheckError on any failure

    Returns:
        List of check results

    Raises:
        StartupCheckError: If fail_fast=True and any check fails
    """
    base_url = build_workspace_service_url(sandbox)
    probe_headers = build_startup_headers(sandbox)
    logger.info('Running startup checks against %s', base_url)

    results = [
        await check_healthz(base_url, timeout=timeout, headers=probe_headers),
        await check_version(base_url, timeout=timeout, headers=probe_headers),
    ]

    for result in results:
        level = 'info' if result.passed else 'error'
        getattr(logger, level)(
            'Startup check [%s]: %s - %s',
            'PASS' if result.passed else 'FAIL',
            result.name,
            result.detail,
        )

    if fail_fast:
        failures = [r.detail for r in results if not r.passed]
        if failures:
            raise StartupCheckError(failures)

    return results
