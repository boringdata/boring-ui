"""Tests for migration rerun and rollback smoke checks.

Bead: bd-223o.6.3.1 (A3a)

Validates that migration SQL files satisfy rerun/rollback safety:
  - Rerun: applying a migration twice in a row produces no errors
    (enforced by IF NOT EXISTS / OR REPLACE patterns).
  - Rollback: migrations don't use destructive DDL that would prevent
    clean rollback (bare DROP without IF EXISTS).
  - CI gate: validate_all() returns clean for the full migration set.
  - Ordering: migrations maintain a strict, gapless sequence.
  - Content: no empty migration files (which would silently skip).
  - Cross-file: no conflicting object names across migrations.
"""

from __future__ import annotations

import re
import textwrap
from pathlib import Path

import pytest

from control_plane.migrations import (
    MIGRATIONS_DIR,
    MigrationFile,
    check_sequence_gaps,
    discover_migrations,
    validate_all,
    validate_idempotency,
)


# ── Helpers ───────────────────────────────────────────────────────────


def _write_sql(directory: Path, name: str, content: str) -> Path:
    p = directory / name
    p.write_text(textwrap.dedent(content))
    return p


def _extract_object_names(sql: str, pattern: re.Pattern[str]) -> list[str]:
    """Extract object names matching a regex pattern from SQL text."""
    return [m.group(1).lower() for m in pattern.finditer(sql)]


# =====================================================================
# 1. Rerun safety — simulated double-apply
# =====================================================================


class TestRerunSafety:
    """Validate that migrations can be safely re-applied (idempotent).

    In production, `supabase db push` applies migrations in order.
    If a migration is re-applied (e.g., after rollback+retry), it must
    not fail. This is guaranteed by our idempotency contract.
    """

    def test_all_real_migrations_are_rerun_safe(self):
        """Every non-review migration must pass idempotency validation.

        This is the core CI gate: if this test fails, the migration
        cannot be safely re-applied and must be fixed before merge.
        """
        results = validate_all(MIGRATIONS_DIR, skip_reviews=True)
        assert len(results) > 0, 'No migrations found to validate'
        for filename, result in results.items():
            assert result.ok, (
                f'{filename} is NOT rerun-safe:\n'
                + '\n'.join(f'  - {e}' for e in result.errors)
            )

    def test_each_migration_individually_rerun_safe(self):
        """Validate each migration file individually (not just validate_all).

        This ensures no masking of errors between files.
        """
        migrations = discover_migrations(MIGRATIONS_DIR)
        for mf in migrations:
            if mf.is_review:
                continue
            result = validate_idempotency(mf.path)
            assert result.ok, (
                f'{mf.filename} failed rerun safety:\n'
                + '\n'.join(f'  - {e}' for e in result.errors)
            )


# =====================================================================
# 2. Rollback safety — no destructive bare DDL
# =====================================================================

# Patterns that would make rollback dangerous
_BARE_DROP_PATTERNS = [
    re.compile(r'^\s*drop\s+table\s+(?!.*if\s+exists)', re.IGNORECASE | re.MULTILINE),
    re.compile(r'^\s*drop\s+index\s+(?!.*if\s+exists)', re.IGNORECASE | re.MULTILINE),
    re.compile(r'^\s*drop\s+schema\s+(?!.*if\s+exists)', re.IGNORECASE | re.MULTILINE),
    re.compile(r'^\s*drop\s+function\s+(?!.*if\s+exists)', re.IGNORECASE | re.MULTILINE),
]

# Irreversible DDL operations
_IRREVERSIBLE_PATTERNS = [
    re.compile(r'^\s*truncate\s+', re.IGNORECASE | re.MULTILINE),
    re.compile(r'^\s*alter\s+table\s+.*\bdrop\s+column\b(?!.*if\s+exists)', re.IGNORECASE | re.MULTILINE),
]


class TestRollbackSafety:
    """Validate that migrations don't contain patterns that make rollback dangerous."""

    def test_no_bare_drop_statements(self):
        """No migration should contain DROP without IF EXISTS.

        Bare DROP fails if the object doesn't exist, making partial
        rollback+retry impossible.
        """
        migrations = discover_migrations(MIGRATIONS_DIR)
        for mf in migrations:
            if mf.is_review:
                continue
            text = mf.path.read_text()
            # Strip SQL comments
            lines = [
                line for line in text.splitlines()
                if line.strip() and not line.strip().startswith('--')
            ]
            cleaned = '\n'.join(lines)
            for pattern in _BARE_DROP_PATTERNS:
                matches = pattern.findall(cleaned)
                assert not matches, (
                    f'{mf.filename} contains bare DROP statement(s) '
                    f'that make rollback dangerous: {matches}'
                )

    def test_no_irreversible_operations(self):
        """Migrations should not contain TRUNCATE or DROP COLUMN
        without IF EXISTS in V0 migrations."""
        migrations = discover_migrations(MIGRATIONS_DIR)
        for mf in migrations:
            if mf.is_review:
                continue
            text = mf.path.read_text()
            lines = [
                line for line in text.splitlines()
                if line.strip() and not line.strip().startswith('--')
            ]
            cleaned = '\n'.join(lines)
            for pattern in _IRREVERSIBLE_PATTERNS:
                matches = pattern.findall(cleaned)
                assert not matches, (
                    f'{mf.filename} contains irreversible DDL: {matches}'
                )

    def test_drop_if_exists_used_consistently(self):
        """Any DROP POLICY/TRIGGER uses IF EXISTS consistently."""
        migrations = discover_migrations(MIGRATIONS_DIR)
        drop_re = re.compile(
            r'^\s*drop\s+(policy|trigger)\s+',
            re.IGNORECASE | re.MULTILINE,
        )
        safe_drop_re = re.compile(
            r'^\s*drop\s+(policy|trigger)\s+if\s+exists\s+',
            re.IGNORECASE | re.MULTILINE,
        )
        for mf in migrations:
            if mf.is_review:
                continue
            text = mf.path.read_text()
            lines = [
                line for line in text.splitlines()
                if line.strip() and not line.strip().startswith('--')
            ]
            cleaned = '\n'.join(lines)
            all_drops = drop_re.findall(cleaned)
            safe_drops = safe_drop_re.findall(cleaned)
            assert len(all_drops) == len(safe_drops), (
                f'{mf.filename}: {len(all_drops)} DROP statements but '
                f'only {len(safe_drops)} use IF EXISTS'
            )


# =====================================================================
# 3. Sequence integrity — CI gate
# =====================================================================


class TestSequenceIntegrity:
    """Validate migration ordering for CI."""

    def test_no_sequence_gaps(self):
        """Migration sequence must be gapless (1, 2, 3, ...)."""
        migrations = discover_migrations(MIGRATIONS_DIR)
        warnings = check_sequence_gaps(migrations)
        assert warnings == [], (
            f'Migration sequence has gaps:\n'
            + '\n'.join(f'  - {w}' for w in warnings)
        )

    def test_no_duplicate_sequences(self):
        """No two migration files share the same sequence number.

        discover_migrations() raises ValueError on duplicates, so
        this test just verifies it completes without error.
        """
        migrations = discover_migrations(MIGRATIONS_DIR)
        assert len(migrations) > 0

    def test_sequences_start_from_reasonable_number(self):
        """First migration should start from 001, 002, or similar low number."""
        migrations = discover_migrations(MIGRATIONS_DIR)
        if not migrations:
            pytest.skip('No migrations found')
        assert migrations[0].sequence <= 10, (
            f'First migration starts at {migrations[0].sequence:03d}, '
            f'expected a low number (<=10)'
        )


# =====================================================================
# 4. Content sanity — non-empty, valid SQL
# =====================================================================


class TestContentSanity:

    def test_no_empty_migration_files(self):
        """Migration files must contain actual SQL, not just whitespace."""
        migrations = discover_migrations(MIGRATIONS_DIR)
        for mf in migrations:
            if mf.is_review:
                continue
            text = mf.path.read_text().strip()
            assert len(text) > 0, (
                f'{mf.filename} is empty — migration would be a no-op'
            )

    def test_migrations_contain_sql_statements(self):
        """Migration files should contain at least one SQL statement."""
        migrations = discover_migrations(MIGRATIONS_DIR)
        sql_keyword_re = re.compile(
            r'\b(create|alter|drop|insert|update|grant|revoke|enable)\b',
            re.IGNORECASE,
        )
        for mf in migrations:
            if mf.is_review:
                continue
            text = mf.path.read_text()
            # Remove comments
            lines = [
                line for line in text.splitlines()
                if line.strip() and not line.strip().startswith('--')
            ]
            cleaned = '\n'.join(lines)
            assert sql_keyword_re.search(cleaned), (
                f'{mf.filename} contains no recognizable SQL statements'
            )


# =====================================================================
# 5. Cross-file consistency
# =====================================================================


_TABLE_NAME_RE = re.compile(
    r'create\s+table\s+(?:if\s+not\s+exists\s+)?(\S+)',
    re.IGNORECASE,
)
_INDEX_NAME_RE = re.compile(
    r'create\s+(?:unique\s+)?index\s+(?:if\s+not\s+exists\s+)?(\S+)',
    re.IGNORECASE,
)


class TestCrossFileConsistency:

    def test_no_duplicate_table_definitions(self):
        """The same table should not be created in multiple migrations.

        This catches accidental duplication across migration files.
        IF NOT EXISTS means the second CREATE is a no-op (safe for rerun)
        but may indicate a copy-paste error.
        """
        migrations = discover_migrations(MIGRATIONS_DIR)
        table_origins: dict[str, str] = {}
        for mf in migrations:
            if mf.is_review:
                continue
            text = mf.path.read_text()
            lines = [
                line for line in text.splitlines()
                if line.strip() and not line.strip().startswith('--')
            ]
            cleaned = '\n'.join(lines)
            for name in _extract_object_names(cleaned, _TABLE_NAME_RE):
                if name in table_origins and table_origins[name] != mf.filename:
                    pytest.fail(
                        f'Table {name} defined in both '
                        f'{table_origins[name]} and {mf.filename}'
                    )
                table_origins[name] = mf.filename


# =====================================================================
# 6. Simulated rerun with synthetic migrations
# =====================================================================


class TestSimulatedRerun:
    """Test rerun/rollback scenarios with synthetic migration files."""

    def test_safe_migration_passes_double_validation(self, tmp_path):
        """A properly idempotent migration passes validation twice."""
        p = _write_sql(tmp_path, '001_safe.sql', '''\
            create schema if not exists cloud;
            create table if not exists cloud.things (
                id uuid primary key default gen_random_uuid()
            );
            create index if not exists ix_things_id on cloud.things(id);
        ''')
        result1 = validate_idempotency(p)
        result2 = validate_idempotency(p)
        assert result1.ok
        assert result2.ok

    def test_unsafe_migration_fails_consistently(self, tmp_path):
        """An unsafe migration fails validation every time."""
        p = _write_sql(tmp_path, '001_unsafe.sql', '''\
            create table cloud.things (
                id uuid primary key
            );
        ''')
        result1 = validate_idempotency(p)
        result2 = validate_idempotency(p)
        assert not result1.ok
        assert not result2.ok
        assert result1.errors == result2.errors

    def test_mixed_migration_reports_only_unsafe_lines(self, tmp_path):
        """A migration mixing safe and unsafe patterns reports only the bad lines."""
        p = _write_sql(tmp_path, '001_mixed.sql', '''\
            create schema if not exists cloud;
            create table cloud.things (id uuid primary key);
            create index if not exists ix_ok on cloud.things(id);
        ''')
        result = validate_idempotency(p)
        assert not result.ok
        assert len(result.errors) == 1
        assert 'CREATE TABLE without IF NOT EXISTS' in result.errors[0]

    def test_rollback_safe_pair_validates(self, tmp_path):
        """A migration pair (create + drop if exists + recreate) validates as safe."""
        p = _write_sql(tmp_path, '001_recreate.sql', '''\
            drop trigger if exists trg_updated on cloud.things;
            create trigger trg_updated before update on cloud.things
                for each row execute function cloud.set_updated_at();

            drop policy if exists rls_things on cloud.things;
            create policy rls_things on cloud.things for select using (true);
        ''')
        result = validate_idempotency(p)
        assert result.ok, f'Errors: {result.errors}'
