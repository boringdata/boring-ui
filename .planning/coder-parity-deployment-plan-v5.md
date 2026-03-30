# Boring-UI Kubernetes Deployment Plan (v5 - Keep It Simple)

**Goal**: Deploy the CURRENT boring-ui architecture to Kubernetes (no major rewrite)

**Status**: Draft (v5 - pragmatic approach)
**Created**: 2026-03-28
**Timeline**: 2-3 weeks

---

## Reality Check

We already have:
- ✅ Multi-user workspaces
- ✅ Workspace isolation (bwrap)
- ✅ File/git/exec operations
- ✅ Auth (Neon)
- ✅ Web IDE

**We DON'T need**: Per-workspace pods, complex agent protocol, Terraform, etc.

**We NEED**: Make it deployable on Kubernetes!

---

## Simple Kubernetes Deployment

### Current Fly.io
```bash
fly deploy -c deploy/fly/fly.backend-agent.toml
```

### Target: Kubernetes
```bash
kubectl apply -f deploy/k8s/
```

That's it!

---

## Phase 1: Basic K8s Deployment (1 week)

### 1.1 Kubernetes Manifests

**File**: `deploy/k8s/deployment.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: boring-ui
  namespace: boring-ui
spec:
  replicas: 1  # Start simple!
  selector:
    matchLabels:
      app: boring-ui
  template:
    metadata:
      labels:
        app: boring-ui
    spec:
      securityContext:
        fsGroup: 1000
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
            cpu: "1"
            memory: 2Gi
          limits:
            cpu: "4"
            memory: 8Gi
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
kind: PersistentVolumeClaim
metadata:
  name: boring-ui-workspaces
  namespace: boring-ui
spec:
  accessModes:
  - ReadWriteOnce  # Simple! No RWX needed with replicas: 1
  resources:
    requests:
      storage: 100Gi
  storageClassName: standard  # Or gp3, etc.
---
apiVersion: v1
kind: Service
metadata:
  name: boring-ui
  namespace: boring-ui
spec:
  type: LoadBalancer
  selector:
    app: boring-ui
  ports:
  - port: 80
    targetPort: 8000
```

**That's it!** Current code runs as-is.

### 1.2 Secrets

```bash
kubectl create namespace boring-ui

kubectl create secret generic boring-ui-secrets \
  --namespace boring-ui \
  --from-literal=database-url="$(vault kv get -field=database_url secret/agent/app/boring-ui/prod)" \
  --from-literal=session-secret="$(vault kv get -field=session_secret secret/agent/app/boring-ui/prod)" \
  --from-literal=anthropic-api-key="$(vault kv get -field=api_key secret/agent/anthropic)"
```

### 1.3 Deploy

```bash
kubectl apply -f deploy/k8s/deployment.yaml

# Get LoadBalancer IP
kubectl get svc -n boring-ui boring-ui
```

Visit `http://<LOAD_BALANCER_IP>`

### 1.4 Dockerfile (Use Existing)

The existing `deploy/shared/Dockerfile.ts-backend` already works! No changes needed.

### Success Criteria
- [ ] Deploys to K8s successfully
- [ ] Users can create workspaces
- [ ] File/git operations work
- [ ] bwrap sandboxing works in K8s pod
- [ ] Data persists (PVC mounted)

---

## Phase 2: Address Gemini's Concerns (1-2 weeks)

Now address the issues WITHOUT rewriting everything:

### 2.1 Noisy Neighbor → Add cgroups to bwrap

**File**: `src/server/adapters/bwrapImpl.ts`

```typescript
// Add CPU/memory limits to bwrap via cgroups
export function buildBwrapArgs(
  workspaceRoot: string,
  options?: {
    cpuShares?: number  // e.g., 1024 (default share)
    memoryLimit?: string  // e.g., '2G'
  }
): string[] {
  const args = [
    '--tmpfs', '/',
    '--proc', '/proc',
    '--dev', '/dev',
    '--tmpfs', '/tmp',
  ]

  // Add cgroup v2 limits (if available)
  if (options?.cpuShares) {
    args.push('--unshare-cgroup')
    args.push('--ro-bind', '/sys/fs/cgroup', '/sys/fs/cgroup')
  }

  // ... existing args

  return args
}
```

**Better**: Use systemd-run to wrap bwrap:

```bash
systemd-run --user --scope \
  --slice=workspace-${workspace_id}.slice \
  --property=CPUQuota=200% \
  --property=MemoryMax=2G \
  bwrap ...
```

Add to K8s pod:
```yaml
securityContext:
  capabilities:
    add: ["SYS_ADMIN"]  # For cgroup management
```

### 2.2 SPOF → Accept It (for now)

**Mitigation**:
- Pod auto-restarts if crashed (K8s does this)
- Save work frequently (already happens)
- Add "Workspace reconnecting..." UI

**Later** (if needed): StatefulSet with 3 pods + workspace→pod routing

### 2.3 Storage → Already Solved

RWO PVC with `replicas: 1` = simple, fast, reliable

### 2.4 Per-User Quotas

Add to workspace creation:

```typescript
// src/server/services/workspacePersistence.ts
async createWorkspace(userId: string, name: string) {
  // Check quota
  const workspaceCount = await this.countUserWorkspaces(userId)
  if (workspaceCount >= 5) {
    throw new Error('Maximum 5 workspaces per user')
  }

  // Check disk usage
  const totalSize = await getDiskUsage(`/workspaces/${userId}`)
  if (totalSize > 50 * 1024 * 1024 * 1024) {  // 50GB
    throw new Error('Disk quota exceeded (50GB)')
  }

  // Create workspace directory
  await mkdir(`/workspaces/${workspaceId}`)
  // ... rest of creation
}
```

### Success Criteria
- [ ] CPU/memory limits per workspace (via cgroups)
- [ ] Disk quotas enforced
- [ ] Pod auto-restarts if crashed
- [ ] User sees reconnecting UI

---

## Phase 3 (Optional): Scale Horizontally

**If** you need more capacity:

### Option A: Vertical Scaling (Easiest)
```yaml
resources:
  limits:
    cpu: "8"      # Bigger pod
    memory: 16Gi
```

### Option B: StatefulSet (Later)
```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: boring-ui
spec:
  replicas: 3
  volumeClaimTemplates:
  - metadata:
      name: workspaces
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 100Gi
```

Each pod gets own PVC. Add routing layer to map workspace→pod.

---

## Comparison: v4 (Coder) vs v5 (Simple)

| Aspect | v4 (Coder Model) | v5 (Simple) |
|--------|------------------|-------------|
| **Complexity** | High (agent, provisioner, per-pod) | Low (existing code) |
| **Timeline** | 10-13 weeks | 2-3 weeks |
| **Code changes** | Major rewrite | Minimal (K8s manifests only) |
| **Storage** | RWO per workspace pod | RWO single PVC |
| **Isolation** | K8s pod boundaries | bwrap (same as now) |
| **Noisy neighbor** | Solved (K8s limits) | Add cgroups (week 2) |
| **SPOF** | Solved (isolated pods) | Accept initially |
| **Scaling** | Horizontal (add pods) | Vertical (bigger pod) |

**v5 is 80% of the benefit for 20% of the work!**

---

## Deployment Comparison

### Current (Fly.io)
```bash
fly deploy -c deploy/fly/fly.backend-agent.toml
```

### v5 (Kubernetes)
```bash
kubectl apply -f deploy/k8s/deployment.yaml
```

### v4 (Coder-like)
```bash
kubectl apply -f deploy/k8s/control-plane.yaml
kubectl apply -f deploy/k8s/provisioner.yaml
# + Terraform templates
# + Agent protocol
# + Workspace routing
```

**v5 is way simpler!**

---

## What We Get

✅ **Self-hosted** - Runs on any K8s cluster
✅ **Enterprise-ready** - K8s = battle-tested platform
✅ **Simple** - Existing code works as-is
✅ **Fast to ship** - 2-3 weeks vs 10-13 weeks
✅ **Can evolve** - Add per-workspace pods later if needed

---

## Timeline

**Week 1**: K8s manifests, deploy to test cluster, verify basic functionality
**Week 2**: Add cgroups for resource limits, quotas, monitoring
**Week 3**: Production deployment, docs, smoke tests

**Total: 2-3 weeks** vs 10-13 weeks (v4)

---

## Addressing Gemini's Concerns

| Issue | v5 Solution | Good Enough? |
|-------|-------------|--------------|
| Noisy neighbor | cgroups limits (week 2) | ✅ Yes |
| SPOF | Pod auto-restart + reconnect UI | 🟡 Acceptable for MVP |
| Stateful sessions | replicas: 1 (no LoadBalancer split) | ✅ Yes |
| Storage | RWO PVC (simple) | ✅ Yes |
| Security | bwrap (same as Fly.io) | ✅ Yes |
| Scaling | Vertical first, StatefulSet later | ✅ Yes |

**Start simple, evolve if needed!**

---

## Next Steps

1. **Try v5 approach** (2-3 weeks) - Get to K8s fast
2. **Iterate** - Add per-workspace pods ONLY if needed
3. **OR** - Go straight to v4 if you want Coder's architecture

**My recommendation**: Start with v5. It's 95% as good for 20% of the effort.

What do you think?
