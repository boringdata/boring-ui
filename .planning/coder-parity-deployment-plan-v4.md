# Coder-Parity Deployment Plan (v4 - Coder-Inspired Architecture)

**Goal**: Adopt Coder's proven architecture - stateless control plane + per-workspace pods

**Status**: Draft (v4 - based on [Coder's Kubernetes template](https://github.com/coder/coder/blob/main/examples/templates/kubernetes/main.tf))
**Created**: 2026-03-28
**Timeline**: 10-13 weeks (2.5-3 months)

---

## Architecture Shift

### ❌ Current (v3 plan - Shared Host Model)
```
┌─────────────────────────────────────┐
│  boring-ui Pod                       │
│  ├── API server                      │
│  ├── /workspaces/abc (user 1)       │
│  ├── /workspaces/def (user 2)       │
│  └── /workspaces/xyz (user 3)       │
└─────────────────────────────────────┘
Problems: Noisy neighbor, SPOF, shared resources
```

### ✅ New (v4 - Coder Model)
```
┌─────────────────────────────────────┐
│  boring-ui-control (stateless)       │
│  - API + workspace lifecycle mgmt    │
│  - Can scale: replicas 3+           │
│  - No workspaces inside             │
└─────────────────────────────────────┘
         ↓ provisions
┌─────────────────────────────────────┐
│  workspace-abc-xxxx (Pod)           │
│  - User A's files (PVC: 10GB RWO)   │
│  - boring-agent connects to control │
│  - Resource limits: 2 CPU, 4GB RAM  │
└─────────────────────────────────────┘
┌─────────────────────────────────────┐
│  workspace-def-yyyy (Pod)           │
│  - User B's files (PVC: 10GB RWO)   │
│  - boring-agent connects to control │
│  - Resource limits: 2 CPU, 4GB RAM  │
└─────────────────────────────────────┘
```

**Benefits**:
- ✅ **No noisy neighbor** - K8s resource limits per pod
- ✅ **No SPOF** - one workspace crash ≠ others crash
- ✅ **Smaller security blast radius** - bwrap escape = 1 workspace
- ✅ **Stateful sessions work** - workspace always on same pod
- ✅ **Simple storage** - RWO (ReadWriteOnce), no RWX needed
- ✅ **Control plane scales** - stateless API can do replicas: 3+

---

## Coder's Architecture (What We're Copying)

From [Coder's Kubernetes template](https://github.com/coder/coder/tree/main/examples/templates/kubernetes):

### Resources per Workspace
```hcl
# 1. PersistentVolumeClaim
resource "kubernetes_persistent_volume_claim" "home" {
  metadata {
    name = "coder-${data.coder_workspace.me.id}-home"
  }
  spec {
    access_modes = ["ReadWriteOnce"]  # RWO, not RWX!
    resources {
      requests = {
        storage = "10Gi"
      }
    }
  }
}

# 2. Deployment (1 replica)
resource "kubernetes_deployment" "main" {
  metadata {
    name = "coder-${data.coder_workspace.me.id}"
  }
  spec {
    replicas = 1
    template {
      spec {
        container {
          image = "codercom/enterprise-base:ubuntu"
          command = ["sh", "-c", coder_agent.main.init_script]

          env {
            name = "CODER_AGENT_TOKEN"
            value = coder_agent.main.token  # Agent auth
          }

          resources {
            requests = { cpu = "250m", memory = "512Mi" }
            limits   = { cpu = "2", memory = "4Gi" }
          }

          volume_mount {
            name = "home"
            mount_path = "/home/coder"
          }
        }

        volume {
          name = "home"
          persistent_volume_claim {
            claim_name = kubernetes_persistent_volume_claim.home.metadata.0.name
          }
        }
      }
    }
  }
}

# 3. Coder Agent (runs inside workspace)
resource "coder_agent" "main" {
  os   = "linux"
  arch = "amd64"

  # Agent reports metrics back to control plane
  startup_script = <<-EOT
    #!/bin/bash
    # Install tools, setup environment
    curl -fsSL https://code-server.dev/install.sh | sh
  EOT
}
```

**Key Pattern**: Control plane creates K8s resources, agent inside workspace connects back.

---

## Phase 1: Split Control Plane from Workspaces (4-5 weeks)

**Goal**: Separate stateless API from workspace execution

### 1.1 Control Plane Service
**New package**: `src/control/` (or refactor existing `src/server/`)

```typescript
// src/control/app.ts
export function createControlPlaneApp(config: ControlPlaneConfig) {
  const app = Fastify()

  // NO workspace directories here!
  // Just API + workspace lifecycle management

  app.register(authRoutes)
  app.register(workspaceRoutes)  // CRUD + provision/deprovision
  app.register(proxyRoutes)      // Proxy requests to workspace pods

  return app
}
```

**Responsibilities**:
- User auth (Neon Auth)
- Workspace CRUD (create, list, delete)
- Provisioning orchestration (create K8s resources)
- Proxy WebSocket/HTTP to workspace pods
- Metrics aggregation

**Does NOT**:
- Run user code
- Store workspace files (those are in workspace pods)
- Execute git/file operations directly

### 1.2 Workspace Image
**New Dockerfile**: `deploy/workspace/Dockerfile`

```dockerfile
FROM ubuntu:22.04

# Install basics
RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    bubblewrap \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (or other runtimes based on template)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs

# Create workspace user
RUN useradd -m -s /bin/bash -u 1000 workspace
USER workspace
WORKDIR /home/workspace

# Install boring-agent
COPY boring-agent /usr/local/bin/boring-agent
RUN chmod +x /usr/local/bin/boring-agent

# Agent connects back to control plane
ENTRYPOINT ["/usr/local/bin/boring-agent"]
```

### 1.3 Workspace Agent
**New package**: `src/agent/` (runs inside workspace pod)

```typescript
// src/agent/main.ts
import WebSocket from 'ws'
import { spawn } from 'child_process'
import { execInSandbox } from './bwrap.js'

interface AgentConfig {
  controlPlaneUrl: string  // ws://boring-ui-control.svc.cluster.local
  workspaceId: string
  agentToken: string       // Auth token from control plane
}

export class WorkspaceAgent {
  private ws: WebSocket
  private config: AgentConfig

  constructor(config: AgentConfig) {
    this.config = config
    this.connect()
  }

  private connect() {
    this.ws = new WebSocket(
      `${this.config.controlPlaneUrl}/agent/${this.config.workspaceId}`,
      { headers: { 'Authorization': `Bearer ${this.config.agentToken}` } }
    )

    this.ws.on('open', () => {
      console.log('Agent connected to control plane')
      this.sendMetrics()  // Start reporting CPU/RAM/disk
    })

    this.ws.on('message', (data) => {
      const msg = JSON.parse(data.toString())
      this.handleCommand(msg)
    })
  }

  private async handleCommand(msg: any) {
    switch (msg.type) {
      case 'exec':
        // Execute command in bwrap sandbox
        const result = await execInSandbox('/home/workspace', msg.command)
        this.ws.send(JSON.stringify({ type: 'exec_result', id: msg.id, result }))
        break

      case 'file.read':
        // Read file and send back
        const content = await fs.readFile(msg.path, 'utf-8')
        this.ws.send(JSON.stringify({ type: 'file.content', id: msg.id, content }))
        break

      // ... other commands
    }
  }

  private sendMetrics() {
    setInterval(async () => {
      const metrics = await this.collectMetrics()
      this.ws.send(JSON.stringify({ type: 'metrics', metrics }))
    }, 30000)  // Every 30s, like Coder
  }

  private async collectMetrics() {
    // Collect CPU, RAM, disk usage
    return {
      cpu: process.cpuUsage(),
      memory: process.memoryUsage(),
      disk: await getDiskUsage('/home/workspace')
    }
  }
}

// Start agent
const config: AgentConfig = {
  controlPlaneUrl: process.env.CONTROL_PLANE_URL!,
  workspaceId: process.env.WORKSPACE_ID!,
  agentToken: process.env.AGENT_TOKEN!
}

new WorkspaceAgent(config)
```

### 1.4 Kubernetes Provisioner
**New file**: `src/control/services/k8sProvisioner.ts`

```typescript
import * as k8s from '@kubernetes/client-node'
import { randomBytes } from 'crypto'

export interface WorkspaceSpec {
  workspaceId: string
  userId: string
  cpu: number      // e.g., 2
  memory: number   // e.g., 4096 (MB)
  storage: number  // e.g., 10 (GB)
  image?: string   // e.g., 'boring-ui-workspace:latest'
}

export class K8sProvisioner {
  private k8sApi: k8s.CoreV1Api
  private appsApi: k8s.AppsV1Api
  private namespace = 'boring-workspaces'

  constructor() {
    const kc = new k8s.KubeConfig()
    kc.loadFromDefault()
    this.k8sApi = kc.makeApiClient(k8s.CoreV1Api)
    this.appsApi = kc.makeApiClient(k8s.AppsV1Api)
  }

  async provisionWorkspace(spec: WorkspaceSpec): Promise<void> {
    const { workspaceId, cpu, memory, storage } = spec

    // 1. Create PVC for workspace storage
    await this.k8sApi.createNamespacedPersistentVolumeClaim(this.namespace, {
      metadata: {
        name: `workspace-${workspaceId}-pvc`,
        labels: {
          'boring.app/workspace-id': workspaceId,
          'boring.app/user-id': spec.userId
        }
      },
      spec: {
        accessModes: ['ReadWriteOnce'],  // RWO, not RWX!
        resources: {
          requests: { storage: `${storage}Gi` }
        }
      }
    })

    // 2. Generate agent token
    const agentToken = randomBytes(32).toString('hex')
    await this.storeAgentToken(workspaceId, agentToken)

    // 3. Create Deployment (like Coder does)
    await this.appsApi.createNamespacedDeployment(this.namespace, {
      metadata: {
        name: `workspace-${workspaceId}`,
        labels: {
          'boring.app/workspace-id': workspaceId,
          'boring.app/user-id': spec.userId
        }
      },
      spec: {
        replicas: 1,  // Always 1 replica per workspace
        strategy: { type: 'Recreate' },  // Like Coder
        selector: {
          matchLabels: { 'boring.app/workspace-id': workspaceId }
        },
        template: {
          metadata: {
            labels: { 'boring.app/workspace-id': workspaceId }
          },
          spec: {
            securityContext: {
              runAsUser: 1000,
              runAsNonRoot: true,
              fsGroup: 1000
            },
            containers: [{
              name: 'workspace',
              image: spec.image || 'boring-ui-workspace:latest',
              env: [
                { name: 'WORKSPACE_ID', value: workspaceId },
                { name: 'AGENT_TOKEN', value: agentToken },
                {
                  name: 'CONTROL_PLANE_URL',
                  value: 'ws://boring-ui-control.boring-ui.svc.cluster.local'
                }
              ],
              resources: {
                requests: {
                  cpu: `${cpu * 0.25}`,  // Request 25% of limit
                  memory: `${memory * 0.5}Mi`
                },
                limits: {
                  cpu: `${cpu}`,
                  memory: `${memory}Mi`
                }
              },
              volumeMounts: [{
                name: 'workspace-storage',
                mountPath: '/home/workspace'
              }]
            }],
            volumes: [{
              name: 'workspace-storage',
              persistentVolumeClaim: {
                claimName: `workspace-${workspaceId}-pvc`
              }
            }]
          }
        }
      }
    })

    // 4. Create Service for network access
    await this.k8sApi.createNamespacedService(this.namespace, {
      metadata: {
        name: `workspace-${workspaceId}`,
        labels: { 'boring.app/workspace-id': workspaceId }
      },
      spec: {
        selector: { 'boring.app/workspace-id': workspaceId },
        ports: [{ port: 8080, targetPort: 8080, name: 'agent' }],
        type: 'ClusterIP'
      }
    })
  }

  async deprovisionWorkspace(workspaceId: string): Promise<void> {
    // Delete Deployment
    await this.appsApi.deleteNamespacedDeployment(
      `workspace-${workspaceId}`,
      this.namespace
    )

    // Delete Service
    await this.k8sApi.deleteNamespacedService(
      `workspace-${workspaceId}`,
      this.namespace
    )

    // Delete PVC (after grace period)
    // Note: Like Coder, we might want to keep PVCs for a while
    await this.k8sApi.deleteNamespacedPersistentVolumeClaim(
      `workspace-${workspaceId}-pvc`,
      this.namespace
    )
  }

  async getWorkspaceStatus(workspaceId: string) {
    const deployment = await this.appsApi.readNamespacedDeployment(
      `workspace-${workspaceId}`,
      this.namespace
    )

    return {
      ready: deployment.body.status.readyReplicas === 1,
      replicas: deployment.body.status.replicas,
      conditions: deployment.body.status.conditions
    }
  }
}
```

### 1.5 Control Plane Proxy
**New file**: `src/control/services/workspaceProxy.ts`

Users connect to control plane, which proxies to workspace pods:

```typescript
export class WorkspaceProxy {
  // User → Control Plane → Workspace Pod
  async proxyWebSocket(workspaceId: string, userWs: WebSocket) {
    // Find workspace pod
    const service = `workspace-${workspaceId}.boring-workspaces.svc.cluster.local`

    // Connect to workspace agent
    const agentWs = new WebSocket(`ws://${service}:8080/agent`)

    // Bidirectional proxy
    userWs.on('message', (data) => agentWs.send(data))
    agentWs.on('message', (data) => userWs.send(data))
  }
}
```

### 1.6 Database Schema Updates
**Migrations**:

```sql
-- Store agent tokens
CREATE TABLE workspace_agents (
  workspace_id UUID PRIMARY KEY REFERENCES workspaces(id),
  agent_token TEXT NOT NULL,
  connected_at TIMESTAMP,
  last_heartbeat TIMESTAMP,
  metrics JSONB
);

-- Track K8s resources
CREATE TABLE workspace_k8s_resources (
  workspace_id UUID PRIMARY KEY REFERENCES workspaces(id),
  deployment_name TEXT NOT NULL,
  service_name TEXT NOT NULL,
  pvc_name TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);
```

### Success Criteria
- [ ] Control plane runs separately from workspaces
- [ ] Workspace pod provisions on K8s
- [ ] Agent connects back to control plane via WebSocket
- [ ] User can connect through control plane proxy
- [ ] File operations routed through agent
- [ ] Pod auto-restarts if agent crashes

---

## Phase 2: Resource Management & Templates (3-4 weeks)

**Goal**: Workspace templates (like Coder) + per-user quotas

### 2.1 Workspace Templates
**Schema**:
```typescript
export const workspaceTemplates = pgTable('workspace_templates', {
  id: uuid().defaultRandom().primaryKey(),
  name: text().notNull(),
  description: text(),
  image: text().notNull(),           // e.g., 'boring-ui-workspace-node:20'
  initScript: text('init_script'),   // Bash script to run on first start
  defaultCpu: integer('default_cpu').default(2),
  defaultMemory: integer('default_memory').default(4096),
  defaultStorage: integer('default_storage').default(10),
  tags: jsonb().default([]),
  isPublic: boolean('is_public').default(true)
})
```

**Built-in templates** (like Coder's examples):
```typescript
const templates = [
  {
    name: 'Blank Ubuntu',
    image: 'boring-ui-workspace-base:latest',
    initScript: null
  },
  {
    name: 'Node.js 20',
    image: 'boring-ui-workspace-node:20',
    initScript: `
#!/bin/bash
npm install -g pnpm typescript
git config --global init.defaultBranch main
    `.trim()
  },
  {
    name: 'Python 3.11',
    image: 'boring-ui-workspace-python:3.11',
    initScript: `
#!/bin/bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
    `.trim()
  }
]
```

### 2.2 Per-User Quotas
(Same as v3 plan Phase 2.1 - enforce at workspace creation time)

### Success Criteria
- [ ] 3+ workspace templates available
- [ ] Template selection in UI
- [ ] Init scripts run on first workspace start
- [ ] Quotas enforced (max 5 workspaces, 50GB total)

---

## Phase 3: Security & Monitoring (3-4 weeks)

**Goal**: Audit logs, per-workspace metrics, GDPR compliance

### 3.1 Per-Workspace Metrics
Agent reports metrics back to control plane (like Coder does):

```typescript
// Agent sends every 30s
{
  type: 'metrics',
  cpu: { usage: 45, limit: 2000 },       // millicores
  memory: { usage: 1024, limit: 4096 },  // MB
  disk: { used: 2.5, total: 10 }         // GB
}
```

Control plane stores in time-series DB (or Postgres JSONB):

```sql
CREATE TABLE workspace_metrics (
  workspace_id UUID NOT NULL,
  timestamp TIMESTAMP NOT NULL,
  cpu_usage INT,
  memory_usage INT,
  disk_usage FLOAT,
  PRIMARY KEY (workspace_id, timestamp)
);

-- Retention: Keep last 7 days
CREATE INDEX idx_metrics_timestamp ON workspace_metrics(timestamp DESC);
```

### 3.2 Audit Logs
(Same as v3 plan Phase 3.1)

### 3.3 Admin Dashboard
**New page**: `src/front/pages/Admin.jsx`

Shows:
- Total workspaces, active users
- Resource usage (CPU/RAM/disk across all workspaces)
- Per-user quota usage
- Audit log viewer

### Success Criteria
- [ ] Per-workspace metrics displayed in UI
- [ ] Admin can view all workspaces + resource usage
- [ ] Audit logs queryable
- [ ] GDPR export/delete works

---

## Phase 4: Operations & Scaling (2-3 weeks)

**Goal**: HA control plane, graceful shutdown, backup/restore

### 4.1 HA Control Plane
Now that control plane is stateless, we can scale:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: boring-ui-control
spec:
  replicas: 3  # Now safe! No workspaces inside
  template:
    spec:
      containers:
      - name: control
        image: boring-ui-control:latest
        resources:
          limits:
            cpu: "1"
            memory: 1Gi
```

**Session affinity**: Not needed for API, but WebSocket proxy needs sticky sessions:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: boring-ui-control
spec:
  sessionAffinity: ClientIP
  sessionAffinityConfig:
    clientIP:
      timeoutSeconds: 3600
```

### 4.2 Graceful Shutdown
**PreStop hook** in workspace pods:

```yaml
containers:
- name: workspace
  lifecycle:
    preStop:
      exec:
        command: ["/bin/sh", "-c", "sleep 30"]
```

Agent warns users via WebSocket before shutdown.

### 4.3 Backup & Restore
- **Control plane**: Stateless, no backup needed (just deploy)
- **Database**: Neon automatic backups
- **Workspaces**: PVC snapshots via VolumeSnapshot CRD

### Success Criteria
- [ ] 3-replica control plane running
- [ ] Control plane can be redeployed without affecting workspaces
- [ ] Workspace pods gracefully shutdown (warn users)
- [ ] PVC snapshot/restore tested

---

## Deployment Guide

### Prerequisites
- Kubernetes 1.28+
- PostgreSQL (Neon recommended)
- Container registry (ghcr.io or private)

### 1. Build Images

```bash
# Control plane
docker build -t boring-ui-control:latest -f deploy/control/Dockerfile .
docker push ghcr.io/boring-data/boring-ui-control:latest

# Workspace base
docker build -t boring-ui-workspace:latest -f deploy/workspace/Dockerfile .
docker push ghcr.io/boring-data/boring-ui-workspace:latest
```

### 2. Create Namespaces

```bash
kubectl create namespace boring-ui
kubectl create namespace boring-workspaces
```

### 3. Create Secrets

```bash
kubectl create secret generic boring-ui-secrets \
  --namespace boring-ui \
  --from-literal=database-url='postgresql://...' \
  --from-literal=session-secret='...' \
  --from-literal=anthropic-api-key='...'
```

### 4. Deploy Control Plane

```bash
kubectl apply -f deploy/k8s/control-plane.yaml
```

### 5. Verify

```bash
kubectl get pods -n boring-ui
kubectl get svc -n boring-ui boring-ui-control
```

Visit `http://<LOAD_BALANCER_IP>`

---

## Comparison to Coder

| Aspect | Coder | boring-ui (v4) | Notes |
|--------|-------|----------------|-------|
| **Control plane** | coderd (stateless) | boring-ui-control | ✅ Same pattern |
| **Workspace** | K8s Pod + PVC | K8s Deployment + PVC | ✅ Same pattern |
| **Agent** | Coder agent | boring-agent | ✅ Same pattern |
| **Provisioning** | Terraform | Kubernetes client lib | Simpler (no Terraform layer) |
| **Connection** | WireGuard tunnel | WebSocket proxy | Simpler (no VPN) |
| **Storage** | RWO PVC per workspace | RWO PVC per workspace | ✅ Same |
| **Resource limits** | K8s limits | K8s limits | ✅ Same |
| **Templates** | Terraform templates | Image + init script | Simpler (no Terraform) |
| **HA** | Multi-replica coderd | Multi-replica control | ✅ Same |

**We're copying the good parts**, skipping Terraform complexity (at least initially).

---

## Timeline

```
Week 1-2:   Control plane refactor (split from workspaces)
Week 3-4:   Workspace agent + K8s provisioner
Week 5:     Control plane → agent proxy
Week 6-7:   Workspace templates
Week 8:     Per-user quotas
Week 9:     Per-workspace metrics
Week 10:    Audit logs + admin dashboard
Week 11:    HA control plane
Week 12-13: Graceful shutdown, backup/restore, testing
```

**Total: 10-13 weeks**

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Agent disconnect handling | High | Reconnect logic + heartbeat monitoring |
| PVC cleanup (orphaned volumes) | Medium | Finalizers + cleanup job after 30 days |
| Control plane → workspace routing | High | Service discovery + DNS-based routing |
| Workspace startup time | Medium | Pre-pull images, optimize init script |
| Cost (many pods vs one pod) | High | Start with small limits, auto-shutdown idle |

---

## Why This is Better Than v3

| Issue (from Gemini) | v3 (Shared Host) | v4 (Coder Model) |
|---------------------|------------------|------------------|
| Noisy neighbor | ❌ bwrap only, no CPU/RAM isolation | ✅ K8s resource limits per pod |
| SPOF | ❌ One pod crash = everyone crashes | ✅ Isolated pods |
| Stateful sessions | ❌ Needs sticky sessions + RWX | ✅ Workspace always same pod |
| Storage | ❌ Requires RWX (complex) | ✅ RWO per pod (simple) |
| Security blast radius | ❌ All workspaces in one pod | ✅ One pod per workspace |
| Scalability | ❌ Vertical only | ✅ Horizontal (add more nodes) |

**v4 fixes ALL of Gemini's concerns** by adopting Coder's proven architecture.

---

## Next Steps

1. **Review this plan** - Confirm we want to adopt Coder's architecture
2. **Phase 1 PoC** (2 weeks):
   - Build control plane + workspace images
   - Provision single workspace on local K8s (minikube)
   - Agent connects back, execute command works
3. **Production deployment** (weeks 3-4)
4. **Phases 2-4** (weeks 5-13)
