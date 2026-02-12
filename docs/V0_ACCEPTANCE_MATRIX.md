# V0 Acceptance Matrix and Known Limitations

## Test Coverage Summary

| Suite | Tests | Status |
|-------|-------|--------|
| Unit tests (core) | ~1500+ | Pass |
| Contract tests | 20+ | Pass |
| E2E parity (local vs sandbox) | 97 | Pass |
| E2E resilience | 60 | Pass |
| Fault injection | 52 | Pass |
| Performance/load | 48 | Pass |
| Smoke tests (gated) | 6 | Pass |
| CI matrix wiring | 81 | Pass |
| Verification runner | 42 | Pass |
| SLO measurements | 53 | Pass |

## Acceptance Criteria → Test Mapping

### 1. Contract Compatibility

| Criterion | Test Suite | Result |
|-----------|-----------|--------|
| HTTP API contract preserved | `test_workspace_contract.py` | Pass |
| Response shape parity (local vs sandbox) | `test_e2e_parity.py::TestCompareResponseShapes` | Pass |
| Status code mapping (all endpoints) | `test_e2e_parity.py::TestCompareStatusCodes` | Pass |
| WS close code parity | `test_e2e_parity.py::TestCompareWsCloseCodes` | Pass |
| Error category normalization | `test_error_normalization.py` | Pass |
| No provider detail leaks | `test_fault_injection.py::*no_leak*` | Pass |
| Error semantics E2E | `test_error_semantics_e2e.py` | Pass |

### 2. Health and Readiness

| Criterion | Test Suite | Result |
|-----------|-----------|--------|
| /healthz returns structured status | `test_health_endpoints.py` | Pass |
| /readyz gates on critical deps | `test_health_endpoints.py` | Pass |
| Startup checks validate service | `test_startup_checks.py` | Pass |
| Health flap handling | `test_fault_injection.py::TestInjectHealthFlapActive` | Pass |
| Readiness SLO (<= 5s) | `test_slo_measurements.py::test_measure_readiness_latency` | Pass |

### 3. Proxy and Delegation

| Criterion | Test Suite | Result |
|-----------|-----------|--------|
| HTTP delegation maps status codes | `test_http_delegation.py` | Pass |
| Response policy enforced | `test_response_policy.py` | Pass |
| Proxy client request forwarding | `test_proxy_client.py` | Pass |
| Proxy guardrails (path traversal) | `test_proxy_guardrails.py` | Pass |
| Tree traversal bounded | `test_tree_traversal.py` | Pass |

### 4. Exec and Session Management

| Criterion | Test Suite | Result |
|-----------|-----------|--------|
| Exec client lifecycle | `test_exec_client.py` | Pass |
| Exec policy enforcement | `test_exec_policy.py` | Pass |
| Session token management | `test_session_tokens.py` | Pass |
| PTY bridge WS handling | `test_pty_bridge.py` | Pass |
| Chat bridge WS handling | `test_chat_bridge.py` | Pass |

### 5. Security

| Criterion | Test Suite | Result |
|-----------|-----------|--------|
| Internal auth enforcement | `test_internal_auth.py` | Pass |
| Secret redaction | `test_secret_redaction.py` | Pass |
| Rate limiter | `test_rate_limiter.py` | Pass |
| Path traversal blocked | `test_proxy_guardrails.py` | Pass |
| No upstream error leaks | `test_fault_injection.py::*no_leak*` | Pass |

### 6. WebSocket Lifecycle

| Criterion | Test Suite | Result |
|-----------|-----------|--------|
| WS lifecycle policy | `test_ws_lifecycle.py` | Pass |
| Bounded outbound queue | `test_ws_lifecycle.py` | Pass |
| Midstream disconnect handling | `test_fault_injection.py::TestInjectWsMidstreamDisconnect` | Pass |
| Backpressure simulation | `test_e2e_resilience.py::TestSimulateBackpressure` | Pass |
| WS reconnect simulation | `test_e2e_resilience.py::TestSimulateWsReconnect` | Pass |

### 7. Fault Tolerance

| Criterion | Test Suite | Result |
|-----------|-----------|--------|
| Service 503 handling | `test_fault_injection.py::TestInjectService503` | Pass |
| Exec attach failure | `test_fault_injection.py::TestInjectExecAttachFail` | Pass |
| Rate limit burst (429) | `test_fault_injection.py::TestInjectRateLimitBurst` | Pass |
| Auth expiry (403) | `test_fault_injection.py::TestInjectAuthExpiry` | Pass |
| Provider timeout cascade | `test_fault_injection.py::TestInjectProviderTimeoutCascade` | Pass |
| Health flap active | `test_fault_injection.py::TestInjectHealthFlapActive` | Pass |
| All scenarios deterministic | `test_fault_injection.py::TestScenarioRegistry::test_all_pass_deterministically` | Pass |

### 8. Performance SLOs

| SLO Target | Threshold | Test | Status |
|-----------|-----------|------|--------|
| Readiness latency | <= 5000ms | `test_slo_measurements.py` | Met |
| PTY median latency | <= 150ms | `test_slo_measurements.py` | Met |
| Reattach success rate | >= 99% | `test_slo_measurements.py` | Met |
| Tree p95 multiplier | <= 2x local | `test_slo_measurements.py` | Met |
| Error rate (burst) | <= 2% | `test_slo_measurements.py` | Met |
| Fault tolerance | 100% pass | `test_slo_measurements.py` | Met |

## Known Limitations (V0)

### Architectural

1. **Fixed target only**: V0 supports a single fixed sprite target.
   Dynamic sandbox management deferred to V1 (bd-ptl.2.1).
2. **No session persistence**: Sessions are in-memory only.
   Durable session registry deferred to V1 (bd-ptl.2.2).
3. **Single worker**: Service runs with 1 uvicorn worker.
   Multi-worker support deferred to V1.

### Operational

4. **Manual deploy**: Script-based deployment without CI/CD pipeline.
   Automated release pipeline deferred to V1 (bd-ptl.2.7.6).
5. **No OpenTelemetry**: Observability limited to structured logs.
   Full tracing/metrics deferred to V1 (bd-ptl.2.3.5).
6. **Credential-gated smoke tests**: Live smoke tests skip without
   credentials. Full CI integration requires credential injection.

### Security

7. **No authz hooks**: Authorization is binary (token present/absent).
   Fine-grained authz deferred to V1 (bd-ptl.2.1.4).
8. **No typed error codes**: Error codes are string-based.
   Typed error contract deferred to V1 (bd-ptl.2.1.5).

### Testing

9. **Simulated load**: Performance tests use synthetic latency models,
   not real network traffic. Live load testing requires deployed service.
10. **No flaky test history**: Flaky test tracker starts fresh each run.
    Historical trend persistence not yet implemented.

## Residual Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Fixed target limits horizontal scaling | Medium | V1 dynamic targets |
| In-memory sessions lost on restart | Medium | V1 durable registry |
| No live performance data | Low | Smoke check validates basic health |
| Single point of failure (1 worker) | Medium | V1 multi-worker + load balancing |

## V1 Deferrals

| Feature | Bead | Priority |
|---------|------|----------|
| Sandbox management API | bd-ptl.2.1 | P2 |
| Durable session registry | bd-ptl.2.2 | P2 |
| OpenTelemetry tracing | bd-ptl.2.3.5 | P2 |
| Typed error contract | bd-ptl.2.1.5 | P2 |
| Authz hooks | bd-ptl.2.1.4 | P2 |
| Release pipeline | bd-ptl.2.7.6 | P2 |
| Provider extensibility | bd-ptl.2.6 | P2 |

## Release Decision

**Verdict: GO** — All V0 acceptance criteria are met by deterministic
tests. Known limitations are documented and tracked as V1 deferrals.
SLO measurements confirm performance targets are achievable.
