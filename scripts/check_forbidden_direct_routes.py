#!/usr/bin/env python3
"""Static guard for forbidden direct route literals in frontend feature code."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

TARGET_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx"}
EXCLUDED_DIR_NAMES = {"__tests__"}
EXCLUDED_FILE_SUFFIXES = (".test.js", ".test.jsx", ".test.ts", ".test.tsx")
EXCLUDED_PATH_PREFIXES = (
    Path("src/front/providers/companion/upstream"),
)
ALLOWLIST_PATHS = {
    Path("src/front/utils/apiBase.js"),
    Path("src/front/utils/controlPlane.js"),
    Path("src/front/utils/routes.js"),
    Path("src/front/utils/transport.js"),
    Path("src/front/providers/pi/routes.js"),
}


@dataclass(frozen=True)
class Rule:
    code: str
    pattern: re.Pattern[str]
    message: str


@dataclass(frozen=True)
class Violation:
    rule: str
    path: str
    line: int
    snippet: str
    message: str


RULES: tuple[Rule, ...] = (
    Rule(
        code="legacy-compat-route",
        pattern=re.compile(
            r"""['"`]/(?:api/(?:tree|file|search|git|attachments)(?:/|$|[?#]|['"`])|ws/(?:stream|pty)(?:/|$|[?#]|['"`]))"""
        ),
        message="Legacy /api/* or /ws/* compat literals are forbidden in feature modules.",
    ),
    Rule(
        code="workspace-proxy-literal",
        pattern=re.compile(r"""['"`]/w/"""),
        message="Direct /w/{workspace_id}/... literals are forbidden in feature modules; use shared route helpers.",
    ),
    Rule(
        code="direct-internal-service-route",
        pattern=re.compile(
            r"""['"`]/(?:api/v1/(?:files|git|pty|agent(?:/(?:normal|companion|pi))?)(?:/|$|[?#]|['"`])|ws/(?:pty|agent/(?:normal|companion|pi))(?:/|$|[?#]|['"`]))"""
        ),
        message="Direct internal service families are forbidden; route via control-plane boundaries.",
    ),
    Rule(
        code="template-direct-route-construction",
        pattern=re.compile(r"""\$\{(?:apiBase|baseUrl|origin)\}/(?:api|ws)"""),
        message="Template-based direct /api or /ws route construction is forbidden in feature modules.",
    ),
)


def _is_candidate(rel_path: Path) -> bool:
    if rel_path.suffix not in TARGET_EXTENSIONS:
        return False
    if rel_path.name.endswith(EXCLUDED_FILE_SUFFIXES):
        return False
    if any(part in EXCLUDED_DIR_NAMES for part in rel_path.parts):
        return False
    if rel_path in ALLOWLIST_PATHS:
        return False
    if any(rel_path.is_relative_to(prefix) for prefix in EXCLUDED_PATH_PREFIXES):
        return False
    return True


def _strip_comments(line: str, in_block_comment: bool) -> tuple[str, bool]:
    result: list[str] = []
    index = 0
    string_delimiter: str | None = None
    escaped = False

    while index < len(line):
        if in_block_comment:
            end = line.find("*/", index)
            if end == -1:
                return "".join(result).strip(), True
            index = end + 2
            in_block_comment = False
            continue

        char = line[index]

        if string_delimiter is not None:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == string_delimiter:
                string_delimiter = None
            index += 1
            continue

        # Keep parsing focused on standard quoted strings where comment-token
        # ambiguity is common. Template literals are still scanned for route
        # patterns, but comment stripping inside `${...}` expressions is not
        # modeled here.
        if char in {"'", '"'}:
            string_delimiter = char
            result.append(char)
            index += 1
            continue

        if line.startswith("//", index):
            break

        if line.startswith("/*", index):
            in_block_comment = True
            index += 2
            continue

        result.append(char)
        index += 1

    return "".join(result).strip(), in_block_comment


def _iter_targets(root: Path, scan_root: Path) -> Iterable[Path]:
    base_dir = root / scan_root
    if not base_dir.exists():
        return []
    files = sorted(path for path in base_dir.rglob("*") if path.is_file())
    return [path for path in files if _is_candidate(path.relative_to(root))]


def _scan_file(root: Path, file_path: Path) -> list[Violation]:
    rel_path = file_path.relative_to(root)
    text = file_path.read_text(encoding="utf-8")
    violations: list[Violation] = []
    in_block_comment = False
    for line_number, line in enumerate(text.splitlines(), start=1):
        candidate_line, in_block_comment = _strip_comments(
            line=line,
            in_block_comment=in_block_comment,
        )
        if not candidate_line:
            continue
        for rule in RULES:
            if rule.pattern.search(candidate_line):
                violations.append(
                    Violation(
                        rule=rule.code,
                        path=str(rel_path),
                        line=line_number,
                        snippet=line.strip(),
                        message=rule.message,
                    )
                )
    return violations


def scan_repo(root: Path, scan_root: Path) -> list[Violation]:
    violations: list[Violation] = []
    for file_path in _iter_targets(root, scan_root):
        violations.extend(_scan_file(root, file_path))
    return violations


def _format_text(violations: list[Violation]) -> str:
    if not violations:
        return "No forbidden direct route patterns found."
    lines = ["Forbidden direct-route patterns detected:"]
    for violation in violations:
        lines.append(
            f"- [{violation.rule}] {violation.path}:{violation.line} :: {violation.snippet}"
        )
        lines.append(f"  hint: {violation.message}")
    return "\n".join(lines)


def _format_json(violations: list[Violation]) -> str:
    payload = {
        "violation_count": len(violations),
        "violations": [asdict(v) for v in violations],
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check frontend feature code for forbidden direct route literals/construction."
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Repository root path (default: current directory).",
    )
    parser.add_argument(
        "--scan-root",
        default="src/front",
        help="Relative path to scan from repository root (default: src/front).",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format (default: text).",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    scan_root = Path(args.scan_root)

    violations = scan_repo(root=root, scan_root=scan_root)
    if args.format == "json":
        print(_format_json(violations))
    else:
        print(_format_text(violations))
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
