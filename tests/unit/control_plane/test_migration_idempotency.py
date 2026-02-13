"""Tests for migration discovery, ordering, and idempotency validation.

Bead: bd-223o.6.3 (A3)

Validates that the migration validation module correctly:
  - Discovers migration files by numeric prefix
  - Detects idempotency contract violations
  - Reports safe patterns as passing
  - Catches sequence gaps
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from control_plane.migrations import (
    MigrationFile,
    ValidationResult,
    check_sequence_gaps,
    discover_migrations,
    validate_all,
    validate_idempotency,
)


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def migrations_dir(tmp_path):
    """Create a temporary migrations directory with test SQL files."""
    return tmp_path


def _write_sql(directory: Path, name: str, content: str) -> Path:
    p = directory / name
    p.write_text(textwrap.dedent(content))
    return p


# =====================================================================
# 1. Migration discovery
# =====================================================================


class TestDiscoverMigrations:

    def test_discovers_numbered_sql_files(self, migrations_dir):
        _write_sql(migrations_dir, '001_initial.sql', 'SELECT 1;')
        _write_sql(migrations_dir, '002_second.sql', 'SELECT 2;')

        result = discover_migrations(migrations_dir)
        assert len(result) == 2
        assert result[0].sequence == 1
        assert result[1].sequence == 2

    def test_sorted_by_sequence(self, migrations_dir):
        _write_sql(migrations_dir, '003_third.sql', 'SELECT 3;')
        _write_sql(migrations_dir, '001_first.sql', 'SELECT 1;')

        result = discover_migrations(migrations_dir)
        assert [m.sequence for m in result] == [1, 3]

    def test_ignores_non_sql_files(self, migrations_dir):
        _write_sql(migrations_dir, '001_initial.sql', 'SELECT 1;')
        (migrations_dir / 'README.md').write_text('docs')
        (migrations_dir / 'notes.txt').write_text('notes')

        result = discover_migrations(migrations_dir)
        assert len(result) == 1

    def test_ignores_files_without_numeric_prefix(self, migrations_dir):
        _write_sql(migrations_dir, 'init.sql', 'SELECT 1;')
        _write_sql(migrations_dir, '001_valid.sql', 'SELECT 2;')

        result = discover_migrations(migrations_dir)
        assert len(result) == 1

    def test_duplicate_sequence_raises(self, migrations_dir):
        _write_sql(migrations_dir, '001_first.sql', 'SELECT 1;')
        _write_sql(migrations_dir, '001_duplicate.sql', 'SELECT 2;')

        with pytest.raises(ValueError, match='Duplicate migration sequence'):
            discover_migrations(migrations_dir)

    def test_review_file_detected(self, migrations_dir):
        _write_sql(migrations_dir, '001_rls_review.sql', 'SELECT 1;')

        result = discover_migrations(migrations_dir)
        assert result[0].is_review is True

    def test_non_review_file_detected(self, migrations_dir):
        _write_sql(migrations_dir, '001_core_schema.sql', 'SELECT 1;')

        result = discover_migrations(migrations_dir)
        assert result[0].is_review is False

    def test_empty_directory(self, migrations_dir):
        result = discover_migrations(migrations_dir)
        assert result == []


# =====================================================================
# 2. Idempotency validation — safe patterns
# =====================================================================


class TestValidateSafePatterns:

    def test_create_table_if_not_exists_passes(self, migrations_dir):
        p = _write_sql(migrations_dir, '001_ok.sql', '''\
            create table if not exists cloud.workspaces (
                id text primary key
            );
        ''')
        result = validate_idempotency(p)
        assert result.ok

    def test_create_index_if_not_exists_passes(self, migrations_dir):
        p = _write_sql(migrations_dir, '001_ok.sql', '''\
            create index if not exists ix_test on cloud.workspaces(id);
        ''')
        result = validate_idempotency(p)
        assert result.ok

    def test_create_unique_index_if_not_exists_passes(self, migrations_dir):
        p = _write_sql(migrations_dir, '001_ok.sql', '''\
            create unique index if not exists ux_test
                on cloud.workspaces(id);
        ''')
        result = validate_idempotency(p)
        assert result.ok

    def test_create_or_replace_function_passes(self, migrations_dir):
        p = _write_sql(migrations_dir, '001_ok.sql', '''\
            create or replace function cloud.set_updated_at()
            returns trigger as $$ begin return new; end; $$ language plpgsql;
        ''')
        result = validate_idempotency(p)
        assert result.ok

    def test_drop_trigger_before_create_passes(self, migrations_dir):
        p = _write_sql(migrations_dir, '001_ok.sql', '''\
            drop trigger if exists trg_test on cloud.workspaces;
            create trigger trg_test before update on cloud.workspaces
                for each row execute function cloud.set_updated_at();
        ''')
        result = validate_idempotency(p)
        assert result.ok

    def test_drop_policy_before_create_passes(self, migrations_dir):
        p = _write_sql(migrations_dir, '001_ok.sql', '''\
            drop policy if exists test_policy on cloud.workspaces;
            create policy test_policy on cloud.workspaces for select
                using (true);
        ''')
        result = validate_idempotency(p)
        assert result.ok

    def test_comments_and_blank_lines_ignored(self, migrations_dir):
        p = _write_sql(migrations_dir, '001_ok.sql', '''\
            -- This is a comment
            -- create table without_if_not_exists (bad);

            create schema if not exists cloud;
        ''')
        result = validate_idempotency(p)
        assert result.ok


# =====================================================================
# 3. Idempotency validation — unsafe patterns
# =====================================================================


class TestValidateUnsafePatterns:

    def test_create_table_without_if_not_exists_fails(self, migrations_dir):
        p = _write_sql(migrations_dir, '001_bad.sql', '''\
            create table cloud.workspaces (
                id text primary key
            );
        ''')
        result = validate_idempotency(p)
        assert not result.ok
        assert any('CREATE TABLE without IF NOT EXISTS' in e for e in result.errors)

    def test_create_index_without_if_not_exists_fails(self, migrations_dir):
        p = _write_sql(migrations_dir, '001_bad.sql', '''\
            create index ix_test on cloud.workspaces(id);
        ''')
        result = validate_idempotency(p)
        assert not result.ok
        assert any('CREATE INDEX without IF NOT EXISTS' in e for e in result.errors)

    def test_create_unique_index_without_if_not_exists_fails(self, migrations_dir):
        p = _write_sql(migrations_dir, '001_bad.sql', '''\
            create unique index ux_test on cloud.workspaces(id);
        ''')
        result = validate_idempotency(p)
        assert not result.ok
        assert any('CREATE INDEX without IF NOT EXISTS' in e for e in result.errors)

    def test_create_function_without_or_replace_fails(self, migrations_dir):
        p = _write_sql(migrations_dir, '001_bad.sql', '''\
            create function cloud.bad_func()
            returns void as $$ begin end; $$ language plpgsql;
        ''')
        result = validate_idempotency(p)
        assert not result.ok
        assert any('CREATE FUNCTION without OR REPLACE' in e for e in result.errors)

    def test_create_trigger_without_drop_fails(self, migrations_dir):
        p = _write_sql(migrations_dir, '001_bad.sql', '''\
            create trigger trg_test before update on cloud.workspaces
                for each row execute function cloud.set_updated_at();
        ''')
        result = validate_idempotency(p)
        assert not result.ok
        assert any('CREATE TRIGGER trg_test without' in e for e in result.errors)

    def test_create_policy_without_drop_fails(self, migrations_dir):
        p = _write_sql(migrations_dir, '001_bad.sql', '''\
            create policy test_policy on cloud.workspaces for select
                using (true);
        ''')
        result = validate_idempotency(p)
        assert not result.ok
        assert any('CREATE POLICY test_policy without' in e for e in result.errors)

    def test_create_schema_without_if_not_exists_fails(self, migrations_dir):
        p = _write_sql(migrations_dir, '001_bad.sql', '''\
            create schema cloud;
        ''')
        result = validate_idempotency(p)
        assert not result.ok
        assert any('CREATE SCHEMA without IF NOT EXISTS' in e for e in result.errors)

    def test_drop_table_without_if_exists_fails(self, migrations_dir):
        p = _write_sql(migrations_dir, '001_bad.sql', '''\
            drop table cloud.old_table;
        ''')
        result = validate_idempotency(p)
        assert not result.ok
        assert any('DROP TABLE without IF EXISTS' in e for e in result.errors)


# =====================================================================
# 4. Sequence gap detection
# =====================================================================


class TestSequenceGaps:

    def test_no_gaps(self):
        files = [
            MigrationFile(1, '001_a.sql', Path('001_a.sql')),
            MigrationFile(2, '002_b.sql', Path('002_b.sql')),
            MigrationFile(3, '003_c.sql', Path('003_c.sql')),
        ]
        assert check_sequence_gaps(files) == []

    def test_gap_detected(self):
        files = [
            MigrationFile(1, '001_a.sql', Path('001_a.sql')),
            MigrationFile(3, '003_c.sql', Path('003_c.sql')),
        ]
        warnings = check_sequence_gaps(files)
        assert len(warnings) == 1
        assert '001 -> 003' in warnings[0]

    def test_multiple_gaps(self):
        files = [
            MigrationFile(1, '001_a.sql', Path('001_a.sql')),
            MigrationFile(5, '005_e.sql', Path('005_e.sql')),
            MigrationFile(10, '010_j.sql', Path('010_j.sql')),
        ]
        warnings = check_sequence_gaps(files)
        assert len(warnings) == 2

    def test_single_file_no_gaps(self):
        files = [MigrationFile(1, '001_a.sql', Path('001_a.sql'))]
        assert check_sequence_gaps(files) == []

    def test_empty_list_no_gaps(self):
        assert check_sequence_gaps([]) == []


# =====================================================================
# 5. validate_all integration
# =====================================================================


class TestValidateAll:

    def test_validates_non_review_files(self, migrations_dir):
        _write_sql(migrations_dir, '001_review.sql', '''\
            -- Review only
            create policy bad_policy on cloud.workspaces for select using (true);
        ''')
        _write_sql(migrations_dir, '002_schema.sql', '''\
            create schema if not exists cloud;
        ''')

        results = validate_all(migrations_dir, skip_reviews=True)
        # Only 002 should be validated (001 is a review file)
        assert '002_schema.sql' in results
        assert '001_review.sql' not in results

    def test_validates_all_when_not_skipping_reviews(self, migrations_dir):
        _write_sql(migrations_dir, '001_review.sql', '''\
            create schema if not exists cloud;
        ''')
        _write_sql(migrations_dir, '002_schema.sql', '''\
            create schema if not exists cloud;
        ''')

        results = validate_all(migrations_dir, skip_reviews=False)
        assert len(results) == 2


# =====================================================================
# 6. Real migration validation
# =====================================================================


class TestRealMigrations:
    """Validate the actual project migration files."""

    def test_schema_migration_is_idempotent(self):
        """002_v0_core_schema.sql must pass idempotency validation."""
        from control_plane.migrations import MIGRATIONS_DIR
        schema_path = MIGRATIONS_DIR / '002_v0_core_schema.sql'
        if not schema_path.exists():
            pytest.skip('Schema migration not found')
        result = validate_idempotency(schema_path)
        assert result.ok, f'Idempotency errors: {result.errors}'

    def test_rls_migration_is_idempotent(self):
        """003_v0_rls_policies.sql must pass idempotency validation."""
        from control_plane.migrations import MIGRATIONS_DIR
        rls_path = MIGRATIONS_DIR / '003_v0_rls_policies.sql'
        if not rls_path.exists():
            pytest.skip('RLS migration not found')
        result = validate_idempotency(rls_path)
        assert result.ok, f'Idempotency errors: {result.errors}'

    def test_no_sequence_gaps(self):
        """Migration sequence should have no gaps."""
        from control_plane.migrations import MIGRATIONS_DIR
        migrations = discover_migrations(MIGRATIONS_DIR)
        warnings = check_sequence_gaps(migrations)
        assert warnings == [], f'Sequence gaps: {warnings}'

    def test_all_migrations_pass_validation(self):
        """All non-review migrations must pass idempotency checks."""
        from control_plane.migrations import MIGRATIONS_DIR
        results = validate_all(MIGRATIONS_DIR, skip_reviews=True)
        for filename, result in results.items():
            assert result.ok, (
                f'{filename} has idempotency errors: {result.errors}'
            )
