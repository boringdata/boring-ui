# Example App Deployment for E2E Validation

**Bead:** bd-223o.16.2 (K2)

Deterministic deployment configuration for the Feature 3 V0 example app
used as the canonical target for scenario execution (test-scenarios/).

## Environment Assumptions

| Property | Value | Source |
|---|---|---|
| **Sprite name** | `boring-ui-e2e` | deploy/example-app/config.env |
| **App ID** | `e2e-example` | AppIdentityResolver host mapping |
| **Host** | `boring-ui-e2e-<hash>.sprites.app` | Sprite URL after deploy |
| **Release ID** | `e2e-v0-<git-sha>` | Deterministic from HEAD |
| **Control plane port** | 8000 | Sprite service config |
| **Supabase project** | From Vault | `secret/agent/boring-ui-supabase-*` |

## Test Users

Seeded by `seed.py` into Supabase `auth.users`:

| User | Email | Role | Purpose |
|---|---|---|---|
| **alice** | `alice@e2e.test` | owner | Primary scenario actor (S-001 through S-005) |
| **bob** | `bob@e2e.test` | member | Multi-user scenarios (S-003, S-007) |
| **eve** | `eve@e2e.test` | none | Negative auth scenarios (S-008) |

## Seeded Workspaces

Created by `seed.py` after user seeding:

| Workspace | Owner | Files | Purpose |
|---|---|---|---|
| `ws-alpha` | alice | `README.md`, `src/main.py` | File editing (S-004) |
| `ws-beta` | alice | (empty) | Workspace switch (S-003) |

## Quick Start

```bash
# 1. Copy and fill environment config.
cp deploy/example-app/config.env.template deploy/example-app/config.env
# (Or source secrets from Vault -- see below.)

# 2. Deploy the example app to a sprite.
bash deploy/example-app/deploy.sh

# 3. Seed test users and workspaces.
python3 deploy/example-app/seed.py

# 4. Validate the environment is scenario-ready.
bash deploy/example-app/validate.sh
```

### Secrets from Vault

```bash
export SUPABASE_URL=$(vault kv get -field=value secret/agent/boring-ui-supabase-project-url)
export SUPABASE_SERVICE_ROLE_KEY=$(vault kv get -field=value secret/agent/boring-ui-supabase-service-role-key)
export SUPABASE_PUBLISHABLE_KEY=$(vault kv get -field=value secret/agent/boring-ui-supabase-publishable-key)
```

## Determinism Guarantees

1. **Fixed seed data** -- `seed.py` is idempotent; re-running creates the
   same users/workspaces without duplicates.
2. **Pinned release ID** -- derived from `git rev-parse --short HEAD` so
   every deploy of the same commit produces the same release tag.
3. **No external dependencies** -- scenarios reference only the seeded data
   and the deployed app; no third-party API calls.
4. **Reproducible environment** -- `validate.sh` checks all preconditions
   so scenario failures can be attributed to app behavior, not env drift.

## Lifecycle

```
deploy.sh → seed.py → validate.sh → (scenario runner K3)
```

After scenarios complete, the environment can be torn down with:

```bash
sprite destroy -force boring-ui-e2e
```

## Files

| File | Purpose |
|---|---|
| `README.md` | This document |
| `config.env.template` | Environment variable template |
| `deploy.sh` | Deploy workspace API + control plane to sprite |
| `seed.py` | Seed test users, workspaces, and content |
| `validate.sh` | Pre-scenario health and data validation |
| `app_identity.json` | App identity resolver config for e2e host |
