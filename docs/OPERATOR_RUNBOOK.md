# V0 Operator Runbook: Deploy, Smoke, and Restart Workflows

## Overview

This runbook documents the operational procedures for deploying, verifying,
and managing the boring-ui workspace service in V0 sandbox mode. All
operations use script-first workflows under `deploy/sandbox/`.

## Prerequisites

- SSH access to the sprite host
- Environment variables configured (see each section)
- Python 3.10+ on the target host

## 1. Deploy Workspace Service

**Script:** `deploy/sandbox/deploy_workspace_service.sh`

Syncs source code and configuration to the remote sprite host without
starting the service. Idempotent—safe to run multiple times.

### Required Environment

| Variable | Description | Example |
|----------|-------------|---------|
| `SPRITE_HOST` | SSH-reachable hostname/IP | `sprite-01.internal` |

### Optional Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `SERVICE_ROOT` | `/srv/workspace-api` | Remote service installation path |
| `WORKSPACE_ROOT` | `/home/sprite/workspace` | User workspace path |
| `SECRETS_DIR` | `/home/sprite/.auth` | Auth credentials directory |
| `SERVICE_USER` | `sprite` | Remote service user |
| `SOURCE_DIR` | `src/back` | Local source directory |

### Usage

```bash
export SPRITE_HOST=sprite-01.internal
./deploy/sandbox/deploy_workspace_service.sh
```

### Expected Output

- Creates remote directory structure
- Syncs Python source via rsync
- Sets file ownership to SERVICE_USER
- Exit 0 on success, 1 on failure

### Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Source directory not found` | Wrong SOURCE_DIR | Verify `src/back` exists locally |
| SSH connection refused | Host unreachable | Check network and SSH config |
| Permission denied | Wrong user | Verify SSH key and SERVICE_USER |

---

## 2. Configure Exec Profiles

**Script:** `deploy/sandbox/configure_exec_profiles.sh`

Creates server-owned JSON configuration templates for PTY and Claude
sessions. Must run before starting the service.

### Required Environment

| Variable | Description |
|----------|-------------|
| `SPRITE_HOST` | SSH-reachable hostname/IP |

### Optional Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKSPACE_ROOT` | `/home/sprite/workspace` | Workspace path |
| `EXEC_CONFIG_DIR` | `/home/sprite/.config/exec` | Profile config path |
| `PTY_SHELL` | `/bin/bash` | Shell binary for PTY sessions |
| `CHAT_BINARY` | `claude` | Chat binary name |

### Usage

```bash
export SPRITE_HOST=sprite-01.internal
./deploy/sandbox/configure_exec_profiles.sh
```

### Output Profiles

- `pty_shell.json`: Bash shell (3600s timeout, 200KB max output)
- `pty_claude.json`: Claude Code (7200s timeout, 1MB max output)

---

## 3. Start/Restart Service

**Script:** `deploy/sandbox/restart_workspace_service.sh`

Starts or restarts the uvicorn FastAPI server on the remote host.
Kills existing processes before starting.

### Required Environment

| Variable | Description | Example |
|----------|-------------|---------|
| `SPRITE_HOST` | SSH-reachable hostname/IP | `sprite-01.internal` |
| `SPRITES_WORKSPACE_SERVICE_PORT` | Service port | `8080` |

### Optional Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `SERVICE_ROOT` | `/srv/workspace-api` | Service installation path |
| `SERVICE_BIND` | `0.0.0.0` | Bind address |
| `SERVICE_WORKERS` | `1` | Uvicorn workers |

### Usage

```bash
export SPRITE_HOST=sprite-01.internal
export SPRITES_WORKSPACE_SERVICE_PORT=8080
./deploy/sandbox/restart_workspace_service.sh
```

### Expected Behavior

1. Kills any existing `uvicorn.*boring_ui` processes
2. Starts new uvicorn server with nohup
3. Waits 2 seconds, verifies process is alive
4. Exit 0 on success, 1 if process died

### Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Service failed to start | Port in use | Check for other processes on port |
| Process dies immediately | Import error | Check service.log in SERVICE_ROOT |
| Connection refused after start | Bind address wrong | Verify SERVICE_BIND and firewall |

To view logs:
```bash
ssh $SPRITE_HOST "tail -50 $SERVICE_ROOT/service.log"
```

---

## 4. Smoke Check

**Script:** `deploy/sandbox/smoke_check.sh`

Validates the deployed service is healthy, version-compatible, and
responds correctly. Includes security checks.

### Required Environment

| Variable | Description | Example |
|----------|-------------|---------|
| `SPRITES_WORKSPACE_SERVICE_HOST` | Service hostname | `sprite-01.internal` |
| `SPRITES_WORKSPACE_SERVICE_PORT` | Service port | `8080` |

### Optional Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `SMOKE_TIMEOUT` | `5` | Request timeout (seconds) |
| `EXPECTED_VERSION` | `0.1.0` | Expected service version |

### Usage

```bash
export SPRITES_WORKSPACE_SERVICE_HOST=sprite-01.internal
export SPRITES_WORKSPACE_SERVICE_PORT=8080
./deploy/sandbox/smoke_check.sh
```

### Checks Performed

1. **Health:** `/healthz` and `/health` return 200 with `status` key
2. **Version:** `/__meta/version` matches expected major version
3. **Endpoints:** `/api/capabilities`, `/api/config`, `/api/project`,
   `/api/tree`, `/api/git/status`, `/api/sessions` return 200
4. **Security:** Path traversal `../../../etc` returns 400

### Interpreting Results

- `PASS N failed, M passed`: N should be 0 for healthy deploy
- Exit 0: All checks passed
- Exit 1: One or more checks failed

---

## 5. Full Deploy Sequence

Complete deployment procedure from scratch:

```bash
# 1. Set environment
export SPRITE_HOST=sprite-01.internal
export SPRITES_WORKSPACE_SERVICE_HOST=$SPRITE_HOST
export SPRITES_WORKSPACE_SERVICE_PORT=8080

# 2. Deploy code
./deploy/sandbox/deploy_workspace_service.sh

# 3. Configure exec profiles
./deploy/sandbox/configure_exec_profiles.sh

# 4. Start service
./deploy/sandbox/restart_workspace_service.sh

# 5. Verify
./deploy/sandbox/smoke_check.sh
```

---

## 6. Verification Runner

For comprehensive verification beyond smoke checks, use the
programmatic verification runner:

```python
from boring_ui.api.verification_runner import VerificationRunner

runner = VerificationRunner.from_defaults()
report = runner.run_all()
print(report.to_summary_line())
# VERDICT: GO | 265 passed 0 failed 1 skipped in 2.3s
```

The runner executes four phases:
1. **Unit Tests:** Core unit tests and contract verification
2. **E2E Suites:** Parity, resilience, and fault injection
3. **Performance:** Load and latency testing
4. **Live Smoke:** Optional credential-gated live tests

Save artifact bundle for CI:
```python
paths = runner.save_bundle(report, Path('./artifacts'))
# paths = {report, log, timeline, manifest}
```

---

## 7. SLO Measurements

For release go/no-go decisions:

```python
from boring_ui.api.slo_measurements import SLOMeasurementRunner

runner = SLOMeasurementRunner()
report = runner.run_all()
print(report.to_summary_line())
# RELEASE: GO | 6/6 SLOs met
```

V0 SLO targets:
- Readiness latency <= 5000ms
- PTY median latency <= 150ms
- Reattach success rate >= 99%
- Tree p95 multiplier <= 2x local
- Error rate <= 2% under burst
- All fault injection scenarios pass

---

## 8. Failure Recovery

### Service won't start

```bash
# Check logs
ssh $SPRITE_HOST "tail -100 /srv/workspace-api/service.log"

# Check port availability
ssh $SPRITE_HOST "ss -tlnp | grep $SPRITES_WORKSPACE_SERVICE_PORT"

# Kill stale processes
ssh $SPRITE_HOST "pkill -f 'uvicorn.*boring_ui'"

# Redeploy and restart
./deploy/sandbox/deploy_workspace_service.sh
./deploy/sandbox/restart_workspace_service.sh
```

### Smoke check fails

```bash
# Check which endpoint failed (look at script output)
# Manually test individual endpoints:
curl -s http://$SPRITES_WORKSPACE_SERVICE_HOST:$SPRITES_WORKSPACE_SERVICE_PORT/healthz

# If health fails, check service logs
ssh $SPRITE_HOST "tail -50 /srv/workspace-api/service.log"

# If version fails, redeploy
./deploy/sandbox/deploy_workspace_service.sh
./deploy/sandbox/restart_workspace_service.sh
```

### Service degraded but running

```bash
# Check health details
curl -s http://$SPRITES_WORKSPACE_SERVICE_HOST:$SPRITES_WORKSPACE_SERVICE_PORT/healthz | python3 -m json.tool

# Check readiness
curl -s http://$SPRITES_WORKSPACE_SERVICE_HOST:$SPRITES_WORKSPACE_SERVICE_PORT/readyz | python3 -m json.tool

# Restart if degraded
./deploy/sandbox/restart_workspace_service.sh
./deploy/sandbox/smoke_check.sh
```

---

## 9. Manual Verification Checklist

Before marking a deploy as complete:

- [ ] `deploy_workspace_service.sh` exits 0
- [ ] `configure_exec_profiles.sh` exits 0
- [ ] `restart_workspace_service.sh` exits 0
- [ ] `smoke_check.sh` exits 0 with 0 failures
- [ ] `/healthz` returns `{"status": "ok"}`
- [ ] `/readyz` returns 200
- [ ] PTY session can be created and terminated
- [ ] File tree endpoint returns workspace contents
