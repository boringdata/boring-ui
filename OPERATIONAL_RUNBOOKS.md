# Boring UI - Operational Runbooks (bd-1pwb.9.3)

Operational runbooks for common failure modes and incident response. Each runbook maps observed metrics to specific remediation steps.

## Alert: High Authentication Failure Rate

**Alert Trigger**: `auth_failures_total > 10` per hour

**Symptoms**:
- Users unable to authenticate
- Elevated 401 Unauthorized responses in logs
- Auth latency increases above baseline

**Root Cause Analysis**:
1. Check OIDC provider health:
   ```bash
   curl -s https://${OIDC_ISSUER}/.well-known/jwks.json
   # Should return 200 with valid JWKS
   ```

2. Verify OIDC configuration:
   ```bash
   echo $OIDC_ISSUER $OIDC_AUDIENCE
   # Should match actual IdP settings
   ```

3. Check clock skew between services:
   ```bash
   # Compare timestamps in auth error logs with current time
   # Discrepancy > 5 minutes indicates clock sync issue
   ```

**Remediation Steps**:

| Issue | Fix |
|-------|-----|
| JWKS fetch failing | Verify IdP is accessible, check CORS headers |
| Token validation failing | Verify OIDC_ISSUER and OIDC_AUDIENCE match IdP config |
| Clock skew > 5 min | Resync system clock with `ntpdate` or `timedatectl` |
| JWKS cache stale | Wait 1 hour for TTL, or restart service to refresh |

**Escalation**:
- If JWKS endpoint unreachable: Contact IdP team
- If token validation still fails: Check IdP token format (RS256, claims)
- If persists > 15 min: Failover to backup OIDC provider or manual auth

---

## Alert: High Authorization Denial Rate

**Alert Trigger**: `auth_denials_total > 20` per hour (policy rejections)

**Symptoms**:
- Users get 403 Forbidden errors
- Audit log shows AUTHZ_DENIED events
- Legitimate users cannot access resources

**Root Cause Analysis**:
1. Check audit trail for patterns:
   ```bash
   # Query JSONL audit file
   grep 'AUTHZ_DENIED' .logs/audit/events.jsonl | jq '.details'
   ```

2. Identify permission gaps:
   - Which permissions are consistently denied?
   - Are certain user groups affected?

3. Check policy configuration:
   ```bash
   grep -r "required.*permission\|permission.*denied" config/
   ```

**Remediation Steps**:

| Scenario | Fix |
|----------|-----|
| Legitimate users denied | Update permission policy to grant access |
| Overly permissive policy | Audit token claims, restrict permissions |
| Policy misconfiguration | Check workspace_id mapping in tokens |
| Role/group not recognized | Verify OIDC provider sends correct claims |

**Rollback**:
```bash
# If policy change caused denials, revert:
git revert <commit-hash>
systemctl restart boring-ui
```

---

## Alert: High Proxy Latency

**Alert Trigger**: `proxy_latency_ms p99 > 2000` (>2 seconds)

**Symptoms**:
- Slow responses from hosted->sandbox proxy
- Client requests timing out
- User reports sluggish UI

**Root Cause Analysis**:
1. Check proxy error rate:
   ```bash
   grep 'proxy_error\|timeout' .logs/app.log
   ```

2. Check sandbox health:
   ```bash
   curl http://127.0.0.1:2468/v1/health
   # Should return 200 with quick response
   ```

3. Monitor network latency:
   ```bash
   ping sandbox-host  # Check RTT
   ss -tulpn | grep :2468  # Check socket stats
   ```

4. Check resource utilization on sandbox:
   ```bash
   free -h  # Memory
   df -h    # Disk
   top      # CPU
   ```

**Remediation Steps**:

| Cause | Fix |
|-------|-----|
| Sandbox overloaded | Scale sandbox horizontally, add replicas |
| Network latency | Optimize network path, use closer regions |
| Memory pressure | Increase sandbox heap, reduce max connections |
| Slow operations | Profile slow handlers, add caching |

---

## Alert: Sandbox Operation Failures

**Alert Trigger**: `sandbox_operation_errors_total > 10` per hour

**Symptoms**:
- File operations fail with errors
- Git operations timeout
- Command execution returns errors
- Audit trail shows EXEC_RUN failures

**Root Cause Analysis**:
1. Check sandbox logs:
   ```bash
   tail -f .logs/sandbox.log
   # Look for startup errors, memory issues, permission denials
   ```

2. Check which operations fail:
   ```bash
   grep 'EXEC_RUN.*failure\|FILE_.*error' .logs/audit/events.jsonl
   ```

3. Verify sandbox process:
   ```bash
   ps aux | grep sandbox-agent
   lsof -p <pid>  # Check open files
   ```

4. Check workspace permissions:
   ```bash
   ls -la workspace_root/
   # Ensure sandbox process can read/write
   ```

**Remediation Steps**:

| Issue | Fix |
|-------|-----|
| Sandbox crash | Restart: `pkill -f sandbox-agent && systemctl restart boring-ui` |
| Permission denied | Fix workspace permissions: `chmod 755 workspace_root` |
| Disk full | Clean up: `rm -rf .logs/*old* .cache/` |
| Memory exhausted | Increase heap: `SANDBOX_HEAP=2G systemctl restart` |
| Network error | Check connectivity to external services |

---

## Alert: High File Operation Latency

**Alert Trigger**: `file_operation_latency_ms p99 > 5000` (>5 seconds)

**Symptoms**:
- File reads/writes are slow
- Editor becomes unresponsive
- User perceives laggy file operations

**Root Cause Analysis**:
1. Check file operation errors:
   ```bash
   grep 'FILE_.*error' .logs/audit/events.jsonl | wc -l
   ```

2. Check disk I/O:
   ```bash
   iostat -x 1 5  # Monitor disk utilization
   ```

3. Profile slow operations:
   ```bash
   grep 'FILE_READ\|FILE_WRITE' .logs/app.log | jq '.latency_ms'
   ```

4. Check filesystem:
   ```bash
   df -i  # Inode usage
   fsck -n workspace_root  # Check filesystem errors
   ```

**Remediation Steps**:

| Cause | Fix |
|-------|-----|
| Disk I/O bottleneck | Add SSD, increase IO capacity |
| Too many open files | Increase ulimit: `ulimit -n 65536` |
| Large files | Optimize by streaming or chunking |
| Filesystem fragmentation | Defragment or migrate to ext4 |

---

## Incident Response Checklist

When multiple alerts fire simultaneously:

### Phase 1: Stabilize (5 minutes)
- [ ] Check service health: `curl /health`
- [ ] Verify OIDC provider is accessible
- [ ] Confirm sandbox is running
- [ ] Check available disk/memory/CPU

### Phase 2: Diagnose (10 minutes)
- [ ] Collect metrics summary: `GET /api/metrics`
- [ ] Search audit trail for error patterns
- [ ] Check service logs for exceptions
- [ ] Identify affected users/workspaces

### Phase 3: Mitigate (15 minutes)
- [ ] If auth failing: Restart auth service
- [ ] If sandbox issues: Restart sandbox manager
- [ ] If performance: Trigger horizontal scaling
- [ ] If data issue: Run consistency checks

### Phase 4: Recovery (30+ minutes)
- [ ] Verify remediation resolved alerts
- [ ] Clear any cached bad state
- [ ] Monitor for secondary failures
- [ ] Document incident details

---

## Rollback Procedures

### Quick Rollback (if latest deploy introduced issue)
```bash
# Revert to previous commit
git revert HEAD

# Rebuild and restart
python3 -c "from boring_ui.api.app import create_app; import uvicorn; \
  app = create_app(include_sandbox=True); \
  uvicorn.run(app, host='0.0.0.0', port=8000)"
```

### Full Rollback (if major incident)
```bash
# Restore from backup
aws s3 cp s3://boring-ui-backups/workspace.tar.gz .
tar -xzf workspace.tar.gz

# Restart from clean state
systemctl restart boring-ui
```

---

## SLO Targets

| Signal | SLO | Alert Threshold |
|--------|-----|-----------------|
| Auth success rate | 99.5% | <99.5% or 401>5/hr |
| Auth latency (p99) | <500ms | >500ms |
| Authz denial rate | <1% | >20 denials/hr |
| Proxy latency (p99) | <2s | >2000ms |
| Proxy error rate | <0.1% | >5 errors/hr |
| Sandbox operation success | >99% | <99% or >10 errors/hr |
| File operation latency (p99) | <5s | >5000ms |
| Overall uptime | 99.9% | <99.9% or service down |

---

## Monitoring Dashboard Metrics

Export these metrics for dashboard visualization:

```json
{
  "uptime_seconds": "Value from /api/metrics",
  "auth": {
    "failures_total": "auth_failures_total counter",
    "denials_total": "auth_denials_total counter",
    "latency_ms": {
      "avg": "Mean latency",
      "p99": "99th percentile",
      "max": "Max observed"
    }
  },
  "proxy": {
    "errors_total": "proxy_errors_total counter",
    "latency_ms": {
      "p99": "99th percentile"
    }
  },
  "sandbox": {
    "errors_total": "sandbox_operation_errors counter",
    "startup_time_ms": "Startup latency",
    "operation_latency_ms": {
      "p99": "99th percentile by operation"
    }
  },
  "file_operations": {
    "errors_total": "file_operation_errors counter",
    "latency_ms": {
      "p99": "99th percentile by operation"
    }
  },
  "alerts": {
    "active": ["list of active alert names"],
    "severity": "critical|warning|info"
  }
}
```

---

## Escalation Contacts

- **Auth Issues**: OIDC provider support
- **Sandbox Issues**: Sandbox agent team
- **Infrastructure**: Platform team
- **Data Integrity**: Database team
- **On-call**: Check PagerDuty rotation

---

## Related Documentation

- `MEMORY.md` - Architecture and key learnings
- `SPRITES_AUTHENTICATION.md` - Auth token flow
- `SPRITES_DEPLOYMENT_GUIDE.md` - Deployment procedures
