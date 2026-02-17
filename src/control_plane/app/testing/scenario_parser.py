"""Parse test scenario markdown files into structured specs.

Bead: bd-223o.16.3 (K3)

Reads ``test-scenarios/sNNN_*.md`` files and extracts:
  - Scenario ID and title from H1 header
  - Preconditions as bullet list
  - Steps as numbered list
  - API expected signals from markdown table
  - Evidence artifacts as bullet list
  - Failure modes from markdown table

The parser is intentionally lenient — missing sections produce empty lists
rather than errors, since not all scenarios define every section.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


_H1_RE = re.compile(r'^#\s+S-(\d+):\s+(.+)$', re.MULTILINE)
_STEP_RE = re.compile(r'^\d+\.\s+(.+)$', re.MULTILINE)
_BULLET_RE = re.compile(r'^-\s+(.+)$', re.MULTILINE)

# Markdown table row: | col1 | col2 | col3 | col4 |
_TABLE_ROW_RE = re.compile(
    r'^\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|$',
    re.MULTILINE,
)

# API signal: extract method + path from backtick-wrapped endpoint
_ENDPOINT_RE = re.compile(r'`(GET|POST|PUT|PATCH|DELETE)\s+([^`]+)`')


@dataclass(frozen=True, slots=True)
class ApiSignal:
    """Expected API response for a scenario step."""

    step: int
    method: str
    path: str
    status: int
    key_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FailureMode:
    """Expected behavior when a specific failure occurs."""

    failure: str
    expected_behavior: str


@dataclass(frozen=True, slots=True)
class ScenarioSpec:
    """Parsed scenario specification from a markdown file."""

    scenario_id: str
    title: str
    source_path: str
    preconditions: tuple[str, ...]
    steps: tuple[str, ...]
    api_signals: tuple[ApiSignal, ...]
    evidence_artifacts: tuple[str, ...]
    failure_modes: tuple[FailureMode, ...]
    critical_path: bool = True

    @property
    def step_count(self) -> int:
        return len(self.steps)

    @property
    def api_step_numbers(self) -> tuple[int, ...]:
        """Step numbers that have API signals defined."""
        return tuple(s.step for s in self.api_signals)


def parse_scenario(text: str, source_path: str = '<string>') -> ScenarioSpec:
    """Parse scenario markdown text into a ScenarioSpec.

    Args:
        text: Raw markdown content.
        source_path: File path for error reporting.

    Returns:
        Parsed ScenarioSpec.

    Raises:
        ValueError: If H1 header with scenario ID is missing.
    """
    # Extract scenario ID and title from H1.
    h1_match = _H1_RE.search(text)
    if not h1_match:
        raise ValueError(
            f'No scenario header found in {source_path}. '
            f'Expected: # S-NNN: Title'
        )

    scenario_id = f'S-{h1_match.group(1).zfill(3)}'
    title = h1_match.group(2).strip()

    # Split into sections by H2 headers.
    sections = _split_sections(text)

    preconditions = _extract_bullets(sections.get('preconditions', ''))
    steps = _extract_steps(sections.get('steps', ''))
    api_signals = _extract_api_signals(
        sections.get('expected signals', '')
    )
    evidence = _extract_bullets(sections.get('evidence artifacts', ''))
    failure_modes = _extract_failure_modes(
        sections.get('failure modes', '')
    )

    critical = 'critical_path: false' not in text.lower()

    return ScenarioSpec(
        scenario_id=scenario_id,
        title=title,
        source_path=source_path,
        preconditions=tuple(preconditions),
        steps=tuple(steps),
        api_signals=tuple(api_signals),
        evidence_artifacts=tuple(evidence),
        failure_modes=tuple(failure_modes),
        critical_path=critical,
    )


def parse_scenario_file(path: Path) -> ScenarioSpec:
    """Parse a scenario markdown file.

    Args:
        path: Path to the scenario ``.md`` file.

    Returns:
        Parsed ScenarioSpec with source_path set.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file cannot be parsed.
    """
    text = path.read_text(encoding='utf-8')
    return parse_scenario(text, source_path=str(path))


def scan_scenario_dir(
    directory: Path,
    *,
    pattern: str = 's[0-9][0-9][0-9]_*.md',
) -> list[ScenarioSpec]:
    """Scan a directory for scenario files and parse them all.

    Files are sorted by name (i.e., by scenario ID).

    Args:
        directory: Path to the scenarios directory.
        pattern: Glob pattern for scenario files.

    Returns:
        List of parsed ScenarioSpec objects, sorted by ID.
    """
    specs: list[ScenarioSpec] = []
    for path in sorted(directory.glob(pattern)):
        specs.append(parse_scenario_file(path))
    return specs


# ── Private helpers ────────────────────────────────────────────────


def _split_sections(text: str) -> dict[str, str]:
    """Split markdown by H2 headers into a section dict."""
    sections: dict[str, str] = {}
    current_key: str | None = None
    current_lines: list[str] = []

    for line in text.split('\n'):
        if line.startswith('## '):
            if current_key is not None:
                sections[current_key] = '\n'.join(current_lines)
            current_key = line[3:].strip().lower()
            current_lines = []
        elif current_key is not None:
            current_lines.append(line)

    if current_key is not None:
        sections[current_key] = '\n'.join(current_lines)

    return sections


def _extract_steps(text: str) -> list[str]:
    """Extract numbered steps from markdown."""
    return [m.group(1).strip() for m in _STEP_RE.finditer(text)]


def _extract_bullets(text: str) -> list[str]:
    """Extract bullet-list items from markdown."""
    return [m.group(1).strip() for m in _BULLET_RE.finditer(text)]


def _extract_api_signals(text: str) -> list[ApiSignal]:
    """Extract API signal table rows."""
    signals: list[ApiSignal] = []

    for match in _TABLE_ROW_RE.finditer(text):
        step_str = match.group(1).strip()
        endpoint_str = match.group(2).strip()
        status_str = match.group(3).strip()
        fields_str = match.group(4).strip()

        # Skip header and separator rows.
        if step_str.lower() == 'step' or step_str.startswith('-'):
            continue

        try:
            step_num = int(step_str)
        except ValueError:
            continue

        try:
            status = int(status_str)
        except ValueError:
            continue

        ep_match = _ENDPOINT_RE.search(endpoint_str)
        if not ep_match:
            continue

        method = ep_match.group(1)
        path = ep_match.group(2).strip()

        key_fields = tuple(
            f.strip().strip('`')
            for f in fields_str.split(',')
            if f.strip()
        )

        signals.append(ApiSignal(
            step=step_num,
            method=method,
            path=path,
            status=status,
            key_fields=key_fields,
        ))

    return signals


def _extract_failure_modes(text: str) -> list[FailureMode]:
    """Extract failure mode table rows."""
    modes: list[FailureMode] = []

    for match in _TABLE_ROW_RE.finditer(text):
        failure = match.group(1).strip()
        behavior = match.group(2).strip()

        # _TABLE_ROW_RE expects 4 columns but failure table has 2.
        # Re-parse with 2-column regex.
        pass

    # Use a 2-column regex for failure modes.
    row_re = re.compile(
        r'^\|\s*(.+?)\s*\|\s*(.+?)\s*\|$',
        re.MULTILINE,
    )
    for match in row_re.finditer(text):
        failure = match.group(1).strip()
        behavior = match.group(2).strip()

        if failure.lower() == 'failure' or failure.startswith('-'):
            continue

        modes.append(FailureMode(failure=failure, expected_behavior=behavior))

    return modes
