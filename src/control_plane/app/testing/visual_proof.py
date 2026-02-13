"""Visual proof capture for scenario-driven evidence collection.

Bead: bd-223o.16.4 (K4)

Implements the Showboat/Rodney-compatible workflow:
  - BrowserCapture: Playwright-based screenshot/HAR collection.
  - ProofSession: Per-scenario evidence aggregator tied to step IDs.
  - EvidenceArtifact: Typed evidence record with path + metadata.

Usage::

    config = CaptureConfig(output_dir=Path('evidence'))
    session = ProofSession(config, scenario_id='S-001')

    # Record API evidence from scenario runner results.
    session.record_api_response(step=2, method='GET', path='/api/v1/me',
                                status=200, body={'user_id': 'u1'})

    # Capture screenshot via Playwright subprocess.
    await session.capture_screenshot(step=1, description='Login page',
                                     url='http://localhost:5173/login')

    artifacts = session.finalize()
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class ArtifactType(str, Enum):
    """Type of evidence artifact."""

    SCREENSHOT = 'screenshot'
    HAR = 'har'
    API_RESPONSE = 'api_response'
    LOG_ENTRY = 'log_entry'


@dataclass(frozen=True, slots=True)
class EvidenceArtifact:
    """A single piece of captured evidence."""

    artifact_type: ArtifactType
    step_number: int
    description: str
    file_path: str  # Relative to output directory.
    timestamp: str  # ISO-8601
    scenario_id: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            'type': self.artifact_type.value,
            'step': self.step_number,
            'description': self.description,
            'file': self.file_path,
            'timestamp': self.timestamp,
            'scenario_id': self.scenario_id,
            'metadata': self.metadata,
        }


@dataclass(frozen=True, slots=True)
class CaptureConfig:
    """Configuration for visual proof capture."""

    output_dir: Path
    viewport_width: int = 1280
    viewport_height: int = 720
    screenshot_format: str = 'png'
    full_page: bool = False
    timeout_ms: int = 15000


class BrowserCapture:
    """Low-level browser screenshot capture via Playwright subprocess.

    Uses ``npx playwright`` to avoid requiring the Python playwright
    package.  Each call spawns a short-lived Chromium instance via a
    small inline script passed to ``node -e``.
    """

    def __init__(self, config: CaptureConfig) -> None:
        self._config = config

    async def screenshot(
        self,
        url: str,
        output_path: Path,
        *,
        full_page: bool | None = None,
    ) -> Path:
        """Capture a screenshot of *url* and write it to *output_path*.

        Returns the resolved output path on success.

        Raises:
            RuntimeError: If the Playwright process fails.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        fp = 'true' if (full_page if full_page is not None
                        else self._config.full_page) else 'false'
        w = self._config.viewport_width
        h = self._config.viewport_height
        timeout = self._config.timeout_ms

        # Inline Node script that uses Playwright's chromium launcher.
        script = (
            "const { chromium } = require('playwright');"
            '(async () => {'
            f"  const browser = await chromium.launch();"
            f"  const page = await browser.newPage({{viewport: {{width: {w}, height: {h}}}}});"
            f"  await page.goto('{_escape_js(url)}', {{timeout: {timeout}, waitUntil: 'commit'}});"
            f"  await page.screenshot({{path: '{_escape_js(str(output_path))}', fullPage: {fp}}});"
            '  await browser.close();'
            '})();'
        )

        proc = await asyncio.create_subprocess_exec(
            'node', '-e', script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(
                f'Playwright screenshot failed (rc={proc.returncode}): '
                f'{stderr.decode(errors="replace").strip()}'
            )

        return output_path


class ProofSession:
    """Collects evidence artifacts for a single scenario run.

    The session creates a per-scenario sub-directory inside
    ``CaptureConfig.output_dir`` and records artifacts as they are
    captured.  Call :meth:`finalize` to get the complete artifact list
    and write the manifest.
    """

    def __init__(
        self,
        config: CaptureConfig,
        scenario_id: str,
        *,
        browser: BrowserCapture | None = None,
    ) -> None:
        self._config = config
        self._scenario_id = scenario_id
        self._browser = browser or BrowserCapture(config)
        self._artifacts: list[EvidenceArtifact] = []
        self._scenario_dir = config.output_dir / scenario_id
        self._scenario_dir.mkdir(parents=True, exist_ok=True)
        self._finalized = False

    @property
    def scenario_dir(self) -> Path:
        return self._scenario_dir

    @property
    def scenario_id(self) -> str:
        return self._scenario_id

    def record_api_response(
        self,
        *,
        step: int,
        method: str,
        path: str,
        status: int,
        body: dict[str, Any] | None = None,
        request_id: str = '',
        description: str = '',
    ) -> EvidenceArtifact:
        """Record an API response as evidence.

        Writes the response body to a JSON file in the scenario
        directory.
        """
        filename = f'step{step:02d}_api_{method.lower()}_{_safe_path(path)}.json'
        file_path = self._scenario_dir / filename

        payload: dict[str, Any] = {
            'method': method,
            'path': path,
            'status': status,
            'request_id': request_id,
        }
        if body is not None:
            payload['body'] = body

        file_path.write_text(json.dumps(payload, indent=2), encoding='utf-8')

        desc = description or f'{method} {path} → {status}'
        artifact = EvidenceArtifact(
            artifact_type=ArtifactType.API_RESPONSE,
            step_number=step,
            description=desc,
            file_path=str(file_path.relative_to(self._config.output_dir)),
            timestamp=_now_iso(),
            scenario_id=self._scenario_id,
            metadata={'method': method, 'path': path, 'status': status,
                      'request_id': request_id},
        )
        self._artifacts.append(artifact)
        return artifact

    async def capture_screenshot(
        self,
        *,
        step: int,
        description: str,
        url: str,
        full_page: bool | None = None,
    ) -> EvidenceArtifact:
        """Capture a browser screenshot and register as evidence.

        Raises:
            RuntimeError: If screenshot capture fails.
        """
        fmt = self._config.screenshot_format
        filename = f'step{step:02d}_screenshot.{fmt}'
        output_path = self._scenario_dir / filename

        await self._browser.screenshot(
            url, output_path, full_page=full_page,
        )

        artifact = EvidenceArtifact(
            artifact_type=ArtifactType.SCREENSHOT,
            step_number=step,
            description=description,
            file_path=str(output_path.relative_to(self._config.output_dir)),
            timestamp=_now_iso(),
            scenario_id=self._scenario_id,
            metadata={'url': url, 'format': fmt},
        )
        self._artifacts.append(artifact)
        return artifact

    def record_log_entry(
        self,
        *,
        step: int,
        description: str,
        log_text: str,
    ) -> EvidenceArtifact:
        """Record a log entry as evidence."""
        filename = f'step{step:02d}_log.txt'
        file_path = self._scenario_dir / filename
        file_path.write_text(log_text, encoding='utf-8')

        artifact = EvidenceArtifact(
            artifact_type=ArtifactType.LOG_ENTRY,
            step_number=step,
            description=description,
            file_path=str(file_path.relative_to(self._config.output_dir)),
            timestamp=_now_iso(),
            scenario_id=self._scenario_id,
        )
        self._artifacts.append(artifact)
        return artifact

    def finalize(self) -> tuple[EvidenceArtifact, ...]:
        """Return all collected artifacts and write the manifest.

        The manifest is a JSON file listing all artifacts for the
        scenario, enabling downstream tooling (K4a) to discover and
        attach artifacts.
        """
        if self._finalized:
            return tuple(self._artifacts)

        manifest_path = self._scenario_dir / 'manifest.json'
        manifest = {
            'scenario_id': self._scenario_id,
            'artifact_count': len(self._artifacts),
            'finalized_at': _now_iso(),
            'artifacts': [a.to_dict() for a in self._artifacts],
        }
        manifest_path.write_text(
            json.dumps(manifest, indent=2), encoding='utf-8',
        )
        self._finalized = True
        return tuple(self._artifacts)


# ── Helpers ────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_path(path: str) -> str:
    """Convert an API path to a safe filename component."""
    return path.strip('/').replace('/', '_').replace('{', '').replace('}', '')


def _escape_js(s: str) -> str:
    """Escape a string for safe insertion into a JS single-quoted literal."""
    return (s.replace('\\', '\\\\')
             .replace("'", "\\'")
             .replace('\n', '\\n')
             .replace('\r', '\\r'))
