# Quick Start Guide - Deploy boring-ui in 5 Minutes

## Option 1: Railway (Fastest - 2 minutes) ⚡

1. Click: [![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/boring-ui)
2. Click "Deploy Now"
3. Set `ANTHROPIC_API_KEY` in the Railway dashboard
4. Done! Your instance is live

**Database**: Automatically provisioned PostgreSQL

---

## Option 2: Docker Compose (Self-Hosted - 5 minutes) 🐳

### Prerequisites
- Docker & Docker Compose installed
- PostgreSQL database (or use included PostgreSQL service)

### Steps

```bash
# 1. Clone repo
git clone https://github.com/boring-data/boring-ui.git
cd boring-ui

# 2. Create environment file
cp deploy/.env.example deploy/.env

# 3. Edit secrets (required!)
nano deploy/.env
# Set: DATABASE_URL, BORING_UI_SESSION_SECRET, ANTHROPIC_API_KEY

# 4. Start services
docker-compose -f deploy/docker-compose.yml up -d

# 5. Check status
docker-compose -f deploy/docker-compose.yml ps

# 6. View logs
docker-compose -f deploy/docker-compose.yml logs -f boring-ui

# 7. Visit
open http://localhost:8000
```

### Using Neon (Recommended)

Neon provides a free serverless PostgreSQL database:

```bash
# 1. Sign up at https://neon.tech
# 2. Create a project
# 3. Copy connection string
# 4. Set in .env:
DATABASE_URL=postgresql://user:pass@ep-xxx.neon.tech/neondb?sslmode=require
```

### Using Local PostgreSQL

The docker-compose file includes PostgreSQL:

```bash
# 1. Edit docker-compose.yml - uncomment the postgres service
# 2. Set in .env:
DATABASE_URL=postgresql://boring:your-password@postgres:5432/boring_ui
POSTGRES_PASSWORD=your-password
```

### Generate Secrets

```bash
# Session secret (required)
openssl rand -hex 32

# Use output in .env:
BORING_UI_SESSION_SECRET=<output-here>
```

---

## Option 3: Fly.io (Global Edge - 5 minutes) ✈️

### Prerequisites
- Fly.io account (free tier available)
- flyctl CLI installed

### Steps

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

## Option 4: Render (Auto-Deploy from Git) 🎨

### Steps

1. Go to [render.com/deploy](https://render.com/deploy)
2. Connect your GitHub repo
3. Render auto-detects `render.yaml`
4. Set environment variables:
   - `DATABASE_URL` (auto-set from included PostgreSQL)
   - `ANTHROPIC_API_KEY` (set manually)
5. Click "Create Web Service"
6. Done! Auto-deploys on every git push

**Database**: Automatically provisioned PostgreSQL

---

## Environment Variables Reference

### Required

```bash
# Database connection
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Session secret (generate with: openssl rand -hex 32)
BORING_UI_SESSION_SECRET=your-secret-here

# Anthropic API key
ANTHROPIC_API_KEY=sk-ant-api03-...
```

### Optional

```bash
# Email (for invites, notifications)
RESEND_API_KEY=re_...

# GitHub App (for GitHub integration)
GITHUB_APP_ID=123456
GITHUB_APP_CLIENT_ID=Iv1.abc123
GITHUB_APP_CLIENT_SECRET=secret
GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n..."
GITHUB_APP_SLUG=your-app-slug
```

---

## Verify Installation

### Health Check

```bash
curl http://localhost:8000/health
# Should return: {"status":"ok","timestamp":...}
```

### Ready Check

```bash
curl http://localhost:8000/health/ready
# Should return: {"status":"ready","checks":{...}}
```

### Database Connection

```bash
# Check logs for database connection
docker-compose -f deploy/docker-compose.yml logs boring-ui | grep -i database
# Should see: "Database connected" or similar
```

---

## Troubleshooting

### "Connection refused" to database

**Cause**: Database not reachable or wrong credentials

**Fix**:
```bash
# Test database connection
psql $DATABASE_URL -c "SELECT 1"

# Check if DATABASE_URL is set
docker-compose -f deploy/docker-compose.yml exec boring-ui printenv DATABASE_URL
```

### "bwrap: not found"

**Cause**: bwrap not installed in container

**Fix**: Image includes bwrap by default. If using custom image:
```dockerfile
RUN apt-get update && apt-get install -y bubblewrap
```

### "/workspaces not writable"

**Cause**: Volume permissions issue

**Fix**:
```bash
# Check volume exists
docker volume ls | grep workspaces

# Check container user
docker-compose -f deploy/docker-compose.yml exec boring-ui whoami

# Fix permissions
docker-compose -f deploy/docker-compose.yml exec boring-ui chown -R $(id -u):$(id -g) /workspaces
```

### Port 8000 already in use

**Cause**: Another service using port 8000

**Fix**: Change port in docker-compose.yml:
```yaml
ports:
  - "8080:8000"  # Use port 8080 instead
```

---

## Next Steps

After deployment:

1. **Create first user**: Visit `/` and sign up
2. **Create workspace**: Click "New Workspace"
3. **Invite team**: Share invite link from workspace settings
4. **Configure GitHub**: Set up GitHub App for repository access (optional)

---

## Production Checklist

Before going to production:

- [ ] Use managed PostgreSQL (Neon, Railway, Render)
- [ ] Set strong `BORING_UI_SESSION_SECRET` (32+ random bytes)
- [ ] Configure HTTPS/TLS (Fly.io/Railway/Render do this automatically)
- [ ] Set up monitoring (logs, health checks)
- [ ] Configure backups (database snapshots)
- [ ] Review security settings in database
- [ ] Set up domain name (optional)
- [ ] Test workspace creation and basic operations
- [ ] Configure resource limits (CPU, memory, disk)

---

## Platform Comparison

| Platform | Setup Time | Auto-Deploy | Database | HTTPS | Cost |
|----------|------------|-------------|----------|-------|------|
| **Railway** | 2 min | ✅ Yes | ✅ Included | ✅ Auto | $5/mo |
| **Render** | 3 min | ✅ Yes | ✅ Included | ✅ Auto | $7/mo |
| **Fly.io** | 5 min | Manual | Need Neon | ✅ Auto | $5/mo |
| **Docker Compose** | 5 min | Manual | Self-host | ❌ Manual | Free |
| **DigitalOcean** | 5 min | ✅ Yes | ✅ Included | ✅ Auto | $12/mo |

---

## Getting Help

- **Documentation**: [Full deployment guide](../../deploy/README.md)
- **Issues**: [GitHub Issues](https://github.com/boring-data/boring-ui/issues)
- **Community**: [Discussions](https://github.com/boring-data/boring-ui/discussions)
