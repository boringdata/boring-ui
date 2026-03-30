# Deploying boring-ui

boring-ui is a **standard Docker application** that runs on any platform supporting containers.

## Quick Deploy (Pick One)

| Platform | Complexity | Cost | Best For |
|----------|------------|------|----------|
| **Docker Compose** | ⭐ Easy | Free (self-hosted) | Small teams, on-prem |
| **Fly.io** | ⭐⭐ Medium | $5-20/mo | Managed, global edge |
| **Railway** | ⭐ Easy | $5-15/mo | Simple managed hosting |
| **Render** | ⭐ Easy | $7-25/mo | Auto-deploy from Git |
| **DigitalOcean App Platform** | ⭐⭐ Medium | $12-30/mo | Managed K8s-backed |
| **Kubernetes** | ⭐⭐⭐ Hard | Varies | Enterprise, self-hosted |

---

## 1. Docker Compose (Self-Hosted)

**Best for**: Small teams, on-premises, full control

### Setup

```bash
# 1. Copy environment file
cp deploy/.env.example deploy/.env

# 2. Edit secrets
nano deploy/.env

# 3. Start
docker-compose -f deploy/docker-compose.yml up -d

# 4. Visit
open http://localhost:8000
```

**Database**: Use Neon (cloud) or include PostgreSQL in compose (see file)

---

## 2. Fly.io (Managed Edge)

**Best for**: Global deployment, automatic scaling, Heroku-like experience

### Setup

```bash
# 1. Install flyctl
curl -L https://fly.io/install.sh | sh

# 2. Login
fly auth login

# 3. Set secrets
fly secrets set \
  DATABASE_URL="postgresql://..." \
  BORING_UI_SESSION_SECRET="$(openssl rand -hex 32)" \
  ANTHROPIC_API_KEY="sk-ant-..."

# 4. Deploy
fly deploy -c deploy/fly/fly.backend-agent.toml

# 5. Visit
fly open
```

**Database**: Use [Neon](https://neon.tech) (recommended) or `fly postgres create`

---

## 3. Railway (One-Click Deploy)

**Best for**: Fastest deployment, GitHub integration

### Setup

1. Click: [![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/YOUR_TEMPLATE)

2. Or manual:
```bash
# 1. Install Railway CLI
npm install -g @railway/cli

# 2. Login
railway login

# 3. Create project
railway init

# 4. Add PostgreSQL
railway add --plugin postgresql

# 5. Set variables
railway variables set BORING_UI_SESSION_SECRET="$(openssl rand -hex 32)"
railway variables set ANTHROPIC_API_KEY="sk-ant-..."

# 6. Deploy
railway up
```

**Database**: Included PostgreSQL plugin (automatic)

---

## 4. Render (Git-Based Deploys)

**Best for**: Auto-deploy from GitHub, simple pricing

### Setup

1. **Create `render.yaml`** (in repo root):

```yaml
services:
  - type: web
    name: boring-ui
    env: docker
    dockerfilePath: deploy/shared/Dockerfile.ts-backend
    envVars:
      - key: DATABASE_URL
        sync: false  # Set in Render dashboard
      - key: BORING_UI_SESSION_SECRET
        generateValue: true
      - key: ANTHROPIC_API_KEY
        sync: false

databases:
  - name: boring-ui-db
    databaseName: boring_ui
    user: boring_user
```

2. **Deploy**:
   - Go to [render.com/deploy](https://render.com/deploy)
   - Connect GitHub repo
   - Render auto-detects `render.yaml`
   - Set `DATABASE_URL` and `ANTHROPIC_API_KEY` in dashboard
   - Click "Create Web Service"

**Database**: Managed PostgreSQL included

---

## 5. DigitalOcean App Platform

**Best for**: DigitalOcean customers, K8s-backed simplicity

### Setup

1. **Create `app.yaml`**:

```yaml
name: boring-ui
services:
- name: web
  dockerfile_path: deploy/shared/Dockerfile.ts-backend
  github:
    repo: your-org/boring-ui
    branch: main
  http_port: 8000
  envs:
  - key: DATABASE_URL
  - key: BORING_UI_SESSION_SECRET
    type: SECRET
  - key: ANTHROPIC_API_KEY
    type: SECRET
  instance_size_slug: basic-s  # $12/mo

databases:
- name: db
  engine: PG
  version: "16"
```

2. **Deploy**:
```bash
doctl apps create --spec app.yaml
```

Or use the [web UI](https://cloud.digitalocean.com/apps/new)

**Database**: Managed PostgreSQL included

---

## 6. Kubernetes (Advanced)

**Best for**: Enterprise, multi-region, full control

See [`deploy/k8s/README.md`](./k8s/README.md) for manifests and Helm chart.

```bash
kubectl apply -f deploy/k8s/
```

---

## Environment Variables (Required)

All platforms need these:

```bash
# Database (required)
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Session secret (required - generate with: openssl rand -hex 32)
BORING_UI_SESSION_SECRET=your-secret-here

# Anthropic API (required)
ANTHROPIC_API_KEY=sk-ant-...

# Optional
RESEND_API_KEY=re_...
GITHUB_APP_ID=123456
GITHUB_APP_CLIENT_ID=...
GITHUB_APP_CLIENT_SECRET=...
GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----..."
GITHUB_APP_SLUG=your-app-slug
```

---

## Database Options

boring-ui needs PostgreSQL 14+. Options:

### Managed (Recommended)
- **[Neon](https://neon.tech)** - Serverless Postgres, free tier, fast
- **[Supabase](https://supabase.com)** - Free tier, includes auth (optional)
- **[Railway PostgreSQL](https://railway.app)** - Included with deployment
- **[Render PostgreSQL](https://render.com)** - Included with deployment

### Self-Hosted
```yaml
# docker-compose.yml
services:
  postgres:
    image: postgres:16
    volumes:
      - postgres_data:/var/lib/postgresql/data
```

---

## Health Checks

All platforms should configure:

- **Liveness**: `GET /health` (should return 200)
- **Readiness**: `GET /health/ready` (checks DB connection)

---

## Troubleshooting

### "Connection refused" errors
- Check `DATABASE_URL` is set correctly
- Ensure database allows connections from your platform

### "bwrap not found"
- Image includes bwrap by default
- If custom image, install: `apt-get install bubblewrap`

### "/workspaces not writable"
- Ensure volume is mounted at `/workspaces`
- Check container runs as non-root with write permissions

---

## Next Steps

1. **Pick a platform** from the table above
2. **Follow the setup guide** for that platform
3. **Set environment variables** (DATABASE_URL, secrets)
4. **Deploy!**

Questions? See [docs/deployment/](../../docs/deployment/) or open an issue.
