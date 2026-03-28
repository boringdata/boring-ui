# Coder-Parity Deployment Plan (v2)

**Goal**: Transform boring-ui into an enterprise-ready, multi-provider development platform comparable to Coder.

**Status**: Draft (Updated 2026-03-28 based on feedback)
**Created**: 2026-03-28
**Target**: Q2-Q3 2026

---

## Executive Summary

boring-ui currently has strong foundations (multi-user workspaces, RBAC, Fly.io provisioning, auth), but lacks enterprise deployment features. This plan addresses critical gaps across 4 phases, prioritizing **infrastructure abstraction** as the key enabler.

**Timeline**: 15-19 weeks total (4-5 months)

**Current State**: Fly.io-only, web-based IDE with basic workspace provisioning
**Target State**: Multi-provider platform with templates, resource quotas, and enterprise security

**Key Priority**: Infrastructure abstraction (support Kubernetes, Docker, multiple clouds) - this unlocks self-hosted and bring-your-own-infrastructure deployments.

---

## Gap Analysis

### ✅ Already Have
- **Multi-user workspaces** with RBAC (owner/editor/viewer)
- **Workspace provisioning** (Fly.io + bwrap sandbox)
- **Neon Auth** + session management
- **File/git/exec operations** via TypeScript backend
- **Workspace invites** & encrypted settings
- **TypeScript backend** (Fastify + Drizzle ORM)

### ❌ Critical Gaps (Priority Order)
1. **Infrastructure** (Priority #1): Locked to Fly.io, no provider abstraction - **blocks self-hosted deployments**
2. **Resource Management**: No quotas, templates, or auto-shutdown policies
3. **Security**: No audit logs, network policies, compliance features
4. **Monitoring**: No metrics, cost tracking, or usage analytics
5. **Operations**: No HA, disaster recovery, or IaC

### 🟡 Out of Scope (for now)
- **Organization/team multi-tenancy**: Workspace abstraction already exists, per-user workspaces sufficient for now
- **IDE integration**: No SSH, VS Code Remote, or CLI - web-only is sufficient
- **Real-time collaboration**: Not needed

---

## Phase 1: Infrastructure Abstraction (5-6 weeks) 🎯 PRIORITY

**Goal**: Support multiple infrastructure providers (Fly.io, Kubernetes, Docker) to enable self-hosted deployments

**Why this is priority #1**: Current Fly.io lock-in blocks:
- Enterprise self-hosted deployments
- Bring-your-own-infrastructure
- Multi-cloud strategies
- Local development with Docker

### 1.1 Provider Abstraction Interface
**New file**: `src/server/provisioning/providers/base.ts`

Define the common interface all providers must implement:

```typescript
export interface WorkspaceProvider {
  name: string  // 'fly' | 'kubernetes' | 'docker'

  // Lifecycle
  create(config: WorkspaceConfig): Promise<WorkspaceRuntime>
  destroy(runtimeId: string): Promise<void>
  start(runtimeId: string): Promise<void>
  stop(runtimeId: string): Promise<void>

  // Status & Metrics
  getStatus(runtimeId: string): Promise<RuntimeStatus>
  getMetrics(runtimeId: string): Promise<ResourceMetrics>

  // Execution
  exec(runtimeId: string, command: string): Promise<ExecResult>

  // Health check
  healthCheck(): Promise<boolean>
}

export interface WorkspaceConfig {
  workspaceId: string
  baseImage: string  // e.g., 'node:20', 'python:3.11'
  cpu: number
  ram: number  // MB
  storage: number  // GB
  region?: string
  env?: Record<string, string>
}

export interface WorkspaceRuntime {
  provider: string
  runtimeId: string  // provider-specific ID
  status: 'pending' | 'provisioning' | 'ready' | 'stopped' | 'error'
  endpoint?: string  // HTTP endpoint if applicable
  metadata: Record<string, unknown>  // provider-specific data
}

export interface RuntimeStatus {
  state: 'running' | 'stopped' | 'error'
  uptime?: number  // seconds
  lastError?: string
}

export interface ResourceMetrics {
  cpu: { current: number, limit: number }  // percentage
  memory: { current: number, limit: number }  // MB
  disk: { used: number, total: number }  // GB
  network?: { ingress: number, egress: number }  // bytes
}
```

### 1.2 Fly.io Provider (refactor existing)
**File**: `src/server/provisioning/providers/fly.ts`

Refactor existing Fly.io provisioning code to implement the interface:

```typescript
import { WorkspaceProvider, WorkspaceConfig, WorkspaceRuntime } from './base.js'

export class FlyProvider implements WorkspaceProvider {
  name = 'fly'
  private apiToken: string
  private flyApi: FlyAPI

  constructor(config: { token: string, org?: string }) {
    this.apiToken = config.token
    this.flyApi = new FlyAPI(config.token)
  }

  async create(config: WorkspaceConfig): Promise<WorkspaceRuntime> {
    // Create Fly.io app (if not exists)
    await this.flyApi.createApp(config.workspaceId)

    // Create machine with bwrap
    const machine = await this.flyApi.createMachine({
      app: config.workspaceId,
      region: config.region || 'cdg',
      config: {
        image: config.baseImage,
        guest: {
          cpus: config.cpu,
          memory_mb: config.ram
        },
        env: config.env,
        mounts: [{
          volume: await this.createVolume(config.workspaceId, config.storage),
          path: '/workspace'
        }]
      }
    })

    return {
      provider: 'fly',
      runtimeId: machine.id,
      status: 'provisioning',
      endpoint: `https://${config.workspaceId}.fly.dev`,
      metadata: { machineId: machine.id, region: machine.region }
    }
  }

  async destroy(runtimeId: string): Promise<void> {
    await this.flyApi.destroyMachine(runtimeId)
  }

  async start(runtimeId: string): Promise<void> {
    await this.flyApi.startMachine(runtimeId)
  }

  async stop(runtimeId: string): Promise<void> {
    await this.flyApi.stopMachine(runtimeId)
  }

  async getStatus(runtimeId: string): Promise<RuntimeStatus> {
    const machine = await this.flyApi.getMachine(runtimeId)
    return {
      state: machine.state === 'started' ? 'running' : 'stopped',
      uptime: machine.instance_id ? Date.now() - new Date(machine.created_at).getTime() : 0
    }
  }

  async getMetrics(runtimeId: string): Promise<ResourceMetrics> {
    const stats = await this.flyApi.getMachineStats(runtimeId)
    return {
      cpu: { current: stats.cpu_usage, limit: 100 },
      memory: { current: stats.mem_usage_mb, limit: stats.mem_limit_mb },
      disk: { used: stats.disk_usage_gb, total: stats.disk_total_gb }
    }
  }

  async exec(runtimeId: string, command: string): Promise<ExecResult> {
    return await this.flyApi.exec(runtimeId, command)
  }

  async healthCheck(): Promise<boolean> {
    try {
      await this.flyApi.listApps()
      return true
    } catch {
      return false
    }
  }

  private async createVolume(appId: string, sizeGb: number): Promise<string> {
    const volume = await this.flyApi.createVolume({
      app: appId,
      name: `${appId}_storage`,
      size_gb: sizeGb,
      region: 'cdg'
    })
    return volume.id
  }
}
```

### 1.3 Kubernetes Provider (new)
**File**: `src/server/provisioning/providers/kubernetes.ts`

Implement Kubernetes provider for self-hosted deployments:

```typescript
import * as k8s from '@kubernetes/client-node'
import { WorkspaceProvider, WorkspaceConfig, WorkspaceRuntime } from './base.js'

export class KubernetesProvider implements WorkspaceProvider {
  name = 'kubernetes'
  private coreApi: k8s.CoreV1Api
  private appsApi: k8s.AppsV1Api
  private metricsApi: k8s.MetricsV1beta1Api
  private namespace: string

  constructor(config: { kubeconfig?: string, namespace?: string }) {
    const kc = new k8s.KubeConfig()
    if (config.kubeconfig) {
      kc.loadFromFile(config.kubeconfig)
    } else {
      kc.loadFromDefault()
    }

    this.coreApi = kc.makeApiClient(k8s.CoreV1Api)
    this.appsApi = kc.makeApiClient(k8s.AppsV1Api)
    this.metricsApi = kc.makeApiClient(k8s.MetricsV1beta1Api)
    this.namespace = config.namespace || 'boring-workspaces'
  }

  async create(config: WorkspaceConfig): Promise<WorkspaceRuntime> {
    const workspaceNamespace = `ws-${config.workspaceId.slice(0, 8)}`

    // Create dedicated namespace for workspace
    await this.coreApi.createNamespace({
      metadata: {
        name: workspaceNamespace,
        labels: {
          'boring.app/workspace-id': config.workspaceId,
          'boring.app/managed': 'true'
        }
      }
    })

    // Create PVC for workspace storage
    await this.coreApi.createNamespacedPersistentVolumeClaim(workspaceNamespace, {
      metadata: { name: 'workspace-storage' },
      spec: {
        accessModes: ['ReadWriteOnce'],
        resources: { requests: { storage: `${config.storage}Gi` } },
        storageClassName: 'standard'  // configurable
      }
    })

    // Create StatefulSet for workspace (stable network ID + persistent storage)
    const statefulSet = await this.appsApi.createNamespacedStatefulSet(workspaceNamespace, {
      metadata: { name: 'workspace' },
      spec: {
        serviceName: 'workspace',
        replicas: 1,
        selector: { matchLabels: { app: 'workspace' } },
        template: {
          metadata: { labels: { app: 'workspace' } },
          spec: {
            securityContext: {
              fsGroup: 1000,
              runAsUser: 1000,
              runAsNonRoot: true
            },
            containers: [{
              name: 'workspace',
              image: config.baseImage,
              env: Object.entries(config.env || {}).map(([k, v]) => ({ name: k, value: v })),
              resources: {
                requests: {
                  cpu: `${config.cpu}`,
                  memory: `${config.ram}Mi`
                },
                limits: {
                  cpu: `${config.cpu}`,
                  memory: `${config.ram}Mi`
                }
              },
              volumeMounts: [{ name: 'storage', mountPath: '/workspace' }],
              ports: [{ containerPort: 8000, name: 'http' }]
            }],
            volumes: [{
              name: 'storage',
              persistentVolumeClaim: { claimName: 'workspace-storage' }
            }]
          }
        }
      }
    })

    // Create Service for network access
    await this.coreApi.createNamespacedService(workspaceNamespace, {
      metadata: { name: 'workspace' },
      spec: {
        selector: { app: 'workspace' },
        type: 'ClusterIP',
        ports: [{ port: 8000, targetPort: 8000, name: 'http' }]
      }
    })

    return {
      provider: 'kubernetes',
      runtimeId: `${workspaceNamespace}/workspace`,
      status: 'provisioning',
      endpoint: `http://workspace.${workspaceNamespace}.svc.cluster.local:8000`,
      metadata: { namespace: workspaceNamespace, statefulSet: 'workspace' }
    }
  }

  async destroy(runtimeId: string): Promise<void> {
    const [namespace] = runtimeId.split('/')

    // Delete namespace (cascades to all resources)
    await this.coreApi.deleteNamespace(namespace)
  }

  async start(runtimeId: string): Promise<void> {
    const [namespace, name] = runtimeId.split('/')

    // Scale StatefulSet to 1
    await this.appsApi.patchNamespacedStatefulSet(
      name,
      namespace,
      { spec: { replicas: 1 } }
    )
  }

  async stop(runtimeId: string): Promise<void> {
    const [namespace, name] = runtimeId.split('/')

    // Scale StatefulSet to 0
    await this.appsApi.patchNamespacedStatefulSet(
      name,
      namespace,
      { spec: { replicas: 0 } }
    )
  }

  async getStatus(runtimeId: string): Promise<RuntimeStatus> {
    const [namespace, name] = runtimeId.split('/')

    const statefulSet = await this.appsApi.readNamespacedStatefulSet(name, namespace)
    const running = statefulSet.body.status.readyReplicas === 1

    return {
      state: running ? 'running' : 'stopped',
      uptime: running ? Date.now() - new Date(statefulSet.body.metadata.creationTimestamp).getTime() : 0
    }
  }

  async getMetrics(runtimeId: string): Promise<ResourceMetrics> {
    const [namespace] = runtimeId.split('/')

    // Get pod metrics from metrics-server
    const metrics = await this.metricsApi.listNamespacedPod(namespace)
    const podMetrics = metrics.body.items[0]

    return {
      cpu: {
        current: parseFloat(podMetrics.containers[0].usage.cpu),
        limit: 100
      },
      memory: {
        current: parseMemory(podMetrics.containers[0].usage.memory),
        limit: parseMemory(podMetrics.containers[0].resources.limits.memory)
      },
      disk: {
        used: 0,  // requires volume metrics plugin
        total: 10
      }
    }
  }

  async exec(runtimeId: string, command: string): Promise<ExecResult> {
    const [namespace] = runtimeId.split('/')

    const exec = new k8s.Exec(this.coreApi)
    const pod = await this.findPod(namespace)

    return await exec.exec(namespace, pod.name, 'workspace', ['sh', '-c', command], null)
  }

  async healthCheck(): Promise<boolean> {
    try {
      await this.coreApi.listNamespace()
      return true
    } catch {
      return false
    }
  }

  private async findPod(namespace: string): Promise<k8s.V1Pod> {
    const pods = await this.coreApi.listNamespacedPod(namespace, undefined, undefined, undefined, undefined, 'app=workspace')
    return pods.body.items[0]
  }
}

function parseMemory(memStr: string): number {
  const units = { Ki: 1024, Mi: 1024 ** 2, Gi: 1024 ** 3 }
  const match = memStr.match(/^(\d+)(\w+)$/)
  if (!match) return 0
  const [, num, unit] = match
  return parseInt(num) * (units[unit] || 1) / 1024 / 1024  // convert to MB
}
```

### 1.4 Docker Provider (new, for local dev)
**File**: `src/server/provisioning/providers/docker.ts`

Implement Docker provider for local development:

```typescript
import Docker from 'dockerode'
import { WorkspaceProvider, WorkspaceConfig, WorkspaceRuntime } from './base.js'

export class DockerProvider implements WorkspaceProvider {
  name = 'docker'
  private docker: Docker

  constructor(config?: { host?: string, socketPath?: string }) {
    this.docker = new Docker(config || { socketPath: '/var/run/docker.sock' })
  }

  async create(config: WorkspaceConfig): Promise<WorkspaceRuntime> {
    // Create volume for workspace storage
    const volume = await this.docker.createVolume({
      Name: `workspace_${config.workspaceId}`,
      Driver: 'local'
    })

    // Create container
    const container = await this.docker.createContainer({
      name: `workspace_${config.workspaceId}`,
      Image: config.baseImage,
      Env: Object.entries(config.env || {}).map(([k, v]) => `${k}=${v}`),
      HostConfig: {
        Memory: config.ram * 1024 * 1024,  // MB to bytes
        NanoCpus: config.cpu * 1e9,  // cores to nanocpus
        Binds: [`${volume.Name}:/workspace`],
        RestartPolicy: { Name: 'unless-stopped' }
      },
      Labels: {
        'boring.app/workspace-id': config.workspaceId,
        'boring.app/managed': 'true'
      }
    })

    // Start container
    await container.start()

    return {
      provider: 'docker',
      runtimeId: container.id,
      status: 'provisioning',
      endpoint: `http://localhost:${await this.getPort(container)}`,
      metadata: { containerId: container.id, volumeId: volume.Name }
    }
  }

  async destroy(runtimeId: string): Promise<void> {
    const container = this.docker.getContainer(runtimeId)
    await container.stop()
    await container.remove()

    // Remove volume
    const info = await container.inspect()
    const volumeName = info.Mounts.find(m => m.Destination === '/workspace')?.Name
    if (volumeName) {
      await this.docker.getVolume(volumeName).remove()
    }
  }

  async start(runtimeId: string): Promise<void> {
    await this.docker.getContainer(runtimeId).start()
  }

  async stop(runtimeId: string): Promise<void> {
    await this.docker.getContainer(runtimeId).stop()
  }

  async getStatus(runtimeId: string): Promise<RuntimeStatus> {
    const container = this.docker.getContainer(runtimeId)
    const info = await container.inspect()

    return {
      state: info.State.Running ? 'running' : 'stopped',
      uptime: info.State.Running ? Date.now() - new Date(info.State.StartedAt).getTime() : 0,
      lastError: info.State.Error
    }
  }

  async getMetrics(runtimeId: string): Promise<ResourceMetrics> {
    const container = this.docker.getContainer(runtimeId)
    const stats = await container.stats({ stream: false })

    const cpuDelta = stats.cpu_stats.cpu_usage.total_usage - stats.precpu_stats.cpu_usage.total_usage
    const systemDelta = stats.cpu_stats.system_cpu_usage - stats.precpu_stats.system_cpu_usage
    const cpuPercent = (cpuDelta / systemDelta) * stats.cpu_stats.online_cpus * 100

    return {
      cpu: {
        current: cpuPercent,
        limit: 100
      },
      memory: {
        current: stats.memory_stats.usage / 1024 / 1024,
        limit: stats.memory_stats.limit / 1024 / 1024
      },
      disk: {
        used: 0,  // not easily available
        total: 10
      }
    }
  }

  async exec(runtimeId: string, command: string): Promise<ExecResult> {
    const container = this.docker.getContainer(runtimeId)
    const exec = await container.exec({
      Cmd: ['sh', '-c', command],
      AttachStdout: true,
      AttachStderr: true
    })

    const stream = await exec.start({})
    const output = await streamToString(stream)

    return { stdout: output, stderr: '', exitCode: 0 }
  }

  async healthCheck(): Promise<boolean> {
    try {
      await this.docker.ping()
      return true
    } catch {
      return false
    }
  }

  private async getPort(container: Docker.Container): Promise<number> {
    const info = await container.inspect()
    const ports = Object.keys(info.NetworkSettings.Ports)
    return parseInt(ports[0]?.split('/')[0] || '8000')
  }
}
```

### 1.5 Provider Registry
**New file**: `src/server/provisioning/registry.ts`

Centralized registry for all providers:

```typescript
import { WorkspaceProvider } from './providers/base.js'
import { FlyProvider } from './providers/fly.js'
import { KubernetesProvider } from './providers/kubernetes.js'
import { DockerProvider } from './providers/docker.js'

export class ProviderRegistry {
  private providers = new Map<string, WorkspaceProvider>()

  constructor() {
    this.loadProviders()
  }

  private loadProviders() {
    // Fly.io (requires FLY_API_TOKEN)
    if (process.env.FLY_API_TOKEN) {
      this.register(new FlyProvider({
        token: process.env.FLY_API_TOKEN,
        org: process.env.FLY_ORG
      }))
    }

    // Kubernetes (requires KUBECONFIG or in-cluster config)
    if (process.env.KUBECONFIG || process.env.KUBERNETES_SERVICE_HOST) {
      this.register(new KubernetesProvider({
        kubeconfig: process.env.KUBECONFIG,
        namespace: process.env.K8S_NAMESPACE || 'boring-workspaces'
      }))
    }

    // Docker (local dev only)
    if (process.env.DOCKER_HOST || process.env.ENABLE_DOCKER_PROVIDER) {
      this.register(new DockerProvider({
        host: process.env.DOCKER_HOST
      }))
    }
  }

  register(provider: WorkspaceProvider) {
    this.providers.set(provider.name, provider)
    console.log(`Registered workspace provider: ${provider.name}`)
  }

  get(name: string): WorkspaceProvider {
    const provider = this.providers.get(name)
    if (!provider) {
      throw new Error(`Provider '${name}' not found. Available: ${this.list().join(', ')}`)
    }
    return provider
  }

  list(): string[] {
    return Array.from(this.providers.keys())
  }

  async healthCheckAll(): Promise<Record<string, boolean>> {
    const results: Record<string, boolean> = {}
    for (const [name, provider] of this.providers) {
      results[name] = await provider.healthCheck()
    }
    return results
  }
}

// Singleton instance
export const providerRegistry = new ProviderRegistry()
```

### 1.6 Database Schema Updates
**File**: `src/server/db/schema.ts`

Add provider tracking to workspaces:

```typescript
export const workspaceRuntimes = pgTable('workspace_runtimes', {
  // ... existing columns
  provider: text().default('fly').notNull(),  // 'fly' | 'kubernetes' | 'docker'
  providerConfig: jsonb('provider_config'),  // provider-specific metadata
  runtimeId: text('runtime_id'),  // provider's runtime identifier
})
```

### 1.7 Workspace Service Integration
**File**: `src/server/services/workspacePersistence.ts`

Update workspace creation to use provider registry:

```typescript
import { providerRegistry } from '../provisioning/registry.js'

async function createWorkspaceRuntime(workspaceId: string, config: WorkspaceConfig) {
  // Get provider (from user selection or default)
  const providerName = config.provider || process.env.DEFAULT_WORKSPACE_PROVIDER || 'fly'
  const provider = providerRegistry.get(providerName)

  // Create workspace via provider
  const runtime = await provider.create({
    workspaceId,
    baseImage: config.baseImage || 'node:20-bookworm',
    cpu: config.cpu || 2,
    ram: config.ram || 4096,
    storage: config.storage || 10,
    region: config.region
  })

  // Store runtime metadata
  await db.insert(workspaceRuntimes).values({
    workspaceId,
    provider: runtime.provider,
    runtimeId: runtime.runtimeId,
    state: runtime.status,
    providerConfig: runtime.metadata,
    spriteUrl: runtime.endpoint
  })

  return runtime
}
```

### 1.8 Frontend Provider Selection
**File**: `src/front/dialogs/CreateWorkspace.jsx`

Add provider dropdown to workspace creation:

```jsx
import { Select, SelectContent, SelectItem } from '@/components/ui/select'

export function CreateWorkspaceDialog({ open, onClose }) {
  const [provider, setProvider] = useState('fly')
  const { data: providers } = useQuery('/api/v1/providers')

  return (
    <Dialog open={open} onClose={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create Workspace</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div>
            <Label>Name</Label>
            <Input placeholder="my-workspace" />
          </div>

          <div>
            <Label>Infrastructure Provider</Label>
            <Select value={provider} onValueChange={setProvider}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {providers?.map(p => (
                  <SelectItem key={p.name} value={p.name}>
                    {p.displayName}
                    {p.name === 'fly' && <Badge>Managed</Badge>}
                    {p.name === 'kubernetes' && <Badge>Self-Hosted</Badge>}
                    {p.name === 'docker' && <Badge>Local</Badge>}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-sm text-muted-foreground mt-1">
              {provider === 'fly' && 'Automatic provisioning on Fly.io (recommended)'}
              {provider === 'kubernetes' && 'Deploy to your Kubernetes cluster'}
              {provider === 'docker' && 'Run locally with Docker (dev only)'}
            </p>
          </div>

          {/* ... resources, region, etc. */}
        </div>
      </DialogContent>
    </Dialog>
  )
}
```

### 1.9 Backend Provider API
**New file**: `src/server/http/providerRoutes.ts`

API for listing available providers:

```typescript
import { FastifyPluginAsync } from 'fastify'
import { providerRegistry } from '../provisioning/registry.js'

export const providerRoutes: FastifyPluginAsync = async (app) => {
  // List available providers
  app.get('/api/v1/providers', async () => {
    const providers = providerRegistry.list()
    const health = await providerRegistry.healthCheckAll()

    return providers.map(name => ({
      name,
      displayName: formatProviderName(name),
      healthy: health[name],
      description: getProviderDescription(name)
    }))
  })

  // Get provider details
  app.get('/api/v1/providers/:name', async (req) => {
    const { name } = req.params as { name: string }
    const provider = providerRegistry.get(name)
    const healthy = await provider.healthCheck()

    return {
      name: provider.name,
      healthy,
      capabilities: {
        autoShutdown: name !== 'docker',  // Docker doesn't support auto-shutdown well
        metrics: true,
        networking: name === 'kubernetes'
      }
    }
  })
}

function formatProviderName(name: string): string {
  const names = {
    fly: 'Fly.io',
    kubernetes: 'Kubernetes',
    docker: 'Docker'
  }
  return names[name] || name
}

function getProviderDescription(name: string): string {
  const descriptions = {
    fly: 'Managed Fly.io deployment (automatic, global edge network)',
    kubernetes: 'Self-hosted Kubernetes cluster (bring your own infrastructure)',
    docker: 'Local Docker (development only, no persistence)'
  }
  return descriptions[name] || ''
}
```

### 1.10 Configuration & Environment
**File**: `src/server/config.ts`

Update config to support multi-provider:

```typescript
export interface ServerConfig {
  // ... existing config

  providers: {
    default: string  // 'fly' | 'kubernetes' | 'docker'
    fly?: {
      token: string
      organization?: string
    }
    kubernetes?: {
      kubeconfig?: string
      namespace: string
      inCluster: boolean
    }
    docker?: {
      host?: string
      socketPath: string
    }
  }
}

export function loadServerConfig(): ServerConfig {
  return {
    // ... existing config

    providers: {
      default: process.env.DEFAULT_WORKSPACE_PROVIDER || 'fly',

      fly: process.env.FLY_API_TOKEN ? {
        token: process.env.FLY_API_TOKEN,
        organization: process.env.FLY_ORG
      } : undefined,

      kubernetes: (process.env.KUBECONFIG || process.env.KUBERNETES_SERVICE_HOST) ? {
        kubeconfig: process.env.KUBECONFIG,
        namespace: process.env.K8S_NAMESPACE || 'boring-workspaces',
        inCluster: !!process.env.KUBERNETES_SERVICE_HOST
      } : undefined,

      docker: (process.env.DOCKER_HOST || process.env.ENABLE_DOCKER_PROVIDER) ? {
        host: process.env.DOCKER_HOST,
        socketPath: process.env.DOCKER_SOCKET || '/var/run/docker.sock'
      } : undefined
    }
  }
}
```

**Environment variables**:
```bash
# Default provider (optional, defaults to 'fly')
DEFAULT_WORKSPACE_PROVIDER=kubernetes

# Fly.io
FLY_API_TOKEN=...
FLY_ORG=personal

# Kubernetes
KUBECONFIG=/path/to/kubeconfig
K8S_NAMESPACE=boring-workspaces

# Docker (local dev)
ENABLE_DOCKER_PROVIDER=true
DOCKER_HOST=unix:///var/run/docker.sock
```

### Success Criteria
- [ ] Provider abstraction interface defined and documented
- [ ] Fly.io provider refactored to interface (existing workspaces still work)
- [ ] Kubernetes provider implemented and tested
- [ ] Docker provider implemented (optional, for local dev)
- [ ] Provider registry auto-detects available providers
- [ ] Provider selection UI in workspace creation
- [ ] `/api/v1/providers` endpoint returns available providers
- [ ] Can create workspaces on both Fly.io and Kubernetes
- [ ] Metrics collection works across all providers
- [ ] Documentation for self-hosted Kubernetes deployment

---

## Phase 2: Resource Management & Templates (4-5 weeks)

**Goal**: Resource quotas, workspace templates, and auto-shutdown policies (no org layer - per-user quotas)

Since workspaces already provide multi-user abstraction, we'll implement quotas at the **user level** instead of adding an organization layer.

### 2.1 User Quota Schema
**File**: `src/server/db/schema.ts`

```typescript
export const userQuotas = pgTable('user_quotas', {
  userId: uuid('user_id').primaryKey().notNull(),
  maxWorkspaces: integer('max_workspaces').default(5).notNull(),
  maxCpuPerWorkspace: integer('max_cpu_per_workspace').default(4).notNull(),
  maxRamPerWorkspace: integer('max_ram_per_workspace').default(8192).notNull(),  // MB
  maxStoragePerWorkspace: integer('max_storage_per_workspace').default(50).notNull(),  // GB
  maxTotalCpu: integer('max_total_cpu').default(8).notNull(),  // across all workspaces
  maxTotalRam: integer('max_total_ram').default(16384).notNull(),  // MB
  updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull()
})

export const userUsage = pgTable('user_usage', {
  userId: uuid('user_id').primaryKey().notNull(),
  activeWorkspaces: integer('active_workspaces').default(0).notNull(),
  totalCpu: integer('total_cpu').default(0).notNull(),
  totalRam: integer('total_ram').default(0).notNull(),
  totalStorage: integer('total_storage').default(0).notNull(),
  lastUpdated: timestamp('last_updated', { withTimezone: true }).defaultNow().notNull()
})
```

### 2.2 Quota Service
**New file**: `src/server/services/quotaService.ts`

```typescript
import { db } from '../db/index.js'
import { userQuotas, userUsage, workspaces, workspaceRuntimes } from '../db/schema.js'

export class QuotaExceededError extends Error {
  code = 'QUOTA_EXCEEDED' as const
  resource: string

  constructor(resource: string, message: string) {
    super(message)
    this.resource = resource
    this.name = 'QuotaExceededError'
  }
}

export class QuotaService {
  async checkWorkspaceCreation(userId: string, config: WorkspaceConfig): Promise<void> {
    const quota = await this.getQuota(userId)
    const usage = await this.getUsage(userId)

    // Check workspace count
    if (usage.activeWorkspaces >= quota.maxWorkspaces) {
      throw new QuotaExceededError(
        'workspaces',
        `Maximum ${quota.maxWorkspaces} workspaces allowed`
      )
    }

    // Check per-workspace CPU
    if (config.cpu > quota.maxCpuPerWorkspace) {
      throw new QuotaExceededError(
        'cpu',
        `Maximum ${quota.maxCpuPerWorkspace} CPUs per workspace`
      )
    }

    // Check total CPU
    if (usage.totalCpu + config.cpu > quota.maxTotalCpu) {
      throw new QuotaExceededError(
        'total_cpu',
        `Maximum ${quota.maxTotalCpu} total CPUs across all workspaces`
      )
    }

    // Check per-workspace RAM
    if (config.ram > quota.maxRamPerWorkspace) {
      throw new QuotaExceededError(
        'ram',
        `Maximum ${quota.maxRamPerWorkspace}MB RAM per workspace`
      )
    }

    // Check total RAM
    if (usage.totalRam + config.ram > quota.maxTotalRam) {
      throw new QuotaExceededError(
        'total_ram',
        `Maximum ${quota.maxTotalRam}MB total RAM across all workspaces`
      )
    }
  }

  async getQuota(userId: string) {
    const quota = await db.select()
      .from(userQuotas)
      .where(eq(userQuotas.userId, userId))
      .limit(1)

    if (quota.length === 0) {
      // Create default quota
      const defaultQuota = {
        userId,
        maxWorkspaces: 5,
        maxCpuPerWorkspace: 4,
        maxRamPerWorkspace: 8192,
        maxStoragePerWorkspace: 50,
        maxTotalCpu: 8,
        maxTotalRam: 16384
      }
      await db.insert(userQuotas).values(defaultQuota)
      return defaultQuota
    }

    return quota[0]
  }

  async getUsage(userId: string) {
    // Calculate current usage from active workspaces
    const activeWorkspaces = await db.select()
      .from(workspaces)
      .innerJoin(workspaceRuntimes, eq(workspaces.id, workspaceRuntimes.workspaceId))
      .where(
        and(
          eq(workspaces.createdBy, userId),
          isNull(workspaces.deletedAt),
          eq(workspaceRuntimes.state, 'ready')
        )
      )

    const usage = {
      activeWorkspaces: activeWorkspaces.length,
      totalCpu: activeWorkspaces.reduce((sum, ws) => sum + (ws.cpu || 2), 0),
      totalRam: activeWorkspaces.reduce((sum, ws) => sum + (ws.ram || 4096), 0),
      totalStorage: activeWorkspaces.reduce((sum, ws) => sum + (ws.storage || 10), 0)
    }

    // Update cached usage
    await db.insert(userUsage).values({
      userId,
      ...usage,
      lastUpdated: new Date()
    }).onConflictDoUpdate({
      target: userUsage.userId,
      set: { ...usage, lastUpdated: new Date() }
    })

    return usage
  }

  async updateQuota(userId: string, updates: Partial<UserQuota>) {
    await db.update(userQuotas)
      .set({ ...updates, updatedAt: new Date() })
      .where(eq(userQuotas.userId, userId))
  }
}

export const quotaService = new QuotaService()
```

### 2.3 Workspace Templates
**File**: `src/server/db/schema.ts`

```typescript
export const workspaceTemplates = pgTable('workspace_templates', {
  id: uuid().defaultRandom().primaryKey().notNull(),
  name: text().notNull(),
  description: text(),
  baseImage: text('base_image').notNull(),
  defaultCpu: integer('default_cpu').default(2).notNull(),
  defaultRam: integer('default_ram').default(4096).notNull(),
  defaultStorage: integer('default_storage').default(10).notNull(),
  initScript: text('init_script'),  // post-create bash script
  tags: jsonb().default([]),
  isPublic: boolean('is_public').default(true).notNull(),
  createdBy: uuid('created_by'),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull()
})
```

**Seed data**: `src/server/db/seeds/templates.ts`

```typescript
export const defaultTemplates = [
  {
    name: 'Node.js Full-Stack',
    description: 'Node.js 20 with pnpm, tsx, and common tools',
    baseImage: 'node:20-bookworm',
    defaultCpu: 2,
    defaultRam: 4096,
    defaultStorage: 10,
    initScript: `
#!/bin/bash
npm install -g pnpm tsx vitest
git config --global init.defaultBranch main
    `.trim(),
    tags: ['node', 'javascript', 'typescript'],
    isPublic: true
  },
  {
    name: 'Python Data Science',
    description: 'Python 3.11 with pandas, numpy, jupyter',
    baseImage: 'python:3.11-bookworm',
    defaultCpu: 4,
    defaultRam: 8192,
    defaultStorage: 20,
    initScript: `
#!/bin/bash
pip install pandas numpy matplotlib scikit-learn jupyter
jupyter notebook --generate-config
    `.trim(),
    tags: ['python', 'data-science', 'jupyter'],
    isPublic: true
  },
  {
    name: 'Go Development',
    description: 'Go 1.22 with common tools',
    baseImage: 'golang:1.22-bookworm',
    defaultCpu: 2,
    defaultRam: 4096,
    defaultStorage: 10,
    initScript: `
#!/bin/bash
go install golang.org/x/tools/gopls@latest
go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest
    `.trim(),
    tags: ['go', 'golang'],
    isPublic: true
  }
]
```

### 2.4 Auto-Shutdown Policies
**File**: `src/server/db/schema.ts`

```typescript
export const workspaceLifecyclePolicies = pgTable('workspace_lifecycle_policies', {
  workspaceId: uuid('workspace_id').primaryKey().notNull(),
  autoShutdownMinutes: integer('auto_shutdown_minutes').default(30),  // null = never
  autoStartOnConnect: boolean('auto_start_on_connect').default(true).notNull(),
  maxLifetimeHours: integer('max_lifetime_hours'),  // null = unlimited
  lastActivityAt: timestamp('last_activity_at', { withTimezone: true }).defaultNow().notNull(),
  updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull()
})
```

**Cron job**: `src/server/jobs/lifecycleJob.ts`

```typescript
import cron from 'node-cron'
import { db } from '../db/index.js'
import { workspaceLifecyclePolicies, workspaceRuntimes } from '../db/schema.js'
import { providerRegistry } from '../provisioning/registry.js'

// Run every 5 minutes
export function startLifecycleJob() {
  cron.schedule('*/5 * * * *', async () => {
    const now = Date.now()

    // Find workspaces that should auto-shutdown
    const policies = await db.select()
      .from(workspaceLifecyclePolicies)
      .innerJoin(workspaceRuntimes, eq(workspaceLifecyclePolicies.workspaceId, workspaceRuntimes.workspaceId))
      .where(
        and(
          isNotNull(workspaceLifecyclePolicies.autoShutdownMinutes),
          eq(workspaceRuntimes.state, 'ready')
        )
      )

    for (const { workspace_lifecycle_policies: policy, workspace_runtimes: runtime } of policies) {
      const idleMinutes = (now - new Date(policy.lastActivityAt).getTime()) / 1000 / 60

      if (idleMinutes >= policy.autoShutdownMinutes) {
        console.log(`Auto-shutting down workspace ${policy.workspaceId} after ${idleMinutes}min idle`)

        const provider = providerRegistry.get(runtime.provider)
        await provider.stop(runtime.runtimeId)

        await db.update(workspaceRuntimes)
          .set({ state: 'stopped' })
          .where(eq(workspaceRuntimes.workspaceId, policy.workspaceId))
      }
    }
  })
}
```

### 2.5 Template UI
**New file**: `src/front/pages/Templates.jsx`

```jsx
export function TemplatesPage() {
  const { data: templates } = useQuery('/api/v1/templates')

  return (
    <div className="container py-8">
      <h1 className="text-3xl font-bold mb-6">Workspace Templates</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {templates?.map(template => (
          <Card key={template.id}>
            <CardHeader>
              <CardTitle>{template.name}</CardTitle>
              <CardDescription>{template.description}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 text-sm">
                <div className="flex items-center gap-2">
                  <Cpu className="h-4 w-4" />
                  {template.defaultCpu} CPU
                </div>
                <div className="flex items-center gap-2">
                  <MemoryStick className="h-4 w-4" />
                  {template.defaultRam}MB RAM
                </div>
                <div className="flex items-center gap-2">
                  <HardDrive className="h-4 w-4" />
                  {template.defaultStorage}GB Storage
                </div>
              </div>

              <div className="flex flex-wrap gap-1 mt-3">
                {template.tags.map(tag => (
                  <Badge key={tag} variant="secondary">{tag}</Badge>
                ))}
              </div>
            </CardContent>
            <CardFooter>
              <Button onClick={() => createFromTemplate(template.id)}>
                Create Workspace
              </Button>
            </CardFooter>
          </Card>
        ))}
      </div>
    </div>
  )
}
```

### Success Criteria
- [ ] User quotas enforced at workspace creation
- [ ] 3+ built-in templates (Node, Python, Go)
- [ ] Template gallery UI
- [ ] One-click workspace creation from template
- [ ] Auto-shutdown after 30min idle (configurable)
- [ ] Lifecycle job runs every 5 minutes
- [ ] Quota exceeded errors shown in UI

---

## Phase 3: Security & Monitoring (4-5 weeks)

**Goal**: Audit logs, metrics collection, and compliance features

### 3.1 Audit Logs
(Use audit log implementation from original plan Phase 4.1-4.3)

### 3.2 Metrics Collection
(Use metrics implementation from original plan Phase 4.4-4.5)

### 3.3 Network Policies (Kubernetes only)
(Use network policy implementation from original plan Phase 4.6)

### 3.4 GDPR Compliance
(Use compliance implementation from original plan Phase 4.7)

### Success Criteria
- [ ] All workspace/user operations logged
- [ ] Metrics collected every minute
- [ ] Metrics dashboard with charts
- [ ] GDPR export/delete endpoints
- [ ] Network policies for K8s workspaces

---

## Phase 4: Operations & IaC (2-3 weeks)

**Goal**: Terraform/IaC, high availability basics, backup procedures

### 4.1 Terraform Modules
**New directory**: `deploy/terraform/`

```hcl
# deploy/terraform/boring-ui-k8s/main.tf
resource "kubernetes_namespace" "boring_ui" {
  metadata {
    name = "boring-ui"
  }
}

resource "kubernetes_deployment" "backend" {
  metadata {
    name      = "boring-ui-backend"
    namespace = kubernetes_namespace.boring_ui.metadata[0].name
  }

  spec {
    replicas = 3

    selector {
      match_labels = {
        app = "boring-ui"
      }
    }

    template {
      metadata {
        labels = {
          app = "boring-ui"
        }
      }

      spec {
        container {
          name  = "backend"
          image = "ghcr.io/boring-ui/backend:latest"

          env {
            name = "DATABASE_URL"
            value_from {
              secret_key_ref {
                name = "boring-ui-secrets"
                key  = "database_url"
              }
            }
          }

          resources {
            requests = {
              cpu    = "500m"
              memory = "512Mi"
            }
            limits = {
              cpu    = "2000m"
              memory = "2Gi"
            }
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "backend" {
  metadata {
    name      = "boring-ui"
    namespace = kubernetes_namespace.boring_ui.metadata[0].name
  }

  spec {
    selector = {
      app = "boring-ui"
    }

    port {
      port        = 80
      target_port = 8000
    }

    type = "LoadBalancer"
  }
}
```

### 4.2 High Availability
- Run 3+ backend replicas
- Redis for session sharing
- Postgres read replicas
- Health checks

### 4.3 Backup & DR
- Neon Postgres: automatic PITR
- Workspace volume snapshots
- Disaster recovery runbook

### Success Criteria
- [ ] Terraform module for K8s deployment
- [ ] 3-replica backend deployment
- [ ] Health checks configured
- [ ] Backup procedures documented

---

## Success Metrics

### Phase 1 (Infrastructure)
- [ ] Workspaces running on 2+ providers
- [ ] Kubernetes self-hosted deployment works
- [ ] Provider selection in UI functional
- [ ] <5min to add new provider

### Phase 2 (Resource Management)
- [ ] Quotas prevent over-provisioning
- [ ] 5+ templates available
- [ ] 80%+ workspaces from templates
- [ ] Auto-shutdown saves 60%+ idle resources

### Phase 3 (Security)
- [ ] 100% privileged actions logged
- [ ] Metrics dashboard shows usage
- [ ] GDPR export works

### Phase 4 (Operations)
- [ ] Terraform deploys to K8s
- [ ] HA backend (3 replicas)
- [ ] Backups automated

---

## Deployment Guide (Self-Hosted Kubernetes)

### Prerequisites
- Kubernetes 1.28+
- kubectl configured
- Helm 3.x (optional)
- Neon Postgres database
- Domain + TLS cert

### 1. Install Dependencies

```bash
# metrics-server (for resource metrics)
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# cert-manager (for TLS)
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.14.0/cert-manager.yaml
```

### 2. Create Namespace

```bash
kubectl create namespace boring-ui
kubectl create namespace boring-workspaces
```

### 3. Configure Secrets

```bash
kubectl create secret generic boring-ui-secrets \
  --namespace boring-ui \
  --from-literal=database-url='postgres://...' \
  --from-literal=session-secret='...' \
  --from-literal=anthropic-api-key='...'
```

### 4. Deploy boring-ui Backend

```bash
cd deploy/terraform/boring-ui-k8s
terraform init
terraform apply
```

### 5. Configure DNS

```bash
kubectl get svc -n boring-ui boring-ui

# Point your domain to the LoadBalancer IP
```

### 6. Verify

```bash
curl https://your-domain.com/health/ready
```

---

## Next Steps

1. **Start with Phase 1**: Infrastructure abstraction is the foundation
2. **Proof-of-concept**: Deploy to local K8s (minikube/kind) in week 1
3. **Production K8s**: Deploy to production K8s cluster by week 4
4. **Phase 2+**: Add quotas and templates once infrastructure is proven

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Provider API breaking changes | High | Pin SDK versions, integration tests |
| K8s resource quotas need tuning | Medium | Start conservative, monitor metrics |
| Workspace networking complexity | Medium | Use NetworkPolicies, document patterns |
| Provider feature parity | Low | Document provider-specific limitations |

---

## Appendix: Competitive Feature Matrix

| Feature | Coder | boring-ui (current) | boring-ui (post-plan) |
|---------|-------|---------------------|----------------------|
| Multi-provider | ✅ | ❌ (Fly only) | ✅ Phase 1 |
| Kubernetes support | ✅ | ❌ | ✅ Phase 1 |
| Self-hosted | ✅ | ❌ | ✅ Phase 1 |
| Workspace templates | ✅ | ❌ | ✅ Phase 2 |
| Auto-shutdown | ✅ | ❌ | ✅ Phase 2 |
| Resource quotas | ✅ | ❌ | ✅ Phase 2 |
| Audit logs | ✅ | ❌ | ✅ Phase 3 |
| Metrics dashboard | ✅ | ❌ | ✅ Phase 3 |
| RBAC | ✅ | 🟡 (basic) | ✅ (existing) |
| SSH access | ✅ | ❌ | ❌ Out of scope |
| VS Code Remote | ✅ | ❌ | ❌ Out of scope |
| Real-time collab | ❌ | ❌ | ❌ Out of scope |

**Legend**: ✅ Supported | 🟡 Partial | ❌ Not supported
