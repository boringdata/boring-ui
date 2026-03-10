# 8. Database & Migrations

[< Back to Index](README.md) | [Prev: Infrastructure](07-infrastructure.md) | [Next: Build & Packaging >](09-build-packaging.md)

---

## 8.1 Control Plane (Neon or Supabase)

boring-ui manages its own tables for users, workspaces, memberships, and sessions. These are created by running boring-ui's control plane migrations against your Postgres database (Neon or Supabase — the schema is standard Postgres, no provider-specific features).

**Migration SQL:** `interface/boring-ui/deploy/sql/control_plane_supabase_schema.sql`

(The filename says "supabase" for historical reasons — the schema is pure standard Postgres and works on any provider including Neon.)

**How to run migrations:**
```bash
# Option 1: psql against Neon (recommended)
psql "$DATABASE_URL" -f interface/boring-ui/deploy/sql/control_plane_supabase_schema.sql

# Option 2: psql against Supabase (legacy)
psql "$SUPABASE_DB_URL" -f interface/boring-ui/deploy/sql/control_plane_supabase_schema.sql

# Option 3: Neon SQL Editor / Supabase SQL Editor
# Copy the contents of the SQL file and run it in the dashboard SQL Editor
```

**You do not need to manage these tables** — boring-ui handles them. Just ensure the migrations have been run against your database before enabling `CONTROL_PLANE_PROVIDER=neon` (or `supabase`).

**Requirements:** The schema uses `pgcrypto` extension (`gen_random_uuid()`), which is available on both Neon and Supabase by default.

## 8.2 Domain-Specific Database

For your app's domain data, you manage your own database and migrations. Choose the option that fits your use case:

### Option A: Same Supabase Instance (Additional Tables)

Best for: apps with relational domain data that benefits from being co-located with user/workspace data.

```sql
-- Run against your Supabase DB
CREATE TABLE my_domain_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id),
    name TEXT NOT NULL,
    data JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

Access from backend:
```python
# Use asyncpg (already a boring-ui dependency)
import asyncpg

pool = await asyncpg.create_pool(os.environ["SUPABASE_DB_URL"])
async with pool.acquire() as conn:
    rows = await conn.fetch("SELECT * FROM my_domain_items WHERE workspace_id = $1", ws_id)
```

### Option B: Separate Database (e.g., ClickHouse for Analytics)

Best for: apps with analytical/time-series workloads that need a specialized database.

```python
# backend/config.py
@dataclass
class ClickHouseConfig:
    host: str
    port: int
    username: str
    password: str
    database: str
    secure: bool = True

@dataclass
class AppConfig:
    workspace_root: Path
    clickhouse: ClickHouseConfig | None = None

def _resolve_clickhouse() -> ClickHouseConfig | None:
    url = os.environ.get("MY_APP_CLICKHOUSE_URL")
    if not url:
        return None
    parsed = urlparse(url)
    return ClickHouseConfig(
        host=parsed.hostname,
        port=parsed.port or 8443,
        username=parsed.username or "default",
        password=parsed.password or "",
        database=parsed.path.lstrip("/") or "default",
        secure=parsed.scheme == "https",
    )
```

### Option C: Local DuckDB (CLI-First Apps)

Best for: apps with a CLI that operates on local data, with optional web UI.

```sql
-- Created by your CLI init command
CREATE TABLE items (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

```rust
// In your Rust CLI
use duckdb::Connection;
let conn = Connection::open("data/my_app.duckdb")?;
```

## 8.3 Migration Strategy

boring-ui does not prescribe a migration tool. Options:

| Tool | Best for | Notes |
|------|----------|-------|
| Raw SQL files | Simple schemas | Run manually or via script |
| Alembic | Python + SQLAlchemy | Standard for FastAPI apps |
| Supabase migrations | Supabase-hosted | `supabase db push` |
| ClickHouse DDL | ClickHouse schemas | `clickhouse-client --query "CREATE TABLE..."` |

Keep migrations in a `migrations/` directory:
```
migrations/
├── 001_create_items.sql
├── 002_add_workspace_id.sql
└── README.md
```
