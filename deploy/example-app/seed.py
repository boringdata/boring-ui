#!/usr/bin/env python3
"""Seed test users and workspaces for E2E scenario validation.

Bead: bd-223o.16.2 (K2)

Idempotent: safe to run multiple times -- existing records are skipped.

Usage::

    # With config.env loaded:
    python3 deploy/example-app/seed.py

    # Or with explicit env vars:
    SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... python3 deploy/example-app/seed.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SeedUser:
    email: str
    password: str
    role: str
    display_name: str


@dataclass
class SeedWorkspace:
    slug: str
    name: str
    owner_email: str
    files: dict[str, str] = field(default_factory=dict)


# ── Seed data definitions ────────────────────────────────────────────

SEED_USERS = [
    SeedUser(
        email="alice@e2e.test",
        password=os.environ.get("SEED_USER_ALICE_PASSWORD", "alice-e2e-test-2026"),
        role="owner",
        display_name="Alice (E2E)",
    ),
    SeedUser(
        email="bob@e2e.test",
        password=os.environ.get("SEED_USER_BOB_PASSWORD", "bob-e2e-test-2026"),
        role="member",
        display_name="Bob (E2E)",
    ),
    SeedUser(
        email="eve@e2e.test",
        password=os.environ.get("SEED_USER_EVE_PASSWORD", "eve-e2e-test-2026"),
        role="none",
        display_name="Eve (E2E)",
    ),
]

SEED_WORKSPACES = [
    SeedWorkspace(
        slug="ws-alpha",
        name="Alpha Workspace",
        owner_email="alice@e2e.test",
        files={
            "README.md": "# Alpha Workspace\n\nE2E test workspace for file editing scenarios.\n",
            "src/main.py": '"""Entry point for the example app."""\n\ndef main():\n    print("Hello from Alpha")\n\nif __name__ == "__main__":\n    main()\n',
        },
    ),
    SeedWorkspace(
        slug="ws-beta",
        name="Beta Workspace",
        owner_email="alice@e2e.test",
        files={},
    ),
]


# ── Supabase Admin API helpers ────────────────────────────────────────


def _get_config() -> tuple[str, str]:
    """Load Supabase URL and service role key from env or Vault."""
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    if not url:
        try:
            url = subprocess.check_output(
                ["vault", "kv", "get", "-field=value",
                 "secret/agent/boring-ui-supabase-project-url"],
                text=True,
            ).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

    if not key:
        try:
            key = subprocess.check_output(
                ["vault", "kv", "get", "-field=value",
                 "secret/agent/boring-ui-supabase-service-role-key"],
                text=True,
            ).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required.")
        print("Set via environment or ensure Vault is accessible.")
        sys.exit(1)

    return url, key


def _supabase_request(
    url: str,
    key: str,
    path: str,
    *,
    method: str = "GET",
    data: dict | None = None,
) -> dict | list | None:
    """Make an authenticated request to the Supabase Admin API."""
    full_url = f"{url}{path}"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(full_url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        if e.code == 422 and "already been registered" in error_body:
            return None  # User already exists -- idempotent.
        print(f"  Supabase API error {e.code}: {error_body}")
        return None


# ── Seed operations ──────────────────────────────────────────────────


def seed_users(url: str, key: str) -> dict[str, str]:
    """Create test users via Supabase Admin API. Returns email → user_id map."""
    user_ids: dict[str, str] = {}
    print("Seeding users...")
    for user in SEED_USERS:
        result = _supabase_request(
            url, key, "/auth/v1/admin/users",
            method="POST",
            data={
                "email": user.email,
                "password": user.password,
                "email_confirm": True,
                "user_metadata": {
                    "display_name": user.display_name,
                    "role": user.role,
                    "e2e_seed": True,
                },
            },
        )
        if result and "id" in result:
            user_ids[user.email] = result["id"]
            print(f"  + {user.email} ({user.role}) → {result['id']}")
        else:
            # Try to look up existing user.
            users = _supabase_request(url, key, "/auth/v1/admin/users")
            if users and "users" in users:
                for u in users["users"]:
                    if u.get("email") == user.email:
                        user_ids[user.email] = u["id"]
                        print(f"  = {user.email} ({user.role}) → {u['id']} (exists)")
                        break
    return user_ids


def seed_workspaces(user_ids: dict[str, str]) -> None:
    """Document workspace seed records.

    Note: actual workspace creation happens through the control plane
    API after deployment. This function writes a seed manifest that
    the scenario runner (K3) uses to create workspaces via API calls.
    """
    print("Writing workspace seed manifest...")
    manifest = []
    for ws in SEED_WORKSPACES:
        owner_id = user_ids.get(ws.owner_email, "")
        manifest.append({
            "slug": ws.slug,
            "name": ws.name,
            "owner_email": ws.owner_email,
            "owner_id": owner_id,
            "files": ws.files,
        })

    manifest_path = Path(__file__).parent / "seed_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"  Wrote {manifest_path}")
    for ws in SEED_WORKSPACES:
        file_count = len(ws.files)
        print(f"  + {ws.slug} ({ws.name}) → {file_count} file(s)")


def main() -> None:
    print("=== E2E Seed: boring-ui example app ===\n")
    url, key = _get_config()
    print(f"Supabase: {url}\n")

    user_ids = seed_users(url, key)
    print()
    seed_workspaces(user_ids)

    print("\nSeed complete.")
    print(f"Users: {len(user_ids)}")
    print(f"Workspaces: {len(SEED_WORKSPACES)}")
    print("\nNext: bash deploy/example-app/validate.sh")


if __name__ == "__main__":
    main()
