# Team Self-Hosting Gap Analysis

**Vision**: "Cloud co-work in browser, open source" - Self-hosted IDE for teams

**Created**: 2026-03-29
**Status**: Gap Analysis

---

## 🎯 Vision: What Teams Need

A company should be able to:
1. **Deploy boring-ui** on their infrastructure (1 command)
2. **Invite their team** to use it (no individual setup)
3. **Work in browser** - developers code without local setup
4. **Manage resources** - admin can see usage, set limits
5. **Share workspaces** - team members collaborate on same code
6. **Self-host everything** - no external dependencies, no vendor lock-in

**Like**: Coder, Gitpod, GitHub Codespaces (but self-hosted and open source)

---

## ✅ What We Have (Current Status)

### Core IDE Features
- ✅ Web-based editor (file tree, Monaco, terminal)
- ✅ Git integration (commit, push, pull)
- ✅ AI agent (PI in browser)
- ✅ File operations (read, write, exec)
- ✅ Workspace sandboxing (bwrap)

### Multi-User Support
- ✅ User accounts (Neon Auth)
- ✅ Multiple workspaces per user
- ✅ Workspace invites (can invite others to a workspace)
- ✅ RBAC (owner/editor/viewer roles)

### Deployment
- ✅ Docker Compose (self-hosted)
- ✅ Fly.io, Railway, Render configs
- ✅ Multiple platform support
- ✅ PostgreSQL backend (Neon or self-hosted)

### Backend Architecture
- ✅ TypeScript backend (Fastify + Drizzle ORM)
- ✅ Workspace isolation (bwrap sandboxing)
- ✅ Session management
- ✅ WebSocket support (terminal, file sync)

---

## ❌ Critical Gaps for Team Self-Hosting

### Gap 1: No Team/Organization Concept ⚠️ CRITICAL

**Problem**: Users are isolated - no concept of "team" or "organization"

**Current State**:
- Each user creates their own workspaces
- Can invite others to specific workspaces (one by one)
- No way to say "these 10 people are on the same team"

**What's Missing**:
- Team/organization entity
- Team admin role
- Team-wide settings
- Team workspace templates
- Team resource pooling

**Impact**: Admin can't manage "the engineering team" - must manage individuals

---

### Gap 2: No Admin Dashboard ⚠️ CRITICAL

**Problem**: Admin can't see or manage the instance

**What's Missing**:
- Admin UI to see all users
- Usage dashboard (CPU, RAM, disk per user/workspace)
- Active sessions monitoring
- Resource allocation view
- User management (suspend, delete, quotas)

**Current Workaround**: Query database directly (not acceptable for admins)

**Impact**: Admin has no visibility into what's happening

---

### Gap 3: No Resource Quotas/Limits ⚠️ HIGH

**Problem**: Single user can exhaust all resources

**What's Missing**:
- Per-user quotas (max workspaces, max disk, max CPU/RAM)
- Enforcement of limits
- Resource usage tracking
- Quota exceeded warnings
- Auto-cleanup of idle workspaces

**Current State**: Unlimited - first user can create 100 workspaces and fill disk

**Impact**: One user can crash the instance for everyone

---

### Gap 4: Complex Setup ⚠️ HIGH

**Problem**: Setup requires technical expertise

**Current Setup Process**:
```bash
1. Install Docker + Docker Compose
2. Get PostgreSQL database (Neon or local)
3. Copy .env.example → .env
4. Set DATABASE_URL, SESSION_SECRET, API_KEY, etc.
5. docker-compose up
6. Hope it works
```

**What's Missing**:
- Setup wizard (web UI)
- Health checks and diagnostics
- Auto-configuration
- Setup validation
- Guided first-run experience

**Impact**: Teams get stuck during setup, give up

---

### Gap 5: No Usage Monitoring/Observability ⚠️ MEDIUM

**Problem**: Admin can't see what's using resources

**What's Missing**:
- Real-time metrics (CPU, RAM, disk per workspace)
- Historical usage graphs
- Cost estimation (resource hours × pricing)
- Audit logs (who did what when)
- Alerting (disk full, high CPU, etc.)

**Current State**: No visibility - can only see process usage in `docker stats`

**Impact**: Can't optimize, can't troubleshoot, can't charge back costs

---

### Gap 6: Missing Team Features ⚠️ MEDIUM

**Problem**: Limited collaboration features

**What's Missing**:
- Team workspace templates (pre-configured for team's stack)
- Shared workspace pool (anyone on team can access)
- Team-wide settings (git config, API keys, etc.)
- Team activity feed (who's working on what)
- Workspace transfer (reassign workspace to another team member)

**Current State**: Each user's workspaces are isolated

**Impact**: Teams can't easily collaborate or standardize

---

### Gap 7: Documentation Gaps ⚠️ MEDIUM

**Problem**: Docs assume technical audience, not admin/team lead

**Missing Docs**:
- "Set up boring-ui for your team" (step-by-step)
- Admin guide (user management, monitoring, troubleshooting)
- Team lead guide (inviting team, creating workspaces, templates)
- Troubleshooting guide (common issues + fixes)
- Architecture overview (how it works, what's deployed)
- Security guide (best practices, hardening)

**Current Docs**: Deployment README (technical, not team-focused)

**Impact**: Teams don't know how to set up or manage

---

### Gap 8: Auth Configuration ⚠️ LOW

**Problem**: Auth setup requires Neon Auth (external dependency)

**What's Missing**:
- Built-in auth (email/password without Neon)
- LDAP/SAML integration (for enterprise)
- OAuth providers (Google, GitHub, Microsoft)
- Auth provider abstraction

**Current State**: Locked to Neon Auth

**Impact**: Teams must use Neon (extra dependency) or implement custom auth

---

## 📋 Priority Roadmap to "Team-Ready"

### Phase 1: Admin Essentials (2-3 weeks) ⚠️ MUST HAVE

**Goal**: Admin can see and manage the instance

1. **Admin Dashboard** (src/front/pages/Admin.jsx)
   - User list (email, created, last active, workspace count)
   - Workspace list (all workspaces, owner, disk usage)
   - Resource overview (total CPU, RAM, disk usage)
   - Active sessions (who's online right now)

2. **Basic Quotas** (src/server/services/quotaService.ts)
   - Per-user limits: max 5 workspaces, max 50GB disk
   - Enforce at workspace creation
   - Show quota usage in UI ("3/5 workspaces, 12GB/50GB disk")

3. **Admin API**
   - GET /api/v1/admin/users (list all users)
   - GET /api/v1/admin/workspaces (list all workspaces)
   - GET /api/v1/admin/stats (resource usage)
   - DELETE /api/v1/admin/users/:id (delete user)
   - PUT /api/v1/admin/users/:id/quota (update quota)

**Success Criteria**:
- [ ] Admin can log in and see dashboard
- [ ] Can view all users and their workspaces
- [ ] Can see total resource usage
- [ ] Can delete users
- [ ] Quotas prevent resource exhaustion

---

### Phase 2: Easy Setup (1-2 weeks) ⚠️ MUST HAVE

**Goal**: Non-technical admin can deploy

1. **Setup Wizard** (src/front/pages/Setup.jsx)
   - First-run wizard (before first user signup)
   - Configure: instance name, admin email, domain
   - Auto-generate secrets (SESSION_SECRET)
   - Test database connection
   - Create first admin user

2. **Health Checks** (src/server/http/healthRoutes.ts)
   - GET /health/ready returns detailed checks:
     - Database connection
     - Disk space available (warn if < 10%)
     - bwrap available
     - API keys configured
   - Show health status in admin dashboard

3. **Simplified Docker Compose**
   ```yaml
   # Just run: docker-compose up
   # Everything works out of the box
   services:
     boring-ui:
       image: boring-ui:latest
       environment:
         # Auto-generate on first run if not set
         SETUP_WIZARD: "true"
   ```

4. **Setup Docs** (docs/deployment/TEAM_SETUP.md)
   - "Set up boring-ui for your team in 10 minutes"
   - Step-by-step with screenshots
   - Troubleshooting section

**Success Criteria**:
- [ ] Run `docker-compose up`, visit localhost:8000
- [ ] Setup wizard appears on first visit
- [ ] Can configure and create admin without touching .env
- [ ] Health checks show green status
- [ ] Team lead can follow setup doc and succeed

---

### Phase 3: Team Features (2-3 weeks) ⚠️ NICE TO HAVE

**Goal**: Teams can collaborate effectively

1. **Team/Organization Entity** (src/server/db/schema.ts)
   ```sql
   CREATE TABLE teams (
     id UUID PRIMARY KEY,
     name TEXT NOT NULL,
     created_at TIMESTAMP DEFAULT NOW()
   );

   CREATE TABLE team_members (
     team_id UUID REFERENCES teams(id),
     user_id UUID REFERENCES users(id),
     role TEXT DEFAULT 'member',  -- admin, member
     PRIMARY KEY (team_id, user_id)
   );
   ```

2. **Team Invites** (src/front/pages/Team.jsx)
   - Admin can invite users to team via email
   - Invite link or email invitation
   - New users auto-added to team

3. **Team Workspaces** (src/front/pages/Workspaces.jsx)
   - Checkbox: "Share with team" (everyone can access)
   - Team workspace pool (visible to all team members)
   - Team templates (pre-configured for team's stack)

4. **Team Settings** (src/front/pages/TeamSettings.jsx)
   - Team name
   - Default workspace resources (CPU, RAM, disk)
   - Team-wide git config (name, email)
   - Team quotas (total across all members)

**Success Criteria**:
- [ ] Admin can create a team
- [ ] Can invite team members
- [ ] Team members see shared workspaces
- [ ] Can create team workspace templates

---

### Phase 4: Monitoring & Observability (1-2 weeks) ⚠️ NICE TO HAVE

**Goal**: Admin can monitor and troubleshoot

1. **Metrics Dashboard** (src/front/pages/AdminMetrics.jsx)
   - Resource usage graphs (CPU, RAM, disk over time)
   - Per-user breakdown
   - Per-workspace breakdown
   - Active sessions timeline

2. **Audit Logs** (src/server/services/auditService.ts)
   - Log all admin actions
   - Log workspace creation/deletion
   - Log user login/logout
   - Searchable audit log UI

3. **Alerting** (src/server/jobs/alertingJob.ts)
   - Email admin when disk > 80%
   - Email admin when user hits quota
   - Email admin on repeated login failures

**Success Criteria**:
- [ ] Metrics dashboard shows resource usage
- [ ] Audit logs are searchable
- [ ] Alerts trigger on critical events

---

## 🎯 Minimum Viable Product for Teams

**To be "team-ready", we MUST have**:

### Must Have (Phase 1 + 2)
✅ Admin dashboard (see all users/workspaces)
✅ Resource quotas (prevent exhaustion)
✅ Setup wizard (easy first-run)
✅ Health checks (diagnose issues)
✅ Setup docs (team-focused)

### Should Have (Phase 3)
🟡 Team/organization entity
🟡 Team invites (onboard team easily)
🟡 Team workspaces (shared collaboration)

### Nice to Have (Phase 4)
🟢 Metrics dashboard
🟢 Audit logs
🟢 Alerting

---

## 📊 Comparison: Current vs Team-Ready

| Feature | Current | Team-Ready (Post-Phase 1-2) |
|---------|---------|----------------------------|
| **Setup** | Manual .env editing | Setup wizard |
| **Admin Tools** | None (query DB) | Admin dashboard |
| **Quotas** | None (unlimited) | Per-user limits |
| **Team Concept** | None | Teams + invites (Phase 3) |
| **Monitoring** | None | Health checks + metrics (Phase 4) |
| **Docs** | Technical | Team-focused guides |
| **Auth** | Neon Auth only | Built-in (future) |

---

## 🚀 Recommended Approach

### Ship Phase 1-2 First (3-5 weeks)

**Phase 1: Admin Essentials** (2-3 weeks)
- Admin dashboard
- Basic quotas
- Admin API

**Phase 2: Easy Setup** (1-2 weeks)
- Setup wizard
- Health checks
- Team setup docs

**Result**: Teams can self-host and admin can manage

### Then Phase 3 (Optional, 2-3 weeks)
- Team/org entity
- Team invites
- Team workspaces

**Result**: Better team collaboration

---

## 💡 Key Insights

### What's Actually Missing?

**Not missing**: Core IDE features (editor, git, terminal, AI) ✅
**Not missing**: Multi-user support (accounts, workspaces, RBAC) ✅
**Not missing**: Deployment (Docker Compose, multiple platforms) ✅

**Missing**: **Admin tooling** and **easy setup** ⚠️

### Why Teams Can't Use It Today

1. **Setup is too hard** - Requires technical expertise, manual config
2. **No admin dashboard** - Can't see or manage users/resources
3. **No quotas** - One user can crash the instance
4. **No docs** - No "set up for your team" guide

### The Fix

**Focus on Phase 1-2**: Admin dashboard + Setup wizard + Docs

**Timeline**: 3-5 weeks to "team-ready"

---

## 📝 Next Steps

1. **Review this gap analysis** - Confirm priorities
2. **Start Phase 1** - Admin dashboard (2-3 weeks)
   - User list
   - Workspace list
   - Resource overview
   - Basic quotas
3. **Then Phase 2** - Setup wizard (1-2 weeks)
   - First-run wizard
   - Health checks
   - Team setup docs
4. **Ship it** - Teams can now self-host!

**Goal**: Make boring-ui as easy to self-host as GitLab or Nextcloud

---

## ❓ Questions for Review

1. **Phase 1-2 only?** Or also ship Phase 3 (team features)?
2. **Auth**: Keep Neon Auth or add built-in email/password?
3. **Metrics**: Must have in MVP or nice-to-have?
4. **Team vs Organization**: Use "team" terminology or "organization"?

Let's focus on **admin tooling** and **easy setup** first - that's 80% of what's needed!
