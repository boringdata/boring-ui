"""Migration discovery, ordering, and idempotency validation.

Provides utilities for:
- Discovering migration files by numeric prefix ordering.
- Validating that SQL migrations follow idempotency contracts
  (IF NOT EXISTS, DROP IF EXISTS, CREATE OR REPLACE patterns).
- Documenting backfill strategy for column additions to existing tables.

Migration Execution:
    Actual execution is via ``supabase db push`` (see design doc section 21.1).
    This module provides the validation/linting layer, not execution.

Idempotency Contract:
    Every migration file MUST satisfy:
    1. All CREATE TABLE use IF NOT EXISTS.
    2. All CREATE INDEX use IF NOT EXISTS.
    3. All CREATE SCHEMA use IF NOT EXISTS.
    4. All CREATE FUNCTION use CREATE OR REPLACE.
    5. All CREATE TRIGGER are preceded by DROP TRIGGER IF EXISTS.
    6. All CREATE POLICY are preceded by DROP POLICY IF EXISTS.
    7. ALTER TABLE ADD COLUMN uses IF NOT EXISTS.
    8. No bare DROP TABLE/DROP INDEX (use IF EXISTS variants only).

Backfill Strategy (V0):
    All new columns added to existing tables MUST:
    1. Use DEFAULT values for non-null columns (safe for existing rows).
    2. Use nullable columns when no sensible default exists.
    3. Avoid NOT NULL without DEFAULT on columns added via ALTER TABLE.
    4. Ensure CHECK constraints accept the default value.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

# Migration file discovery pattern: NNN_description.sql
_MIGRATION_RE = re.compile(r'^(\d{3})_.*\.sql$')

# Directory containing migration SQL files.
MIGRATIONS_DIR = Path(__file__).parent


@dataclass(frozen=True, slots=True)
class MigrationFile:
    """A discovered migration file with its sequence number."""

    sequence: int
    filename: str
    path: Path

    @property
    def is_review(self) -> bool:
        """True if file is a review/specification, not executable migration."""
        return 'review' in self.filename.lower()


@dataclass
class ValidationResult:
    """Result of idempotency validation for a single migration file."""

    path: Path
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


# ------------------------------------------------------------------
# Idempotency pattern checks
# ------------------------------------------------------------------
# Each check returns a list of (line_number, message) issues.

_UNSAFE_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    # CREATE TABLE without IF NOT EXISTS
    (
        re.compile(
            r'^\s*create\s+table\s+(?!.*if\s+not\s+exists)',
            re.IGNORECASE,
        ),
        'CREATE TABLE without IF NOT EXISTS',
        'error',
    ),
    # CREATE INDEX without IF NOT EXISTS
    (
        re.compile(
            r'^\s*create\s+(unique\s+)?index\s+(?!.*if\s+not\s+exists)',
            re.IGNORECASE,
        ),
        'CREATE INDEX without IF NOT EXISTS',
        'error',
    ),
    # CREATE SCHEMA without IF NOT EXISTS
    (
        re.compile(
            r'^\s*create\s+schema\s+(?!.*if\s+not\s+exists)',
            re.IGNORECASE,
        ),
        'CREATE SCHEMA without IF NOT EXISTS',
        'error',
    ),
    # CREATE FUNCTION without OR REPLACE
    (
        re.compile(
            r'^\s*create\s+function\s+',
            re.IGNORECASE,
        ),
        'CREATE FUNCTION without OR REPLACE',
        'error',
    ),
    # Bare DROP TABLE (without IF EXISTS)
    (
        re.compile(
            r'^\s*drop\s+table\s+(?!.*if\s+exists)',
            re.IGNORECASE,
        ),
        'DROP TABLE without IF EXISTS',
        'error',
    ),
    # Bare DROP INDEX (without IF EXISTS)
    (
        re.compile(
            r'^\s*drop\s+index\s+(?!.*if\s+exists)',
            re.IGNORECASE,
        ),
        'DROP INDEX without IF EXISTS',
        'error',
    ),
    # ALTER TABLE ADD COLUMN without IF NOT EXISTS
    (
        re.compile(
            r'^\s*(?:add\s+column)\s+(?!.*if\s+not\s+exists)',
            re.IGNORECASE,
        ),
        'ADD COLUMN without IF NOT EXISTS',
        'warning',
    ),
]

# CREATE OR REPLACE is the safe form; bare CREATE FUNCTION is not.
_CREATE_OR_REPLACE_FUNCTION = re.compile(
    r'^\s*create\s+or\s+replace\s+function\s+', re.IGNORECASE
)

# CREATE POLICY must be preceded by DROP POLICY IF EXISTS.
_CREATE_POLICY_RE = re.compile(
    r'^\s*create\s+policy\s+(\S+)', re.IGNORECASE
)
_DROP_POLICY_RE = re.compile(
    r'^\s*drop\s+policy\s+if\s+exists\s+(\S+)', re.IGNORECASE
)

# CREATE TRIGGER must be preceded by DROP TRIGGER IF EXISTS.
_CREATE_TRIGGER_RE = re.compile(
    r'^\s*create\s+(?:or\s+replace\s+)?trigger\s+(\S+)', re.IGNORECASE
)
_DROP_TRIGGER_RE = re.compile(
    r'^\s*drop\s+trigger\s+if\s+exists\s+(\S+)', re.IGNORECASE
)


def discover_migrations(
    directory: Path | None = None,
) -> list[MigrationFile]:
    """Discover and return migration files sorted by sequence number.

    Args:
        directory: Path to search. Defaults to this package's directory.

    Returns:
        Sorted list of MigrationFile entries.

    Raises:
        ValueError: If duplicate sequence numbers are found.
    """
    d = directory or MIGRATIONS_DIR
    results: list[MigrationFile] = []
    seen_seqs: dict[int, str] = {}

    for p in sorted(d.iterdir()):
        if not p.is_file():
            continue
        m = _MIGRATION_RE.match(p.name)
        if not m:
            continue
        seq = int(m.group(1))
        if seq in seen_seqs:
            raise ValueError(
                f'Duplicate migration sequence {seq:03d}: '
                f'{seen_seqs[seq]} and {p.name}'
            )
        seen_seqs[seq] = p.name
        results.append(MigrationFile(sequence=seq, filename=p.name, path=p))

    results.sort(key=lambda mf: mf.sequence)
    return results


def validate_idempotency(sql_path: Path) -> ValidationResult:
    """Check a migration SQL file for idempotency contract violations.

    Args:
        sql_path: Path to the .sql file.

    Returns:
        ValidationResult with any errors or warnings found.
    """
    result = ValidationResult(path=sql_path)
    text = sql_path.read_text()
    lines = text.splitlines()

    # Track DROP POLICY/TRIGGER names seen (for pairing with CREATE).
    dropped_policies: set[str] = set()
    dropped_triggers: set[str] = set()

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()

        # Skip empty lines and comments.
        if not stripped or stripped.startswith('--'):
            continue

        # Check CREATE OR REPLACE FUNCTION (safe) vs CREATE FUNCTION.
        if re.match(r'^\s*create\s+function\s+', stripped, re.IGNORECASE):
            if not _CREATE_OR_REPLACE_FUNCTION.match(stripped):
                result.errors.append(
                    f'Line {i}: CREATE FUNCTION without OR REPLACE'
                )
            continue

        # Track DROP POLICY IF EXISTS.
        dp = _DROP_POLICY_RE.match(stripped)
        if dp:
            dropped_policies.add(dp.group(1).lower())
            continue

        # Check CREATE POLICY has preceding DROP.
        cp = _CREATE_POLICY_RE.match(stripped)
        if cp:
            name = cp.group(1).lower()
            if name not in dropped_policies:
                result.errors.append(
                    f'Line {i}: CREATE POLICY {cp.group(1)} without '
                    f'preceding DROP POLICY IF EXISTS'
                )
            continue

        # Track DROP TRIGGER IF EXISTS.
        dt = _DROP_TRIGGER_RE.match(stripped)
        if dt:
            dropped_triggers.add(dt.group(1).lower())
            continue

        # Check CREATE TRIGGER has preceding DROP.
        ct = _CREATE_TRIGGER_RE.match(stripped)
        if ct:
            name = ct.group(1).lower()
            if name not in dropped_triggers:
                result.errors.append(
                    f'Line {i}: CREATE TRIGGER {ct.group(1)} without '
                    f'preceding DROP TRIGGER IF EXISTS'
                )
            continue

        # Run pattern-based checks.
        for pattern, msg, severity in _UNSAFE_PATTERNS:
            if pattern.search(stripped):
                # Skip false positives for CREATE OR REPLACE FUNCTION
                # (already handled above).
                if 'FUNCTION' in msg:
                    continue
                if severity == 'error':
                    result.errors.append(f'Line {i}: {msg}')
                else:
                    result.warnings.append(f'Line {i}: {msg}')

    return result


def validate_all(
    directory: Path | None = None,
    skip_reviews: bool = True,
) -> dict[str, ValidationResult]:
    """Validate all discovered migrations for idempotency.

    Args:
        directory: Migration directory. Defaults to package directory.
        skip_reviews: If True, skip review/specification files.

    Returns:
        Dict mapping filename to ValidationResult.
    """
    migrations = discover_migrations(directory)
    results: dict[str, ValidationResult] = {}

    for mf in migrations:
        if skip_reviews and mf.is_review:
            continue
        results[mf.filename] = validate_idempotency(mf.path)

    return results


def check_sequence_gaps(
    migrations: Sequence[MigrationFile],
) -> list[str]:
    """Check for gaps in migration sequence numbers.

    Returns list of warning messages for any gaps found.
    """
    warnings: list[str] = []
    for i in range(1, len(migrations)):
        prev = migrations[i - 1].sequence
        curr = migrations[i].sequence
        if curr != prev + 1:
            warnings.append(
                f'Gap in sequence: {prev:03d} -> {curr:03d} '
                f'(expected {prev + 1:03d})'
            )
    return warnings
