# Coder-Parity Deployment Plan

**Goal**: Transform boring-ui into an enterprise-ready, multi-provider development platform comparable to Coder.

**Status**: Draft (Updated 2026-03-28)
**Created**: 2026-03-28
**Target**: Q2-Q3 2026

---

## Executive Summary

boring-ui currently has strong foundations (multi-user workspaces, RBAC, Fly.io provisioning, auth), but lacks enterprise deployment features. This plan addresses critical gaps across 4 phases, prioritizing **infrastructure abstraction** as the key enabler.

**Timeline**: 16-21 weeks total (4-5 months)

**Current State**: Fly.io-only, web-based IDE with basic workspace provisioning
**Target State**: Multi-provider platform with templates, resource quotas, and enterprise security

**Key Priority**: Infrastructure abstraction (support Kubernetes, Docker, multiple clouds) - this unlocks self-hosted and bring-your-own-infrastructure deployments.

---

## Gap Analysis

### ✅ Already Have
- Multi-user workspaces with RBAC (owner/editor/viewer)
- Workspace provisioning (Fly.io + bwrap)
- Neon Auth + session management
- File/git/exec operations
- Workspace invites & encrypted settings
- TypeScript backend (Fastify + Drizzle ORM)

### ❌ Critical Gaps
1. **Infrastructure** (Priority #1): Locked to Fly.io, no provider abstraction - blocks self-hosted deployments
2. **Resource Management**: No quotas, templates, or auto-shutdown policies
3. **Security**: No audit logs, network policies, compliance features
4. **Monitoring**: No metrics, cost tracking, or usage analytics
5. **Operations**: No HA, disaster recovery, or IaC

### 🟡 Out of Scope (for now)
- Organization/team multi-tenancy (workspaces abstraction already exists)
- IDE integration (SSH, VS Code Remote, CLI) - web-only is sufficient
- Real-time collaboration

---

## Phase 1: Multi-Tenancy Foundation (4-6 weeks)

**Goal**: Enable organization-based workspace management with quotas

### 1.1 Organization Schema
**File**: `src/server/db/schema.ts`

Add tables:
```typescript
organizations (id, name, slug, created_at, deleted_at)
organization_members (org_id, user_id, role, created_at)
  - roles: admin, member, billing
organization_quotas (org_id, max_workspaces, max_cpu, max_ram, max_storage)
organization_usage (org_id, active_workspaces, cpu_hours, storage_gb, updated_at)
```

**Changes**:
- Add `org_id` to `workspaces` table (nullable, backfill later)
- Unique constraint: `(org_id, slug)` for org-scoped workspace names

### 1.2 Organization Service
**New file**: `src/server/services/organizationService.ts`

```typescript
interface OrganizationService {
  createOrganization(name: string, createdBy: string): Promise<Organization>
  addMember(orgId: string, userId: string, role: OrgRole): Promise<void>
  getQuotas(orgId: string): Promise<OrgQuotas>
  checkQuota(orgId: string, resource: 'workspaces' | 'cpu' | 'ram'): Promise<boolean>
  trackUsage(orgId: string, metrics: UsageMetrics): Promise<void>
}
```

### 1.3 Quota Enforcement
**Files**:
- `src/server/services/workspacePersistence.ts` (modify `createWorkspace`)
- `src/server/workspace/resolver.ts` (add quota checks)

**Logic**:
```typescript
async createWorkspace(userId: string, orgId: string, name: string) {
  const canCreate = await orgService.checkQuota(orgId, 'workspaces')
  if (!canCreate) throw new QuotaExceededError('workspaces')

  // existing workspace creation...
  await orgService.trackUsage(orgId, { active_workspaces: +1 })
}
```

### 1.4 Admin Dashboard (MVP)
**New files**:
- `src/front/pages/OrgSettings.jsx` - Org management UI
- `src/front/components/QuotaMonitor.jsx` - Usage visualization

**Features**:
- List org members, invite/remove
- View quotas and current usage
- Workspace list (org-scoped)

### 1.5 Migration Strategy
**File**: `src/server/db/migrations/001_add_organizations.sql`

```sql
-- Create organizations from existing users (each user gets a personal org)
INSERT INTO organizations (id, name, slug, created_at)
SELECT
  gen_random_uuid(),
  user_settings.display_name || '''s Organization',
  LOWER(REGEXP_REPLACE(user_settings.email, '@.*', '', 'g')),
  NOW()
FROM user_settings;

-- Backfill workspaces.org_id
UPDATE workspaces w
SET org_id = (
  SELECT o.id FROM organizations o
  JOIN organization_members om ON om.org_id = o.id
  WHERE om.user_id = w.created_by AND om.role = 'admin'
  LIMIT 1
);
```

**Success Criteria**:
- [ ] Orgs table created with quotas
- [ ] Existing workspaces migrated to personal orgs
- [ ] Quota checks block workspace creation when exceeded
- [ ] Admin can view org usage in UI

---

## Phase 2: Workspace Templates & Lifecycle (3-4 weeks)

**Goal**: Pre-configured workspace templates with auto-shutdown policies

### 2.1 Template Schema
**File**: `src/server/db/schema.ts`

```typescript
workspace_templates (
  id, org_id, name, description,
  dockerfile_url, init_script,
  default_cpu, default_ram, default_storage,
  tags jsonb, created_by, created_at
)

workspace_lifecycle_policies (
  workspace_id,
  auto_shutdown_minutes,
  auto_start_on_connect,
  max_lifetime_hours,
  updated_at
)
```

### 2.2 Template Service
**New file**: `src/server/services/templateService.ts`

```typescript
interface TemplateService {
  createTemplate(orgId: string, config: TemplateConfig): Promise<Template>
  listTemplates(orgId: string): Promise<Template[]>
  instantiateTemplate(templateId: string, name: string): Promise<Workspace>
}

interface TemplateConfig {
  name: string
  baseImage: string  // e.g., 'node:20', 'python:3.11'
  initScript?: string  // post-create bash script
  defaultCpu: number
  defaultRam: number
  tools?: string[]  // ['git', 'docker', 'kubectl']
}
```

### 2.3 Auto-Shutdown Job
**New file**: `src/server/jobs/workspaceLifecycle.ts`

```typescript
// Cron job: every 5 minutes
async function checkWorkspaceLifecycles() {
  const policies = await db.select()
    .from(workspaceLifecyclePolicies)
    .where(eq(workspaceLifecyclePolicies.autoShutdownMinutes, gt(0)))

  for (const policy of policies) {
    const runtime = await getRuntimeStatus(policy.workspaceId)
    const idleMinutes = getIdleTime(runtime.lastActivityAt)

    if (idleMinutes >= policy.autoShutdownMinutes) {
      await shutdownWorkspace(policy.workspaceId)
      await recordEvent('workspace.auto_shutdown', { workspaceId, idleMinutes })
    }
  }
}
```

**Integration**: `src/server/app.ts`
```typescript
import cron from 'node-cron'

// Run every 5 minutes
cron.schedule('*/5 * * * *', checkWorkspaceLifecycles)
```

### 2.4 Template UI
**New files**:
- `src/front/pages/Templates.jsx` - Template gallery
- `src/front/components/TemplateCard.jsx` - Template preview
- `src/front/dialogs/CreateFromTemplate.jsx` - Template instantiation

**Features**:
- Browse templates (org + public templates)
- One-click workspace creation from template
- Template preview (tools, resources, init script)

### 2.5 Built-in Templates
**New file**: `deploy/templates/default.json`

```json
[
  {
    "id": "node-fullstack",
    "name": "Node.js Full-Stack",
    "baseImage": "node:20-bookworm",
    "tools": ["git", "docker", "postgresql-client"],
    "initScript": "npm install -g pnpm tsx vitest",
    "defaultCpu": 2,
    "defaultRam": 4096
  },
  {
    "id": "python-data",
    "name": "Python Data Science",
    "baseImage": "python:3.11-bookworm",
    "tools": ["git", "jupyter"],
    "initScript": "pip install pandas numpy matplotlib scikit-learn",
    "defaultCpu": 4,
    "defaultRam": 8192
  }
]
```

**Success Criteria**:
- [ ] Templates table + CRUD API
- [ ] 3+ built-in templates (Node, Python, Go)
- [ ] Auto-shutdown after 30min idle (configurable)
- [ ] Template gallery in UI
- [ ] Workspace creation from template (<30s)

---

## Phase 3: Infrastructure Abstraction (5-6 weeks)

**Goal**: Support multiple infrastructure providers (Fly.io, K8s, Docker)

### 3.1 Provider Abstraction
**New file**: `src/server/provisioning/providers/base.ts`

```typescript
interface WorkspaceProvider {
  name: string  // 'fly', 'kubernetes', 'docker'

  create(config: WorkspaceConfig): Promise<WorkspaceRuntime>
  destroy(runtimeId: string): Promise<void>
  start(runtimeId: string): Promise<void>
  stop(runtimeId: string): Promise<void>
  getStatus(runtimeId: string): Promise<RuntimeStatus>
  getMetrics(runtimeId: string): Promise<ResourceMetrics>
  exec(runtimeId: string, command: string): Promise<ExecResult>
}

interface WorkspaceConfig {
  workspaceId: string
  template: Template
  cpu: number
  ram: number
  storage: number
  region?: string
}
```

### 3.2 Fly.io Provider (existing → refactor)
**File**: `src/server/provisioning/providers/fly.ts`

```typescript
export class FlyProvider implements WorkspaceProvider {
  name = 'fly'

  async create(config: WorkspaceConfig): Promise<WorkspaceRuntime> {
    // Existing Fly.io machine creation logic
    const machine = await flyApi.createMachine({
      app: config.workspaceId,
      config: {
        image: config.template.baseImage,
        guest: { cpus: config.cpu, memory_mb: config.ram }
      }
    })

    return {
      provider: 'fly',
      machineId: machine.id,
      region: machine.region,
      status: 'provisioning'
    }
  }

  // ... other methods
}
```

### 3.3 Kubernetes Provider (new)
**File**: `src/server/provisioning/providers/kubernetes.ts`

```typescript
import * as k8s from '@kubernetes/client-node'

export class KubernetesProvider implements WorkspaceProvider {
  name = 'kubernetes'
  private k8sApi: k8s.CoreV1Api

  async create(config: WorkspaceConfig): Promise<WorkspaceRuntime> {
    const namespace = `workspace-${config.workspaceId}`

    // Create namespace
    await this.k8sApi.createNamespace({
      metadata: { name: namespace }
    })

    // Create PVC for workspace storage
    await this.k8sApi.createNamespacedPersistentVolumeClaim(namespace, {
      metadata: { name: 'workspace-storage' },
      spec: {
        accessModes: ['ReadWriteOnce'],
        resources: { requests: { storage: `${config.storage}Gi` } }
      }
    })

    // Create pod with bwrap
    const pod = await this.k8sApi.createNamespacedPod(namespace, {
      metadata: { name: 'workspace' },
      spec: {
        containers: [{
          name: 'workspace',
          image: config.template.baseImage,
          resources: {
            requests: { cpu: `${config.cpu}`, memory: `${config.ram}Mi` },
            limits: { cpu: `${config.cpu}`, memory: `${config.ram}Mi` }
          },
          volumeMounts: [{ name: 'storage', mountPath: '/workspace' }]
        }],
        volumes: [{ name: 'storage', persistentVolumeClaim: { claimName: 'workspace-storage' } }]
      }
    })

    return {
      provider: 'kubernetes',
      namespace,
      podName: pod.metadata.name,
      status: 'provisioning'
    }
  }

  // ... other methods
}
```

### 3.4 Provider Registry
**New file**: `src/server/provisioning/registry.ts`

```typescript
import { FlyProvider } from './providers/fly.js'
import { KubernetesProvider } from './providers/kubernetes.js'
import { DockerProvider } from './providers/docker.js'

export class ProviderRegistry {
  private providers = new Map<string, WorkspaceProvider>()

  constructor() {
    this.register(new FlyProvider())
    if (process.env.KUBECONFIG) {
      this.register(new KubernetesProvider())
    }
    if (process.env.DOCKER_HOST) {
      this.register(new DockerProvider())
    }
  }

  register(provider: WorkspaceProvider) {
    this.providers.set(provider.name, provider)
  }

  get(name: string): WorkspaceProvider {
    const provider = this.providers.get(name)
    if (!provider) throw new Error(`Provider ${name} not found`)
    return provider
  }

  list(): string[] {
    return Array.from(this.providers.keys())
  }
}
```

### 3.5 Provider Selection
**Schema change**: Add `provider` column to `workspace_runtimes` table

```typescript
workspace_runtimes {
  // ... existing columns
  provider: text().default('fly').notNull()  // 'fly' | 'kubernetes' | 'docker'
  provider_config: jsonb()  // provider-specific metadata
}
```

**UI**: `src/front/dialogs/CreateWorkspace.jsx`
```typescript
// Dropdown to select provider when creating workspace
<Select>
  <SelectItem value="fly">Fly.io (Automatic)</SelectItem>
  <SelectItem value="kubernetes">Kubernetes (Self-Hosted)</SelectItem>
  <SelectItem value="docker">Docker (Local)</SelectItem>
</Select>
```

### 3.6 Provider Configuration
**File**: `src/server/config.ts`

```typescript
interface ProviderConfig {
  fly?: {
    token: string
    organization: string
  }
  kubernetes?: {
    kubeconfig: string
    namespace: string
  }
  docker?: {
    host: string
    tls?: { ca: string, cert: string, key: string }
  }
}

export function loadProviderConfig(): ProviderConfig {
  return {
    fly: process.env.FLY_API_TOKEN ? {
      token: process.env.FLY_API_TOKEN,
      organization: process.env.FLY_ORG || 'personal'
    } : undefined,

    kubernetes: process.env.KUBECONFIG ? {
      kubeconfig: process.env.KUBECONFIG,
      namespace: process.env.K8S_NAMESPACE || 'boring-workspaces'
    } : undefined
  }
}
```

**Success Criteria**:
- [ ] Provider abstraction interface defined
- [ ] Fly.io provider refactored to interface
- [ ] Kubernetes provider implemented
- [ ] Provider selection in workspace creation UI
- [ ] Workspaces run on both Fly.io and K8s

---

## Phase 4: Enterprise Security & Monitoring (4-5 weeks)

**Goal**: Audit logs, network policies, metrics, and compliance features

### 4.1 Audit Log Schema
**File**: `src/server/db/schema.ts`

```typescript
audit_logs (
  id uuid primary key,
  org_id uuid not null,
  actor_id uuid not null,  // user who performed action
  action text not null,  // 'workspace.create', 'member.add', 'file.read'
  resource_type text,  // 'workspace', 'organization', 'file'
  resource_id text,
  metadata jsonb,  // action-specific details
  ip_address text,
  user_agent text,
  created_at timestamp not null
)

CREATE INDEX idx_audit_logs_org_id ON audit_logs(org_id)
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at DESC)
CREATE INDEX idx_audit_logs_action ON audit_logs(action)
```

### 4.2 Audit Service
**New file**: `src/server/services/auditService.ts`

```typescript
interface AuditService {
  log(event: AuditEvent): Promise<void>
  query(orgId: string, filters: AuditFilters): Promise<AuditLog[]>
  export(orgId: string, format: 'json' | 'csv'): Promise<string>
}

interface AuditEvent {
  orgId: string
  actorId: string
  action: string
  resourceType?: string
  resourceId?: string
  metadata?: Record<string, unknown>
  ipAddress?: string
  userAgent?: string
}

// Usage in workspace creation
await auditService.log({
  orgId: workspace.orgId,
  actorId: userId,
  action: 'workspace.create',
  resourceType: 'workspace',
  resourceId: workspace.id,
  metadata: { name: workspace.name, template: templateId }
})
```

### 4.3 Audit Middleware
**File**: `src/server/middleware/auditMiddleware.ts`

```typescript
export function auditMiddleware(config: { actions: string[] }) {
  return async (req, reply) => {
    const user = req.user  // from auth middleware
    const action = getActionFromRoute(req.method, req.url)

    if (config.actions.includes(action)) {
      await auditService.log({
        orgId: user.orgId,
        actorId: user.id,
        action,
        ipAddress: req.ip,
        userAgent: req.headers['user-agent']
      })
    }
  }
}

// Apply to sensitive routes
app.register(auditMiddleware, {
  actions: [
    'workspace.create', 'workspace.delete',
    'member.add', 'member.remove',
    'settings.update'
  ]
})
```

### 4.4 Metrics Collection
**New file**: `src/server/services/metricsService.ts`

```typescript
interface MetricsService {
  recordWorkspaceMetrics(workspaceId: string): Promise<void>
  getOrgMetrics(orgId: string, range: TimeRange): Promise<OrgMetrics>
  getWorkspaceMetrics(workspaceId: string, range: TimeRange): Promise<WorkspaceMetrics>
}

interface WorkspaceMetrics {
  cpu: { avg: number, max: number, p95: number }
  memory: { avg: number, max: number, p95: number }
  disk: { used: number, total: number }
  network: { ingress: number, egress: number }
  uptime: number  // seconds
}

// Cron job: every minute
async function collectWorkspaceMetrics() {
  const activeWorkspaces = await db.select()
    .from(workspaceRuntimes)
    .where(eq(workspaceRuntimes.state, 'ready'))

  for (const ws of activeWorkspaces) {
    const provider = providerRegistry.get(ws.provider)
    const metrics = await provider.getMetrics(ws.workspaceId)

    await db.insert(workspaceMetricsSnapshots).values({
      workspaceId: ws.workspaceId,
      cpu: metrics.cpu,
      memory: metrics.memory,
      disk: metrics.disk,
      timestamp: new Date()
    })
  }
}
```

### 4.5 Metrics Dashboard
**New files**:
- `src/front/pages/OrgMetrics.jsx` - Org-wide metrics
- `src/front/components/MetricsChart.jsx` - Time-series visualization (use recharts)

**Features**:
- CPU/RAM usage over time (line chart)
- Workspace count and distribution (pie chart)
- Cost estimation (usage × unit price)
- Top 10 resource-consuming workspaces

### 4.6 Network Policies (Kubernetes only)
**File**: `src/server/provisioning/providers/kubernetes.ts`

```typescript
async applyNetworkPolicy(workspaceId: string, policy: NetworkPolicy) {
  const namespace = `workspace-${workspaceId}`

  await this.k8sNetworkingApi.createNamespacedNetworkPolicy(namespace, {
    metadata: { name: 'workspace-policy' },
    spec: {
      podSelector: { matchLabels: { app: 'workspace' } },
      policyTypes: ['Ingress', 'Egress'],

      ingress: policy.allowedIngressCidrs.map(cidr => ({
        from: [{ ipBlock: { cidr } }]
      })),

      egress: policy.allowedEgressCidrs.map(cidr => ({
        to: [{ ipBlock: { cidr } }]
      }))
    }
  })
}
```

### 4.7 Compliance Features
**New file**: `src/server/services/complianceService.ts`

```typescript
interface ComplianceService {
  // Data retention
  purgeOldAuditLogs(olderThanDays: number): Promise<number>

  // Data export (GDPR right to data portability)
  exportUserData(userId: string): Promise<UserDataExport>

  // Data deletion (GDPR right to erasure)
  deleteUserData(userId: string): Promise<void>

  // Access reports
  generateAccessReport(orgId: string, userId: string): Promise<AccessReport>
}

interface UserDataExport {
  user: UserProfile
  workspaces: Workspace[]
  organizations: Organization[]
  auditLogs: AuditLog[]
  settings: UserSettings
}
```

**Success Criteria**:
- [ ] Audit logs for all workspace/org operations
- [ ] Metrics collection (1min granularity)
- [ ] Org metrics dashboard with charts
- [ ] Network policies (K8s only)
- [ ] GDPR compliance endpoints (export, delete)

---

## Phase 5: IDE Integration (4-5 weeks)

**Goal**: VS Code Remote, SSH access, and CLI client for remote workspace management

### 5.1 SSH Access
**New file**: `src/server/services/sshService.ts`

```typescript
interface SSHService {
  createSSHKey(userId: string, publicKey: string): Promise<SSHKey>
  listSSHKeys(userId: string): Promise<SSHKey[]>
  revokeSSHKey(keyId: string): Promise<void>
  getSSHConfig(workspaceId: string): Promise<SSHConfig>
}

interface SSHConfig {
  host: string
  port: number
  user: string
  command: string  // `ssh -p ${port} ${user}@${host}`
}
```

**Provider integration**: Add `getSSHEndpoint()` to `WorkspaceProvider` interface

```typescript
// Fly.io: use fly proxy
async getSSHEndpoint(workspaceId: string): Promise<SSHConfig> {
  return {
    host: 'fly.io',
    port: 22,
    user: workspaceId,
    command: `flyctl ssh console -a ${workspaceId}`
  }
}

// Kubernetes: expose NodePort service
async getSSHEndpoint(workspaceId: string): Promise<SSHConfig> {
  const service = await this.k8sApi.createNamespacedService(namespace, {
    spec: {
      type: 'NodePort',
      selector: { app: 'workspace' },
      ports: [{ port: 22, nodePort: 30000 + hash(workspaceId) }]
    }
  })

  return {
    host: process.env.K8S_NODE_IP,
    port: service.spec.ports[0].nodePort,
    user: 'workspace'
  }
}
```

### 5.2 VS Code Remote Integration
**New file**: `deploy/vscode-remote/README.md`

Document:
1. Install "Remote - SSH" extension
2. Get SSH config from boring-ui UI
3. Add to `~/.ssh/config`:
```
Host boring-ws-{workspace-id}
  HostName {host}
  Port {port}
  User {user}
  IdentityFile ~/.ssh/boring-ui-key
```
4. Connect via "Remote-SSH: Connect to Host"

**Future**: Custom VS Code extension to automate this flow

### 5.3 CLI Client
**New package**: `packages/boring-ui-cli/`

```bash
npm init -y
npm install commander chalk inquirer node-fetch
```

**File**: `packages/boring-ui-cli/src/index.ts`

```typescript
#!/usr/bin/env node
import { Command } from 'commander'
import chalk from 'chalk'

const program = new Command()

program
  .name('boring-ui')
  .description('Boring UI CLI - manage workspaces from your terminal')
  .version('1.0.0')

program
  .command('login')
  .description('Authenticate with boring-ui')
  .action(async () => {
    const email = await input({ message: 'Email:' })
    const password = await input({ message: 'Password:', type: 'password' })

    const res = await fetch(`${config.apiUrl}/auth/sign-in/email`, {
      method: 'POST',
      body: JSON.stringify({ email, password })
    })

    const { token } = await res.json()
    await saveToken(token)
    console.log(chalk.green('✓ Logged in successfully'))
  })

program
  .command('list')
  .description('List your workspaces')
  .action(async () => {
    const workspaces = await apiClient.listWorkspaces()
    console.table(workspaces.map(w => ({
      ID: w.id.slice(0, 8),
      Name: w.name,
      Status: w.status,
      Created: formatDate(w.createdAt)
    })))
  })

program
  .command('create <name>')
  .option('-t, --template <id>', 'Template ID')
  .description('Create a new workspace')
  .action(async (name, options) => {
    const workspace = await apiClient.createWorkspace({
      name,
      templateId: options.template
    })
    console.log(chalk.green(`✓ Workspace created: ${workspace.id}`))
  })

program
  .command('ssh <workspace-id>')
  .description('SSH into a workspace')
  .action(async (workspaceId) => {
    const config = await apiClient.getSSHConfig(workspaceId)
    execSync(config.command, { stdio: 'inherit' })
  })

program.parse()
```

**Publish**: `npm publish` → `npx boring-ui-cli`

**Success Criteria**:
- [ ] SSH key upload + SSH access to workspaces
- [ ] VS Code Remote connection documented
- [ ] CLI tool published (`boring-ui-cli`)
- [ ] CLI supports login, list, create, ssh commands

---

## Deployment & Operations

### Terraform/IaC (Phase 3+)
**New directory**: `deploy/terraform/`

```hcl
# deploy/terraform/fly.tf
resource "fly_app" "boring_ui" {
  name = "boring-ui-${var.environment}"
  org  = var.fly_org
}

resource "fly_machine" "web" {
  app    = fly_app.boring_ui.name
  region = "cdg"

  services = [{
    ports = [{
      port     = 80
      handlers = ["http"]
    }, {
      port     = 443
      handlers = ["tls", "http"]
    }]

    internal_port = 8000
  }]

  env = {
    NODE_ENV = var.environment
  }
}

# deploy/terraform/kubernetes.tf
resource "kubernetes_namespace" "boring_workspaces" {
  metadata {
    name = "boring-workspaces"
  }
}

resource "kubernetes_resource_quota" "workspace_quota" {
  metadata {
    name      = "workspace-quota"
    namespace = kubernetes_namespace.boring_workspaces.metadata[0].name
  }

  spec {
    hard = {
      "requests.cpu"    = "100"
      "requests.memory" = "200Gi"
      "pods"            = "50"
    }
  }
}
```

### High Availability (Phase 4+)
**Changes**:
- Run 3+ backend instances behind load balancer
- Add Redis for session sharing (`@fastify/redis`)
- Postgres read replicas for query scaling
- Health checks: `/health/live` and `/health/ready`

**File**: `src/server/http/healthRoutes.ts`

```typescript
app.get('/health/live', async () => {
  return { status: 'ok', timestamp: Date.now() }
})

app.get('/health/ready', async () => {
  // Check DB connection
  await db.execute(sql`SELECT 1`)

  // Check provider availability
  for (const provider of providerRegistry.list()) {
    await providerRegistry.get(provider).healthCheck()
  }

  return { status: 'ready' }
})
```

### Backup & Disaster Recovery
**Neon Postgres**: Automatic point-in-time recovery (14-day retention)

**Workspace data**:
- Fly.io: Volume snapshots (manual or scheduled)
- K8s: PVC snapshots via VolumeSnapshot CRD

**File**: `src/server/jobs/backupJob.ts`

```typescript
// Daily backup job
cron.schedule('0 2 * * *', async () => {
  const workspaces = await db.select().from(workspaceRuntimes)

  for (const ws of workspaces) {
    const provider = providerRegistry.get(ws.provider)
    await provider.createSnapshot(ws.workspaceId)
    await auditService.log({
      action: 'workspace.backup',
      resourceId: ws.workspaceId
    })
  }
})
```

---

## Success Metrics

### Phase 1 (Multi-Tenancy)
- [ ] 10+ organizations created
- [ ] Quota enforcement prevents over-provisioning
- [ ] Admin can manage org members via UI

### Phase 2 (Templates)
- [ ] 5+ templates available (Node, Python, Go, Rust, Java)
- [ ] 80%+ of workspaces created from templates
- [ ] Auto-shutdown reduces idle resource waste by 60%+

### Phase 3 (Infrastructure)
- [ ] Workspaces running on 2+ providers (Fly + K8s)
- [ ] Provider abstraction supports custom providers
- [ ] <5min to add new provider implementation

### Phase 4 (Security)
- [ ] 100% of privileged actions logged
- [ ] Metrics dashboard shows real-time usage
- [ ] GDPR export completes in <10s for typical user

### Phase 5 (IDE Integration)
- [ ] SSH access works on all providers
- [ ] VS Code Remote connection documented + tested
- [ ] CLI supports core workflows (login, create, ssh)

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Provider API changes break abstraction | High | Version lock provider SDKs, add integration tests |
| Quota enforcement has race conditions | Medium | Use DB transactions, add pessimistic locking |
| Metrics collection impacts performance | Medium | Async writes, batch inserts, separate read replica |
| Migration breaks existing workspaces | High | Staged rollout, feature flags, rollback plan |
| SSH key management security | High | Use ed25519 keys only, rotate every 90 days, audit key usage |

---

## Next Steps

1. **Review & prioritize**: Get stakeholder feedback on phase order
2. **Proof-of-concept**: Build Phase 1 (Multi-Tenancy) in 2-week sprint
3. **User testing**: Validate quota UX with 3-5 early customers
4. **Phase 2+**: Iterate based on PoC learnings

**Questions for review**:
- Should we support Docker provider in Phase 3? (local dev use case)
- Pricing model: per-workspace, per-resource-hour, or flat org rate?
- Self-hosted deployment: provide Helm chart or Docker Compose?

---

## Appendix: Competitive Feature Matrix

| Feature | Coder | boring-ui (current) | boring-ui (post-plan) |
|---------|-------|---------------------|----------------------|
| Multi-tenancy | ✅ | ❌ | ✅ (Phase 1) |
| Workspace templates | ✅ | ❌ | ✅ (Phase 2) |
| Auto-shutdown | ✅ | ❌ | ✅ (Phase 2) |
| Kubernetes support | ✅ | ❌ | ✅ (Phase 3) |
| Multi-cloud | ✅ | ❌ (Fly only) | ✅ (Phase 3) |
| Audit logs | ✅ | ❌ | ✅ (Phase 4) |
| Metrics dashboard | ✅ | ❌ | ✅ (Phase 4) |
| VS Code Remote | ✅ | ❌ | ✅ (Phase 5) |
| SSH access | ✅ | ❌ | ✅ (Phase 5) |
| CLI client | ✅ | ❌ | ✅ (Phase 5) |
| Real-time collab | ❌ | ❌ | ❌ (Out of scope) |
| RBAC | ✅ | 🟡 (basic) | ✅ (Phase 1) |
| Self-hosted | ✅ | ❌ | ✅ (Phase 3) |

**Legend**: ✅ Supported | 🟡 Partial | ❌ Not supported
