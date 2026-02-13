#!/usr/bin/env python3
"""
Validate that new beads issues include the required Definition-of-Done (DoD)
sections in their *description*.

Policy (DoD-v1):
  - For any issue created on/after DOD_REQUIRED_SINCE (UTC),
    the description must include these markdown headings:
      - "## Acceptance Criteria"
      - "## Evidence"
      - "## Verification"
      - "## Rollback"

  - For CLOSED issues (created on/after the cutoff), sections must be non-empty.
  - For CLOSED bug issues, Evidence must mention repro steps ("repro").

We intentionally do NOT lint older historical issues to avoid retroactive churn.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


DOD_REQUIRED_SINCE = "2026-02-13T22:00:00Z"

_REQUIRED_SECTIONS: tuple[tuple[str, str], ...] = (
    ("acceptance", "## Acceptance Criteria"),
    ("evidence", "## Evidence"),
    ("verification", "## Verification"),
    ("rollback", "## Rollback"),
)


_HEADING_PATTERNS: dict[str, re.Pattern[str]] = {
    key: re.compile(rf"^##\s+{re.escape(title.removeprefix('## ').strip())}\s*$", re.MULTILINE)
    for key, title in _REQUIRED_SECTIONS
}


@dataclass(frozen=True, slots=True)
class LintError:
    issue_id: str
    title: str
    problems: tuple[str, ...]


def _parse_utc(ts: str) -> datetime:
    """Parse ISO-8601 timestamp string (with optional trailing Z) to aware datetime."""
    raw = (ts or "").strip()
    if not raw:
        raise ValueError("missing timestamp")
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _load_latest_issues(jsonl_path: Path) -> dict[str, dict]:
    """Load JSONL and return a map of issue_id -> latest record."""
    latest: dict[str, dict] = {}
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            issue_id = rec.get("id")
            if not issue_id:
                continue
            latest[issue_id] = rec
    return latest


def _extract_sections(desc: str) -> tuple[dict[str, str], list[str]]:
    """Extract required sections from markdown description.

    Returns:
      (sections, problems)
      - sections: key -> raw section body (stripped), for sections that exist
      - problems: human-readable lint problems
    """
    problems: list[str] = []
    if not desc:
        return {}, ["missing description"]

    matches: dict[str, re.Match[str]] = {}
    for key, _title in _REQUIRED_SECTIONS:
        m = _HEADING_PATTERNS[key].search(desc)
        if not m:
            problems.append(f"missing section heading: {_REQUIRED_SECTIONS_DICT()[key]}")
        else:
            matches[key] = m

    if problems:
        return {}, problems

    # Enforce section order (as listed in _REQUIRED_SECTIONS).
    starts = [matches[key].start() for key, _ in _REQUIRED_SECTIONS]
    if starts != sorted(starts):
        problems.append("section headings are out of order (expected: Acceptance -> Evidence -> Verification -> Rollback)")

    # Extract section bodies (from end of heading line to next required heading).
    sections: dict[str, str] = {}
    ordered_keys = [key for key, _ in _REQUIRED_SECTIONS]
    for i, key in enumerate(ordered_keys):
        start = matches[key].end()
        end = len(desc)
        if i + 1 < len(ordered_keys):
            nxt = ordered_keys[i + 1]
            end = matches[nxt].start()
        body = desc[start:end].strip()
        sections[key] = body

    return sections, problems


def _REQUIRED_SECTIONS_DICT() -> dict[str, str]:
    return {k: title for k, title in _REQUIRED_SECTIONS}


def _lint_issue(issue: dict, cutoff: datetime) -> LintError | None:
    issue_id = str(issue.get("id", "")).strip()
    title = str(issue.get("title", "")).strip()
    status = str(issue.get("status", "")).strip().lower()
    issue_type = str(issue.get("issue_type", "")).strip().lower()

    # Ignore tombstones (deleted issues).
    if status == "tombstone":
        return None

    created_at_raw = str(issue.get("created_at", "")).strip()
    if not created_at_raw:
        return LintError(
            issue_id=issue_id or "<missing id>",
            title=title or "<missing title>",
            problems=("missing created_at",),
        )

    created_at = _parse_utc(created_at_raw)
    if created_at < cutoff:
        return None  # Pre-policy issue.

    desc = issue.get("description") or ""
    sections, problems = _extract_sections(str(desc))
    if problems:
        return LintError(issue_id=issue_id, title=title, problems=tuple(problems))

    # For non-closed issues, presence of headings is enough (template can be filled later).
    if status != "closed":
        return None

    # Closed issues must have non-empty sections.
    closed_problems: list[str] = []
    for key, title_heading in _REQUIRED_SECTIONS:
        body = sections.get(key, "").strip()
        if not body:
            closed_problems.append(f"{title_heading} must not be empty for closed issues")

    # Evidence: require at least one commit-ish hash token.
    evidence = sections.get("evidence", "")
    if evidence and not re.search(r"\b[0-9a-f]{7,40}\b", evidence, flags=re.IGNORECASE):
        closed_problems.append("## Evidence must include at least one git sha (7+ hex chars)")

    # Verification: require at least one fenced code block.
    verification = sections.get("verification", "")
    if verification and "```" not in verification:
        closed_problems.append("## Verification must include a fenced code block with the commands that were run")

    # Bug issues: require repro mention in Evidence.
    if issue_type == "bug":
        if evidence and not re.search(r"\brepro\b", evidence, flags=re.IGNORECASE):
            closed_problems.append("bug issues: ## Evidence must include repro steps (include the word 'repro')")

    if closed_problems:
        return LintError(issue_id=issue_id, title=title, problems=tuple(closed_problems))

    return None


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    jsonl_path = repo_root / ".beads" / "issues.jsonl"

    if not jsonl_path.exists():
        print(f"ERROR: missing {jsonl_path}", file=sys.stderr)
        return 2

    cutoff = _parse_utc(DOD_REQUIRED_SINCE)
    latest = _load_latest_issues(jsonl_path)

    errors: list[LintError] = []
    for issue in latest.values():
        err = _lint_issue(issue, cutoff=cutoff)
        if err is not None:
            errors.append(err)

    errors.sort(key=lambda e: e.issue_id)

    if errors:
        print("Beads DoD lint FAILED.", file=sys.stderr)
        print(f"Policy: issues created on/after {DOD_REQUIRED_SINCE} require DoD sections.", file=sys.stderr)
        for e in errors:
            print(f"- {e.issue_id}: {e.title}", file=sys.stderr)
            for p in e.problems:
                print(f"  - {p}", file=sys.stderr)
        return 1

    print(f"Beads DoD lint OK (cutoff={DOD_REQUIRED_SINCE}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

