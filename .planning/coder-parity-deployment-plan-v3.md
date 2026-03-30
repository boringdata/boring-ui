# Coder-Parity Deployment Plan (v3 - Simplified)

**Goal**: Make boring-ui deployable like Coder - multi-platform, self-hosted, with enterprise features

**Status**: Draft (v3 - simplified based on architecture analysis)
**Created**: 2026-03-28
**Timeline**: 8-11 weeks (2-3 months)

---

## Architecture Reality Check

### What We Thought
- Workspaces = separate Fly.io machines
- Need complex provider abstraction (Fly API, K8s API, Docker API)
- Per-workspace provisioning logic

### What It Actually Is
```
┌─────────────────────────────────────┐
│  boring-ui Backend (Docker)         │
│  Single container running TS API     │
│                                      │
│  /workspaces/                        │
│  ├── abc123/ (user 1, bwrap jail)   │
│  ├── def456/ (user 2, bwrap jail)   │
│  └── ghi789/ (user 3, bwrap jail)   │
└─────────────────────────────────────┘
```

**Workspaces = local directories** sandboxed with `bwrap` (bubblewrap)

No Fly.io API calls. No per-workspace machines. Just a web app with sandboxed filesystems.

---

## Current Dependencies on Fly.io

1. **Deployment**: Uses `fly.toml` + `fly deploy` to run the Docker container
2. **That's it!**

The `machineId`/`volumeId`/`flyRegion` fields in the database are **unused/legacy**.

---

## What's Missing to Be Like Coder?

### ✅ Already Have
- Multi-user workspaces with RBAC
- Workspace sandboxing (bwrap)
- Auth (Neon Auth)
- File/git/exec operations
- TypeScript backend (Fastify)
- Web-based IDE

### ❌ Missing (Priority Order)

**1. Multi-Platform Deployment**
- Currently: Only Fly.io deployment documented
- Need: K8s manifests, Docker Compose, Helm chart
- **Gap**: Self-hosted enterprises can't deploy it

**2. Resource Management**
- No per-user quotas (unlimited workspaces, CPU, disk)
- No workspace templates (everyone starts from scratch)
- No auto-cleanup of idle/abandoned workspaces
- **Gap**: Resource exhaustion, poor onboarding UX

**3. Security & Observability**
- No audit logs (who did what when)
- No metrics (CPU/RAM/disk usage per workspace)
- No compliance features (GDPR export/delete)
- **Gap**: Can't deploy in regulated industries

**4. Operations**
- No IaC (manual setup)
- No HA/scaling docs
- No backup/restore procedures
- **Gap**: Hard to operate at scale

### 🟡 Out of Scope
- Organization/team multi-tenancy (workspaces already multi-user)
- SSH/VS Code Remote/CLI (web-only is fine)
- Real-time collaboration
- Per-workspace machines (current architecture is simpler)

---

## Phase 1: Multi-Platform Deployment (2-3 weeks)

**Goal**: Deploy boring-ui backend on Kubernetes, Docker, or Fly.io - user's choice

### 1.1 Kubernetes Manifests
**New directory**: `deploy/k8s/`

**File**: `deploy/k8s/deployment.yaml`
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: boring-ui
  namespace: boring-ui
spec:
  replicas: 3
  selector:
    matchLabels:
      app: boring-ui
  template:
    metadata:
      labels:
        app: boring-ui
    spec:
      containers:
      - name: backend
        image: ghcr.io/boring-data/boring-ui:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: boring-ui-secrets
              key: database-url
        - name: BORING_UI_SESSION_SECRET
          valueFrom:
            secretKeyRef:
              name: boring-ui-secrets
              key: session-secret
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: boring-ui-secrets
              key: anthropic-api-key
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
          limits:
            cpu: 2000m
            memory: 2Gi
        volumeMounts:
        - name: workspaces
          mountPath: /workspaces
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
      volumes:
      - name: workspaces
        persistentVolumeClaim:
          claimName: boring-ui-workspaces
---
apiVersion: v1
kind: Service
metadata:
  name: boring-ui
  namespace: boring-ui
spec:
  selector:
    app: boring-ui
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: boring-ui-workspaces
  namespace: boring-ui
spec:
  accessModes:
  - ReadWriteMany  # Multiple pods need access to same workspaces
  resources:
    requests:
      storage: 100Gi
  storageClassName: standard
```

**Critical**: PVC must be `ReadWriteMany` (RWX) so all pods can access the same workspaces. Use NFS, CephFS, or cloud storage (EFS, Azure Files, GCP Filestore).

### 1.2 Docker Compose (Self-Hosted)
**New file**: `deploy/docker-compose/docker-compose.yml`

```yaml
version: '3.8'

services:
  boring-ui:
    image: ghcr.io/boring-data/boring-ui:latest
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: ${DATABASE_URL}
      BORING_UI_SESSION_SECRET: ${BORING_UI_SESSION_SECRET}
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      NODE_ENV: production
    volumes:
      - workspaces:/workspaces
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G

  # Optional: PostgreSQL (if not using Neon)
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: boring_ui
      POSTGRES_USER: boring
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  workspaces:
  postgres_data:
```

**File**: `deploy/docker-compose/.env.example`
```bash
DATABASE_URL=postgresql://boring:password@postgres:5432/boring_ui
BORING_UI_SESSION_SECRET=generate-with-openssl-rand-hex-32
ANTHROPIC_API_KEY=sk-ant-...
POSTGRES_PASSWORD=generate-with-openssl-rand-hex-16
```

### 1.3 Helm Chart (Optional)
**New directory**: `deploy/helm/boring-ui/`

```yaml
# deploy/helm/boring-ui/Chart.yaml
apiVersion: v2
name: boring-ui
description: Self-hosted development workspaces
version: 1.0.0
appVersion: 1.0.0

# deploy/helm/boring-ui/values.yaml
replicaCount: 3

image:
  repository: ghcr.io/boring-data/boring-ui
  tag: latest
  pullPolicy: IfNotPresent

service:
  type: LoadBalancer
  port: 80

ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
  - host: boring-ui.yourdomain.com
    paths:
    - path: /
      pathType: Prefix

resources:
  limits:
    cpu: 2000m
    memory: 2Gi
  requests:
    cpu: 500m
    memory: 512Mi

persistence:
  enabled: true
  storageClass: ""
  accessMode: ReadWriteMany
  size: 100Gi

secrets:
  databaseUrl: ""
  sessionSecret: ""
  anthropicApiKey: ""
```

### 1.4 Deployment Documentation
**New file**: `docs/deployment/README.md`

```markdown
# Deploying boring-ui

boring-ui can be deployed to:
- **Fly.io** (managed, recommended)
- **Kubernetes** (self-hosted, enterprise)
- **Docker Compose** (single-server, small teams)

## Fly.io (Managed)

```bash
fly deploy -c deploy/fly/fly.backend-agent.toml
```

## Kubernetes

```bash
# Create namespace
kubectl create namespace boring-ui

# Create secrets
kubectl create secret generic boring-ui-secrets \
  --namespace boring-ui \
  --from-literal=database-url='postgresql://...' \
  --from-literal=session-secret='...' \
  --from-literal=anthropic-api-key='sk-ant-...'

# Deploy
kubectl apply -f deploy/k8s/

# Get LoadBalancer IP
kubectl get svc -n boring-ui boring-ui
```

### Prerequisites
- Kubernetes 1.28+
- Storage class with `ReadWriteMany` support (NFS, CephFS, cloud storage)
- PostgreSQL database (or use Neon)

## Docker Compose

```bash
cd deploy/docker-compose
cp .env.example .env
# Edit .env with your secrets
docker-compose up -d
```

Visit http://localhost:8000

## Database Setup

All deployments need PostgreSQL. Options:
1. **Neon** (managed, recommended): Create project at neon.tech
2. **Supabase** (managed): Create project at supabase.com
3. **Self-hosted**: Use Docker Compose postgres service

Run migrations:
```bash
npx drizzle-kit migrate
```
```

### 1.5 Health Checks
**File**: `src/server/http/healthRoutes.ts`

```typescript
import { FastifyPluginAsync } from 'fastify'
import { db } from '../db/index.js'
import { sql } from 'drizzle-orm'
import { existsSync } from 'node:fs'
import { hasBwrap } from '../workspace/helpers.js'

export const healthRoutes: FastifyPluginAsync = async (app) => {
  // Liveness probe (is process alive?)
  app.get('/health', async () => {
    return { status: 'ok', timestamp: Date.now() }
  })

  // Readiness probe (can handle traffic?)
  app.get('/health/ready', async (req, reply) => {
    const checks: Record<string, boolean> = {}

    // Database
    try {
      await db.execute(sql`SELECT 1`)
      checks.database = true
    } catch {
      checks.database = false
    }

    // Workspaces directory
    checks.workspaces = existsSync('/workspaces')

    // bwrap available
    checks.bwrap = hasBwrap()

    const healthy = Object.values(checks).every(v => v)

    if (!healthy) {
      reply.code(503)
    }

    return { status: healthy ? 'ready' : 'not_ready', checks }
  })
}
```

### Success Criteria
- [ ] K8s manifests deploy successfully
- [ ] Docker Compose starts on single server
- [ ] Helm chart installs with `helm install`
- [ ] Health checks return 200 OK
- [ ] Deployment docs cover all 3 platforms
- [ ] Can create workspaces on all platforms

---

## Phase 2: Resource Management (3-4 weeks)

**Goal**: Quotas, templates, auto-cleanup to prevent resource exhaustion

### 2.1 Per-User Quotas
**Schema**: `src/server/db/schema.ts`

```typescript
export const userQuotas = pgTable('user_quotas', {
  userId: uuid('user_id').primaryKey().notNull(),
  maxWorkspaces: integer('max_workspaces').default(5).notNull(),
  maxDiskPerWorkspace: integer('max_disk_per_workspace').default(10).notNull(), // GB
  maxTotalDisk: integer('max_total_disk').default(50).notNull(), // GB across all workspaces
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
  updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull()
})
```

**Service**: `src/server/services/quotaService.ts`

```typescript
export class QuotaService {
  async checkWorkspaceCreation(userId: string): Promise<void> {
    const quota = await this.getQuota(userId)
    const usage = await this.getUsage(userId)

    if (usage.workspaceCount >= quota.maxWorkspaces) {
      throw new QuotaExceededError(
        'workspaces',
        `Maximum ${quota.maxWorkspaces} workspaces allowed. Delete unused workspaces.`
      )
    }

    if (usage.totalDisk >= quota.maxTotalDisk) {
      throw new QuotaExceededError(
        'disk',
        `Maximum ${quota.maxTotalDisk}GB total disk allowed. Current usage: ${usage.totalDisk}GB`
      )
    }
  }

  async getUsage(userId: string) {
    const workspaces = await db.select()
      .from(workspaces)
      .where(
        and(
          eq(workspaces.createdBy, userId),
          isNull(workspaces.deletedAt)
        )
      )

    // Calculate disk usage by checking workspace directories
    let totalDisk = 0
    for (const ws of workspaces) {
      const path = `/workspaces/${ws.id}`
      const size = await getDirSize(path) // du -sb equivalent
      totalDisk += size
    }

    return {
      workspaceCount: workspaces.length,
      totalDisk: Math.ceil(totalDisk / 1024 / 1024 / 1024) // bytes to GB
    }
  }
}
```

### 2.2 Workspace Templates
**Schema**:
```typescript
export const workspaceTemplates = pgTable('workspace_templates', {
  id: uuid().defaultRandom().primaryKey().notNull(),
  name: text().notNull(),
  description: text(),
  initScript: text('init_script'), // bash script to run on first creation
  tags: jsonb().default([]),
  isPublic: boolean('is_public').default(true).notNull(),
  createdBy: uuid('created_by'),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull()
})
```

**Built-in templates**:
```typescript
const defaultTemplates = [
  {
    name: 'Blank Workspace',
    description: 'Empty workspace',
    initScript: null,
    tags: []
  },
  {
    name: 'Node.js Project',
    description: 'Node.js 20 with pnpm',
    initScript: `
#!/bin/bash
npm install -g pnpm
git config --global init.defaultBranch main
echo "Node.js workspace ready!"
    `.trim(),
    tags: ['node', 'javascript']
  },
  {
    name: 'Python Project',
    description: 'Python 3.11 with venv',
    initScript: `
#!/bin/bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
echo "Python workspace ready! Run: source .venv/bin/activate"
    `.trim(),
    tags: ['python']
  }
]
```

### 2.3 Auto-Cleanup Job
**File**: `src/server/jobs/cleanupJob.ts`

```typescript
import cron from 'node-cron'
import { db } from '../db/index.js'
import { workspaces } from '../db/schema.js'
import { rm } from 'node:fs/promises'

// Run daily at 2 AM
export function startCleanupJob() {
  cron.schedule('0 2 * * *', async () => {
    const cutoff = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000) // 30 days ago

    // Find workspaces marked as deleted > 30 days ago
    const toCleanup = await db.select()
      .from(workspaces)
      .where(
        and(
          isNotNull(workspaces.deletedAt),
          lt(workspaces.deletedAt, cutoff.toISOString())
        )
      )

    for (const ws of toCleanup) {
      const path = `/workspaces/${ws.id}`

      try {
        await rm(path, { recursive: true, force: true })
        console.log(`Cleaned up workspace ${ws.id}`)

        // Remove from DB
        await db.delete(workspaces).where(eq(workspaces.id, ws.id))
      } catch (err) {
        console.error(`Failed to cleanup ${ws.id}:`, err)
      }
    }
  })
}
```

### 2.4 Disk Usage Monitoring
**File**: `src/server/services/diskMonitor.ts`

```typescript
import { exec } from 'node:child_process'
import { promisify } from 'node:util'

const execAsync = promisify(exec)

export async function getDirSize(path: string): Promise<number> {
  try {
    const { stdout } = await execAsync(`du -sb ${path}`)
    const size = parseInt(stdout.split('\t')[0])
    return size
  } catch {
    return 0
  }
}

export async function getWorkspacesSummary() {
  const { stdout } = await execAsync('du -sh /workspaces/* 2>/dev/null || echo ""')
  const lines = stdout.trim().split('\n').filter(l => l)

  return lines.map(line => {
    const [size, path] = line.split('\t')
    const id = path.split('/').pop()
    return { id, size }
  })
}
```

### Success Criteria
- [ ] Quotas enforced at workspace creation
- [ ] 3+ built-in templates
- [ ] Template selection in UI
- [ ] Auto-cleanup runs daily
- [ ] Disk usage shown in UI

---

## Phase 3: Security & Observability (3-4 weeks)

**Goal**: Audit logs, metrics, compliance features

### 3.1 Audit Logs
**Schema**:
```typescript
export const auditLogs = pgTable('audit_logs', {
  id: uuid().defaultRandom().primaryKey().notNull(),
  userId: uuid('user_id').notNull(),
  action: text().notNull(), // 'workspace.create', 'file.write', etc.
  resourceType: text('resource_type'),
  resourceId: text('resource_id'),
  metadata: jsonb(),
  ipAddress: text('ip_address'),
  userAgent: text('user_agent'),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull()
})
```

**Middleware**: Automatically log all workspace operations

### 3.2 Metrics Collection
**File**: `src/server/jobs/metricsJob.ts`

Collect every 5 minutes:
- Workspace count
- Total disk usage
- Active users (last 24h)
- CPU/memory of backend process

### 3.3 GDPR Compliance
**Endpoints**:
- `GET /api/v1/users/:id/data-export` - Download all user data
- `DELETE /api/v1/users/:id/data` - Delete all user data (workspaces, logs, settings)

### Success Criteria
- [ ] Audit logs for all operations
- [ ] Metrics collected and stored
- [ ] GDPR export/delete works
- [ ] Admin can query audit logs

---

## Phase 4: Operations (2-3 weeks)

**Goal**: IaC, scaling, backup/restore

### 4.1 Terraform Module
**File**: `deploy/terraform/main.tf`

Automate K8s deployment with Terraform

### 4.2 Scaling Guide
- Vertical: Increase CPU/RAM per pod
- Horizontal: Increase replicas (requires RWX storage)
- Storage: Expand PVC size

### 4.3 Backup/Restore
- Database: Neon automatic backups (or pg_dump)
- Workspaces: Snapshot `/workspaces` volume
- Runbook for disaster recovery

### Success Criteria
- [ ] Terraform deploys to K8s
- [ ] Scaling guide documented
- [ ] Backup/restore tested

---

## Comparison to Coder

| Feature | Coder | boring-ui (current) | boring-ui (post-plan) |
|---------|-------|---------------------|----------------------|
| Self-hosted | ✅ | ❌ | ✅ Phase 1 |
| Kubernetes | ✅ | ❌ | ✅ Phase 1 |
| Docker Compose | ✅ | ❌ | ✅ Phase 1 |
| Resource quotas | ✅ | ❌ | ✅ Phase 2 |
| Workspace templates | ✅ | ❌ | ✅ Phase 2 |
| Auto-cleanup | ✅ | ❌ | ✅ Phase 2 |
| Audit logs | ✅ | ❌ | ✅ Phase 3 |
| Metrics | ✅ | ❌ | ✅ Phase 3 |
| GDPR compliance | ✅ | ❌ | ✅ Phase 3 |
| IaC | ✅ | ❌ | ✅ Phase 4 |
| Multi-user | ✅ | ✅ | ✅ Existing |
| Web IDE | ✅ | ✅ | ✅ Existing |
| SSH access | ✅ | ❌ | ❌ Out of scope |
| VS Code Remote | ✅ | ❌ | ❌ Out of scope |
| Per-workspace VMs | ✅ | ❌ | ❌ Different model |

**Different Architecture**:
- Coder: Each workspace = separate VM/container
- boring-ui: All workspaces = sandboxed directories in one container

**Tradeoffs**:
- 👍 Simpler, cheaper (no per-workspace overhead)
- 👍 Faster workspace creation (<1s vs 30s+)
- 👎 Workspaces share resources (less isolation)
- 👎 All workspaces go down if pod restarts

---

## Timeline

```
Week 1-2:   K8s manifests, Docker Compose, Helm
Week 3:     Deployment docs, health checks
Week 4-5:   Quotas, templates
Week 6-7:   Auto-cleanup, disk monitoring
Week 8:     Audit logs, metrics
Week 9:     GDPR compliance
Week 10:    Terraform, scaling docs
Week 11:    Backup/restore, final testing
```

**Total: 8-11 weeks**

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Storage RWX not available | High | Document RWX requirement upfront; test with NFS/EFS/etc |
| Disk usage calculation slow | Medium | Cache results, run async |
| Workspace cleanup too aggressive | High | 30-day grace period, warn before cleanup |
| Quota bypass via multiple accounts | Medium | Email verification, rate limiting |

---

## Questions for Review

1. **Storage**: Require RWX storage (NFS/CephFS/EFS) or single-pod only?
2. **Isolation**: Is bwrap sandbox enough or need per-workspace containers?
3. **Quotas**: Start with 5 workspaces, 50GB total - reasonable defaults?
4. **Cleanup**: 30-day grace period for deleted workspaces - too long/short?

---

## Next Steps

1. **Review this plan** - Confirm approach and priorities
2. **Phase 1 PoC** - Deploy to local K8s (minikube/kind) in 3 days
3. **Production K8s** - Deploy to real K8s cluster by week 3
4. **Phase 2-4** - Iterate based on Phase 1 learnings
