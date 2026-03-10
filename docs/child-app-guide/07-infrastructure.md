# 7. Infrastructure & Secrets

[< Back to Index](README.md) | [Prev: Deployment](06-deployment.md) | [Next: Database >](08-database.md)

---

## 7.1 Neon (Auth & Database — Recommended)

Neon is the recommended auth provider for new boring-ui apps. It offers 20 free projects (vs Supabase's 2) and built-in Neon Auth (Better Auth) with email/password authentication.

1. **Create a Neon project** at [neon.tech](https://neon.tech)
2. **Enable Neon Auth** in the project dashboard
3. **Run the boring-ui control plane migrations** against your Neon DB
4. **Store credentials** in your secret manager (Vault, Modal secrets, etc.)

Required secrets:
```
DATABASE_URL              # Neon Postgres connection string (pooler recommended)
NEON_AUTH_BASE_URL        # Neon Auth endpoint (e.g., https://ep-xxx.neonauth.region.aws.neon.tech/neondb/auth)
NEON_AUTH_JWKS_URL        # JWKS endpoint for JWT verification (e.g., .../.well-known/jwks.json)
BORING_UI_SESSION_SECRET  # Stable secret for signing boring-ui session cookies
BORING_SETTINGS_KEY       # Encryption key for workspace settings (optional)
```

**Auth flow:** Frontend POSTs to Neon Auth `/sign-up/email` or `/sign-in/email` → fetches EdDSA JWT from `/token` → exchanges it via `POST /auth/token-exchange` → backend verifies JWT via JWKS and issues a `boring_session` cookie (HS256, provider-independent).

## 7.2 Supabase (Legacy)

Still supported for existing deployments. Use Neon for new apps.

Required secrets:
```
SUPABASE_URL              # Project URL (e.g., https://xxx.supabase.co)
SUPABASE_ANON_KEY         # Public/publishable key
SUPABASE_SERVICE_ROLE_KEY # Server-side admin key
SUPABASE_DB_URL           # Postgres connection string (pooler recommended)
```

## 7.3 Modal Secrets

Create Modal secrets for your deploy:

```bash
# Neon (recommended)
modal secret create my-app-secrets \
  CONTROL_PLANE_PROVIDER=neon \
  DATABASE_URL="postgresql://neondb_owner:...@ep-xxx-pooler.region.aws.neon.tech/neondb?sslmode=require" \
  NEON_AUTH_BASE_URL="https://ep-xxx.neonauth.region.aws.neon.tech/neondb/auth" \
  NEON_AUTH_JWKS_URL="https://ep-xxx.neonauth.region.aws.neon.tech/neondb/auth/.well-known/jwks.json" \
  BORING_UI_SESSION_SECRET="your-stable-secret" \
  BORING_SETTINGS_KEY="your-settings-key" \
  MY_APP_DATABASE_URL="postgresql://..."

# Legacy Supabase
# modal secret create my-app-secrets \
#   SUPABASE_PROJECT_URL="https://xxx.supabase.co" \
#   SUPABASE_PUBLISHABLE_KEY="eyJ..." \
#   SUPABASE_SERVICE_ROLE_KEY="eyJ..." \
#   MY_APP_DATABASE_URL="postgresql://..."
#
# modal secret create my-app-dbpool \
#   SUPABASE_DB_URL_POOLER="postgresql://..."
```

Reference in `modal_app.py`:
```python
secrets = modal.Secret.from_name("my-app-secrets")

@app.function(secrets=[secrets], ...)
```

## 7.4 Vault (Self-hosted)

If using HashiCorp Vault:

```bash
# Neon credentials
vault kv put secret/agent/my-app-neon-db url="postgresql://neondb_owner:...@ep-xxx-pooler..."
vault kv put secret/agent/my-app-neon-auth-base-url url="https://ep-xxx.neonauth..."
vault kv put secret/agent/my-app-neon-auth-jwks-url url="https://ep-xxx.neonauth.../.well-known/jwks.json"
vault kv put secret/agent/my-app-session-secret secret="your-stable-secret"

# Domain-specific secrets
vault kv put secret/agent/my-app-database url="postgresql://..."
```

Read in scripts:
```bash
MY_DB_URL=$(vault kv get -field=url secret/agent/my-app-database)
```

Edge mode `app.toml` references Vault paths directly:
```toml
[neon]
database_url = "secret/agent/my-app-neon-db#url"
auth_base_url = "secret/agent/my-app-neon-auth-base-url#url"
auth_jwks_url = "secret/agent/my-app-neon-auth-jwks-url#url"
```

## 7.5 Email (Resend)

For auth emails (invitations, password resets):

```bash
# Store API key
vault kv put secret/agent/services/resend api_key="re_..."
```

Configure in `app.toml` (edge mode):
```toml
[email]
provider = "resend"
resend_api_key = "secret/agent/services/resend#api_key"
resend_from_email = "auth@mail.yourdomain.com"
resend_from_name = "Your App"
```

Or pass via Modal secrets (core mode):
```bash
modal secret create my-app-secrets \
  ... \
  RESEND_API_KEY="re_..."
```

## 7.6 Secret Naming Convention

```
secret/agent/{app-name}-{service}-{field}
```

Examples:
```
secret/agent/my-app-neon-db#url
secret/agent/my-app-neon-auth-base-url#url
secret/agent/my-app-supabase-project-url#url    # Legacy
secret/agent/my-app-clickhouse#url
secret/agent/services/resend#api_key             # Shared across apps
```
