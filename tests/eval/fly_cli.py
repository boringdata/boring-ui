"""Shared Fly CLI discovery for the eval harness."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def resolve_fly_cli(explicit: str | None = None) -> str | None:
    """Resolve the Fly CLI path from env, PATH, or the standard home install."""
    for candidate in fly_cli_candidates(explicit):
        resolved = _resolve_candidate(candidate)
        if resolved:
            return resolved
    return None


def fly_cli_candidates(explicit: str | None = None) -> list[str]:
    candidates: list[str] = []
    if explicit:
        candidates.append(explicit)
    elif env_candidate := os.environ.get("FLYCTL_BIN", "").strip():
        candidates.append(env_candidate)

    candidates.extend(["fly", "flyctl"])
    home = Path.home()
    candidates.extend(
        [
            str(home / ".fly" / "bin" / "fly"),
            str(home / ".fly" / "bin" / "flyctl"),
        ]
    )
    return candidates


def _resolve_candidate(candidate: str) -> str | None:
    normalized = _normalize_candidate(candidate)
    if not normalized:
        return None

    if os.path.sep in normalized:
        path = Path(normalized)
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
        return None

    return shutil.which(normalized)


def _normalize_candidate(candidate: str) -> str:
    candidate = candidate.strip()
    if not candidate:
        return ""
    if candidate.startswith("~/"):
        return str(Path.home() / candidate[2:])
    if candidate.startswith("$HOME/"):
        return str(Path.home() / candidate[len("$HOME/") :])
    return candidate
