# Boring UI Operational Runbooks (bd-1pwb.9.3)

## Overview

This document describes common failure modes, diagnosis procedures, and remediation steps for boring-ui in production. Each incident type includes SLO targets and alert thresholds.

## Alert Baselines & SLOs

| Alert | Threshold | SLO Target | Severity |
|-------|-----------|-----------|----------|
| Auth Success Rate | < 98% | 99% success rate | P2 |
| Auth Failures (spike) | > 10 in 1min | < 1 per minute | P1 |
| Authz Denials (spike) | > 5 in 1min | < 1 per minute | P1 |
| Proxy Latency | > 1000ms p99 | < 500ms p99 | P2 |
| Sandbox Health | < 95% | 99% healthy | P1 |
| File Op Latency | > 500ms p99 | < 200ms p99 | P2 |
| Error Rate | > 1% | < 0.1% | P1 |
| Uptime | < 99.9% rolling | 99.99% rolling | P0 |

---

## Incident 1: High Auth Failure Rate

### Symptoms
- Metrics: `auth_failure_count` increasing sharply
- Dashboard: "Auth Success Rate" alert firing (< 98%)
- Logs: Multiple "Auth failure" entries in structured logs

### Diagnosis Steps

1. **Check auth failure reasons**
   ```bash
   # Query metrics endpoint
   curl http://localhost:8000/api/v1/metrics | jq '.authentication.failure_reasons'
   ```
   - `invalid_token` → Token validation issue
   - `expired` → Token expiry too short
   - `missing_sub` → JWT structure issue

2. **Check OIDC provider connectivity**
   ```bash
   # Verify JWKS endpoint is reachable
   curl ${OIDC_ISSUER}/.well-known/jwks.json
   # Should return 200 with valid keys
   ```

3. **Check token issuance**
   - Verify clients are using correct token format
   - Check Authorization header is "Bearer {token}"

4. **Check logs for patterns**
   ```bash
   # Find most recent auth failures
   grep "Auth failure" .logs/audit/events.jsonl | tail -20 | jq '.'
   ```

### Remediation

- **If OIDC unreachable**: 
  - Verify network connectivity to OIDC provider
  - Check OIDC_ISSUER environment variable
  - Restart backend to refresh JWKS cache

- **If tokens expired too quickly**:
  - Increase token TTL in token issuer configuration
  - Coordinate with OIDC provider on token expiry settings

- **If token format wrong**:
  - Review client implementation of JWT usage
  - Ensure "Bearer" prefix is included in Authorization header

### Prevention

- Monitor auth failure reasons dashboard continuously
- Set alert threshold at 5% increase in failures
- Implement gradual rollout of auth changes

---

## Incident 2: Authorization Denials (Policy Rejection)

### Symptoms
- Metrics: `authz_denied_count` increasing
- Dashboard: "Authz Denial Rate" alert
- Logs: "Authz denied" entries for specific users/resources

### Diagnosis Steps

1. **Check denial reasons**
   ```bash
   curl http://localhost:8000/api/v1/metrics | jq '.authorization.denial_reasons'
   ```
   - `missing_permission` → User lacks required permission
   - `quota_exceeded` → Rate limit hit
   - `workspace_mismatch` → User accessing wrong workspace

2. **Trace specific denials**
   ```bash
   # Query audit events with request_id from logs
   grep "request_id: {ID}" .logs/audit/events.jsonl | jq '.details'
   ```

3. **Check user permissions**
   - Verify permission claims in JWT
   - Check workspace assignment
   - Confirm resource is in user's workspace

4. **Check rate limits**
   - Verify quota settings
   - Check if user has exceeded operation limits

### Remediation

- **If missing permissions**:
  - Grant user required permission in OIDC provider
  - Invalidate cached permissions (refresh JWKS)
  - Re-authenticate user

- **If quota exceeded**:
  - Increase per-user quota limit
  - Distribute load across multiple users/api-keys
  - Implement request batching on client side

- **If workspace mismatch**:
  - Verify workspace_id claim in JWT
  - Ensure user has access to requested workspace
  - Update OIDC provider role mapping

### Prevention

- Monitor denial reasons by user
- Alert on first denial for new users (typo check)
- Implement permission matrix review process

---

## Incident 3: High Proxy Latency

### Symptoms
- Metrics: `proxy_operations.latency_ms.p99 > 1000ms`
- Dashboard: "Proxy Latency p99" alert
- Logs: Slow request logs in structured logging

### Diagnosis Steps

1. **Check operation type breakdown**
   ```bash
   curl http://localhost:8000/api/v1/metrics | jq '.operations | keys[]'
   ```
   - Identify which operation type (file, git, exec) is slow

2. **Trace slow requests**
   ```bash
   # Find requests with latency > 1000ms
   grep "latency_ms" .logs/audit/events.jsonl | grep -E '"latency_ms":\s*[1-9][0-9]{3}' | head -10
   ```

3. **Check sandbox operation latency**
   ```bash
   curl http://localhost:8000/api/v1/metrics | jq '.operations.proxy | .latency_ms'
   ```

4. **Check upstream service health**
   - Verify sandbox-agent is responding
   - Check network latency to sandbox
   - Monitor disk I/O on workspace filesystem

### Remediation

- **If sandbox slow**:
  - Check sandbox process CPU/memory
  - Restart sandbox-agent if stuck
  - Scale sandbox resources (more CPU, memory)

- **If network latency high**:
  - Check VPC connectivity
  - Verify no network policy restrictions
  - Use lower-latency deployment region

- **If disk I/O slow**:
  - Check filesystem performance
  - Monitor disk I/O queue depth
  - Move to faster storage if needed

### Prevention

- Set p99 latency baseline before declaring SLO
- Implement request timeout (fail fast if > 2s)
- Cache frequently accessed files

---

## Incident 4: Sandbox Health Degradation

### Symptoms
- Metrics: `sandbox_health_percent < 95%`
- Dashboard: "Sandbox Health" alert
- Logs: "Sandbox health check failed" entries

### Diagnosis Steps

1. **Check health check pass rate**
   ```bash
   curl http://localhost:8000/api/v1/metrics | jq '.sandbox'
   ```

2. **Direct sandbox health check**
   ```bash
   curl http://localhost:2468/v1/health
   # Should return 200 with { "status": "ok" }
   ```

3. **Check sandbox logs**
   ```bash
   # Look for startup errors or crashes
   journalctl -u boring-ui-sandbox | tail -50
   ```

4. **Check workspace filesystem**
   ```bash
   # Verify workspace is accessible
   ls -la /home/sprite/workspace
   ```

### Remediation

- **If sandbox unresponsive**:
  - Kill sandbox process: `pkill -f sandbox-agent`
  - Backend will auto-restart on next request
  - Or manually trigger: `POST /api/sandbox/restart`

- **If workspace inaccessible**:
  - Check filesystem mount
  - Verify permissions (755 on workspace dir)
  - Restart NFS if networked

- **If repeated failures**:
  - Check sandbox process resource limits
  - Look for memory leaks (check ps aux)
  - Restart backend to clear cached sandbox state

### Prevention

- Monitor sandbox startup latency (alert if > 2s)
- Implement health check every 30s (automated restarts)
- Keep workspace clean (archive old files monthly)

---

## Incident 5: High Error Rate

### Symptoms
- Metrics: `error_count` increasing sharply
- Dashboard: "Error Rate" alert (> 1%)
- Logs: Multiple error entries with different types

### Diagnosis Steps

1. **Check error types**
   ```bash
   curl http://localhost:8000/api/v1/metrics | jq '.errors.by_type'
   ```

2. **Sample recent errors**
   ```bash
   # Find errors in audit trail
   grep '"status":"failure"' .logs/audit/events.jsonl | tail -20 | jq '.details.error'
   ```

3. **Check backend logs for exceptions**
   ```bash
   # Look for stack traces
   grep -i "traceback\|exception\|error" /var/log/boring-ui.log | tail -50
   ```

4. **Identify affected operation**
   - File operations failing?
   - Git operations failing?
   - Exec operations failing?

### Remediation

- **For file operation errors**:
  - Check workspace disk space: `df -h`
  - Verify file permissions
  - Check for corrupted files

- **For git operation errors**:
  - Verify git binary is available
  - Check git repository integrity
  - Look for stale locks: `find .git -name "*.lock" -delete`

- **For exec operation errors**:
  - Check command availability in sandbox
  - Verify sandbox $PATH is correct
  - Look for timeout or resource limit issues

- **For transient errors**:
  - Most errors auto-recover
  - Monitor error rate trend
  - Alert on sustained error rate > 5%

### Prevention

- Implement exponential backoff for retries
- Set operation timeouts (fail fast)
- Regular sanity checks on workspace health

---

## Incident 6: Memory/Disk Exhaustion

### Symptoms
- Metrics: `error_rate` high with "out of memory" or "disk full" errors
- System: `df -h` shows 100% usage or `free -h` shows low memory
- Logs: "No space left on device" or "Cannot allocate memory"

### Diagnosis Steps

1. **Check disk usage**
   ```bash
   du -sh /home/sprite/workspace/*
   # Find largest directories
   ```

2. **Check memory pressure**
   ```bash
   free -h
   # Check if memory < 10% available
   ```

3. **Check audit log size**
   ```bash
   ls -lh .logs/audit/events.jsonl
   # Archive if > 1GB
   ```

### Remediation

- **If disk full**:
  - Archive old audit logs: `gzip .logs/audit/events.jsonl.{date}`
  - Delete temporary workspace files
  - Scale volume size up

- **If memory exhausted**:
  - Restart backend: `systemctl restart boring-ui`
  - Check for memory leaks in sandbox
  - Increase container memory limit

### Prevention

- Set up log rotation (max 100MB per file)
- Archive audit logs monthly to S3
- Monitor disk usage with alert at 80%
- Implement periodic service restart (weekly)

---

## Quick Reference: Alert Response Flowchart

```
Alert fires
  ↓
Check metrics dashboard
  ├─ If auth failure rate high → Incident 1
  ├─ If authz denial rate high → Incident 2
  ├─ If proxy latency high → Incident 3
  ├─ If sandbox health low → Incident 4
  ├─ If error rate high → Incident 5
  └─ If disk/memory → Incident 6
     ↓
  Run diagnosis steps
     ↓
  Apply remediation
     ↓
  Monitor metrics (5-10 min)
     ↓
  If resolved: Post-incident review
  If not: Escalate to engineering
```

---

## Escalation

If incident cannot be resolved in 30 minutes:

1. **Check logs for root cause**
   ```bash
   # Full audit trail from last 1 hour
   find .logs -name "*.jsonl" -mmin -60 -exec cat {} \; | jq '.details'
   ```

2. **Collect diagnostics**
   ```bash
   # Capture system state
   ps aux > /tmp/ps.txt
   df -h > /tmp/df.txt
   free -h > /tmp/free.txt
   ```

3. **Escalate to on-call engineer**
   - Include alert name, timestamp, and metrics
   - Include diagnostics bundle
   - Include relevant log excerpts

---

## Post-Incident Review

After resolution, document:
- Root cause
- How it was detected
- How it was resolved
- Preventive measures added
- Update runbook if necessary

