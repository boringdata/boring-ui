# Control Plane SLO and Alert Contract (Feature 3 V0)

This document captures the concrete implementation for bead `bd-223o.15.1`.

Source of truth:
- `src/control_plane/app/operations/slo_alerts.py`

It codifies section 17.2 of `docs/ideas/feature-3-external-control-plane-with-auth.md` into:
1. Machine-readable SLO targets.
2. Alert rules with thresholds, windows, owners, and escalation actions.
3. Required dashboard panel coverage for availability, provisioning reliability, and tenant safety.

## SLO Targets
1. API availability SLO:
- target: `99.5%`
- window: `30d`
- scope: control-plane auth/workspace APIs
2. Provisioning reliability SLO:
- target: `99.0%` (`>=99%` contract)
- window: `30d`
- scope: valid-release provisioning jobs

## Alert Set
1. `api_5xx_error_rate_burn`
- threshold: `>2%`
- window: `5m`
- owner: `backend_oncall_owner`
2. `provisioning_error_rate_burn`
- threshold: `>5%`
- window: `15m`
- grouped by: `last_error_code`
- owner: `runtime_owner`
3. `tenant_isolation_violation`
- condition: any confirmed cross-workspace incident
- severity: `SEV-1` (immediate)
- mandatory actions:
  - freeze rollout
  - rotate affected credentials
  - publish incident summary

## Dashboard Coverage Contract
Required panels:
1. `api_availability_monthly`
2. `api_5xx_error_rate_5m`
3. `provisioning_success_rate_30d`
4. `provisioning_error_rate_15m_by_code`
5. `tenant_isolation_incidents`

## Escalation Owner Model
1. control-plane/API failures: `backend_oncall_owner`
2. Supabase auth/RLS failures: `database_platform_owner`
3. Sprite runtime/proxy failures: `runtime_owner`

## Validation
Run:

```bash
pytest -q tests/unit/control_plane/test_slo_alerts.py
```

Validation fails if required SLO keys, alert thresholds/windows, dashboard coverage, or owner mapping drift from the contract.
