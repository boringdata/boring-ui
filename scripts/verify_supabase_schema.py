#!/usr/bin/env python3
"""Verify Supabase schema for Feature 3 V0.

Bead: bd-1joj.11 (MIG0)

Checks:
  1. cloud schema exists
  2. All 6 tables exist with required columns
  3. All required indexes exist
  4. RLS is enabled on all cloud.* tables
  5. RLS policies are active

Usage:
  # With DB URL from vault
  SUPABASE_DB_URL=$(vault kv get -field=url secret/agent/boring-ui-supabase-db-url) \\
      python3 scripts/verify_supabase_schema.py

  # With explicit URL
  SUPABASE_DB_URL=postgresql://... python3 scripts/verify_supabase_schema.py

Exit codes:
  0 = all checks pass
  1 = one or more checks fail
"""

import os
import subprocess
import sys
import json


def get_db_url() -> str:
    url = os.environ.get("SUPABASE_DB_URL", "")
    if not url:
        # Try vault
        try:
            result = subprocess.run(
                ["vault", "kv", "get", "-field=url", "secret/agent/boring-ui-supabase-db-url"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                url = result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
    if not url:
        print("ERROR: SUPABASE_DB_URL not set and vault lookup failed")
        sys.exit(1)
    return url


def psql_query(db_url: str, query: str) -> str:
    result = subprocess.run(
        ["psql", db_url, "-t", "-A", "-c", query],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        print(f"  psql error: {result.stderr.strip()}")
        return ""
    return result.stdout.strip()


def check_schema_exists(db_url: str) -> bool:
    out = psql_query(db_url, "SELECT 1 FROM information_schema.schemata WHERE schema_name = 'cloud';")
    return out == "1"


def check_tables_exist(db_url: str) -> dict[str, bool]:
    expected = [
        "workspaces",
        "workspace_members",
        "workspace_runtime",
        "workspace_provision_jobs",
        "audit_events",
        "file_share_links",
    ]
    results = {}
    for table in expected:
        out = psql_query(
            db_url,
            f"SELECT 1 FROM information_schema.tables "
            f"WHERE table_schema = 'cloud' AND table_name = '{table}';",
        )
        results[table] = out == "1"
    return results


def check_columns(db_url: str) -> dict[str, list[str]]:
    """Check required columns exist. Returns missing columns per table."""
    required_columns = {
        "workspaces": ["id", "app_id", "name", "owner_id", "created_at", "updated_at"],
        "workspace_members": ["id", "workspace_id", "user_id", "email", "role", "status", "created_at"],
        "workspace_runtime": ["workspace_id", "app_id", "state", "release_id", "sandbox_name", "bundle_sha256"],
        "workspace_provision_jobs": [
            "id", "workspace_id", "state", "attempt", "idempotency_key",
            "last_error_code", "request_id", "created_at",
        ],
        "audit_events": ["id", "workspace_id", "user_id", "action", "request_id", "payload", "created_at"],
        "file_share_links": [
            "id", "workspace_id", "token_hash", "path", "access",
            "created_by", "expires_at", "revoked_at", "created_at",
        ],
    }
    missing: dict[str, list[str]] = {}
    for table, cols in required_columns.items():
        out = psql_query(
            db_url,
            f"SELECT column_name FROM information_schema.columns "
            f"WHERE table_schema = 'cloud' AND table_name = '{table}';",
        )
        existing = set(out.split("\n")) if out else set()
        table_missing = [c for c in cols if c not in existing]
        if table_missing:
            missing[table] = table_missing
    return missing


def check_indexes(db_url: str) -> dict[str, bool]:
    expected_indexes = [
        "ix_workspaces_app_id",
        "ix_workspaces_owner_id",
        "ux_workspace_members_email",
        "ix_workspace_members_user_id",
        "ix_workspace_runtime_app_id",
        "ix_workspace_runtime_app_release",
        "ix_workspace_runtime_sandbox_name",
        "ux_workspace_jobs_active",
        "ux_workspace_jobs_idempotency",
        "ix_audit_events_workspace_request",
        "ix_audit_events_workspace_action",
        "ux_file_share_links_token_hash",
        "ix_file_share_links_workspace_path",
        "ix_file_share_links_expires",
    ]
    results = {}
    for idx in expected_indexes:
        out = psql_query(
            db_url,
            f"SELECT 1 FROM pg_indexes WHERE schemaname = 'cloud' AND indexname = '{idx}';",
        )
        results[idx] = out == "1"
    return results


def check_rls_enabled(db_url: str) -> dict[str, bool]:
    tables = [
        "workspaces", "workspace_members", "workspace_runtime",
        "workspace_provision_jobs", "audit_events", "file_share_links",
    ]
    results = {}
    for table in tables:
        out = psql_query(
            db_url,
            f"SELECT rowsecurity FROM pg_tables "
            f"WHERE schemaname = 'cloud' AND tablename = '{table}';",
        )
        results[table] = out.strip() == "t"
    return results


def check_rls_policies(db_url: str) -> dict[str, int]:
    """Count RLS policies per table. Each table should have >= 2."""
    tables = [
        "workspaces", "workspace_members", "workspace_runtime",
        "workspace_provision_jobs", "audit_events", "file_share_links",
    ]
    results = {}
    for table in tables:
        out = psql_query(
            db_url,
            f"SELECT count(*) FROM pg_policies "
            f"WHERE schemaname = 'cloud' AND tablename = '{table}';",
        )
        results[table] = int(out) if out.isdigit() else 0
    return results


def main() -> int:
    db_url = get_db_url()
    all_pass = True

    print("=" * 60)
    print("Supabase Schema Verification — Feature 3 V0")
    print("=" * 60)

    # 1. Schema
    print("\n1. Cloud schema exists:")
    if check_schema_exists(db_url):
        print("   PASS: cloud schema exists")
    else:
        print("   FAIL: cloud schema missing")
        all_pass = False

    # 2. Tables
    print("\n2. Required tables (6):")
    tables = check_tables_exist(db_url)
    for table, exists in tables.items():
        status = "PASS" if exists else "FAIL"
        print(f"   {status}: cloud.{table}")
        if not exists:
            all_pass = False

    # 3. Columns
    print("\n3. Required columns:")
    missing_cols = check_columns(db_url)
    if not missing_cols:
        print("   PASS: all required columns present")
    else:
        for table, cols in missing_cols.items():
            print(f"   FAIL: cloud.{table} missing columns: {', '.join(cols)}")
            all_pass = False

    # 4. Indexes
    print("\n4. Required indexes (14):")
    indexes = check_indexes(db_url)
    for idx, exists in indexes.items():
        status = "PASS" if exists else "FAIL"
        print(f"   {status}: {idx}")
        if not exists:
            all_pass = False

    # 5. RLS enabled
    print("\n5. RLS enabled on all tables:")
    rls = check_rls_enabled(db_url)
    for table, enabled in rls.items():
        status = "PASS" if enabled else "FAIL"
        print(f"   {status}: cloud.{table} (RLS={'enabled' if enabled else 'DISABLED'})")
        if not enabled:
            all_pass = False

    # 6. RLS policies
    print("\n6. RLS policies active (>= 2 per table):")
    policies = check_rls_policies(db_url)
    for table, count in policies.items():
        ok = count >= 2
        status = "PASS" if ok else "FAIL"
        print(f"   {status}: cloud.{table} ({count} policies)")
        if not ok:
            all_pass = False

    # Summary
    print("\n" + "=" * 60)
    if all_pass:
        print("RESULT: ALL CHECKS PASSED")
    else:
        print("RESULT: SOME CHECKS FAILED")
    print("=" * 60)

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
