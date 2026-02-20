from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

FEATURE_FILES = [
    'src/front/App.jsx',
    'src/front/components/FileTree.jsx',
    'src/front/components/GitChangesView.jsx',
    'src/front/components/Terminal.jsx',
    'src/front/components/chat/ClaudeStreamChat.jsx',
    'src/front/hooks/useCapabilities.js',
    'src/front/hooks/useWorkspacePlugins.js',
    'src/front/panels/EditorPanel.jsx',
    'src/front/providers/pi/backendAdapter.jsx',
]

PROHIBITED_PATTERNS = [
    re.compile(r"['\"`]/(?:api|ws)"),
    re.compile(r"\$\{apiBase\}/"),
    re.compile(r"\$\{baseUrl\}/api"),
]


def _find_violations(content: str) -> list[str]:
    violations: list[str] = []
    for line_number, line in enumerate(content.splitlines(), start=1):
        for pattern in PROHIBITED_PATTERNS:
            if pattern.search(line):
                violations.append(f"line {line_number}: {line.strip()}")
                break
    return violations


def test_feature_modules_do_not_hardcode_api_or_ws_route_literals() -> None:
    all_violations: list[str] = []

    for rel_path in FEATURE_FILES:
        file_path = REPO_ROOT / rel_path
        content = file_path.read_text(encoding='utf-8')
        violations = _find_violations(content)
        all_violations.extend([f"{rel_path}: {item}" for item in violations])

    assert not all_violations, 'Hardcoded route construction remains:\n' + '\n'.join(all_violations)
