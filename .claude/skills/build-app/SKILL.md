---
name: build-app
description: Create, build, and deploy a new boring-ui child app from a feature description. Use when the user wants to create a new app, build a new child app, or deploy a new project.
argument-hint: "[feature description]"
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent, AskUserQuestion
---

# Build a boring-ui child app

## Phase 1: Requirements

The user wants: $ARGUMENTS

Interview the user (2-4 rounds with AskUserQuestion) to clarify:
- What custom panels and backend endpoints to build
- Data storage needs (in-memory, database, external API)
- Auth requirements (multi-user with Neon, or single-user)

Summarize and get confirmation before building.

## Phase 2: Build

Generate app identity, then use `bui --help` and `bui docs quickstart` to discover the workflow.

```python
python3 -c "
from tests.eval.contracts import NamingContract, RunManifest
import json
nc = NamingContract.from_eval_id()
m = RunManifest.from_naming(nc, platform_profile='core')
print(json.dumps({
    'app_slug': nc.app_slug, 'eval_id': nc.eval_id,
    'python_module': nc.python_module, 'project_root': nc.project_root,
    'verification_nonce': m.verification_nonce,
    'report_output_path': m.report_output_path,
}, indent=2))
"
```

Build the app following `bui docs quickstart`. Include a status router with:
- `GET /health` → `{"ok": true, "app": "<slug>", "custom": true, "eval_id": "<id>", "verification_nonce": "<nonce>"}`
- `GET /info` → `{"name": "<slug>", "version": "0.1.0", "eval_id": "<id>"}`

## Phase 3: Acceptance criteria

The app is NOT done until ALL of these pass. Run each check and report pass/fail.

### Local (before deploy)
- [ ] `bui doctor` exits 0
- [ ] `GET /health` returns JSON with correct verification_nonce
- [ ] `GET /info` returns JSON with correct eval_id
- [ ] All custom endpoints return correct responses
- [ ] No secrets hardcoded in source files

### Deploy
- [ ] `bui neon setup` completes (auth + email auto-configured)
- [ ] `bui deploy` completes with healthy machines
- [ ] App reachable at `https://<slug>.fly.dev`

### Live smoke (after deploy)
- [ ] `GET https://<slug>.fly.dev/health` returns JSON with verification_nonce
- [ ] `GET https://<slug>.fly.dev/info` returns JSON with eval_id
- [ ] `GET https://<slug>.fly.dev/api/capabilities` shows `auth.provider = "neon"`
- [ ] All custom endpoints work live
- [ ] Signup returns 200: `curl -X POST https://<slug>.fly.dev/auth/sign-up -H "Content-Type: application/json" -H "Origin: https://<slug>.fly.dev" -d '{"email":"eval@test.local","password":"eval-2026","name":"Test"}'`
- [ ] Signin returns 200: `curl -X POST https://<slug>.fly.dev/auth/sign-in -H "Content-Type: application/json" -H "Origin: https://<slug>.fly.dev" -d '{"email":"eval@test.local","password":"eval-2026"}'`

If any check fails, fix and re-check. Do not write the report until all pass.

## Phase 4: Report

```
BEGIN_EVAL_REPORT_JSON
{
  "eval_id": "<eval_id>",
  "verification_nonce": "<nonce>",
  "app_slug": "<slug>",
  "project_root": "<root>",
  "deployed_url": "https://<slug>.fly.dev",
  "fly_app_name": "<slug>",
  "neon_project_id": "...",
  "commands_run": ["..."],
  "acceptance_criteria": {
    "doctor_pass": true,
    "local_health": true,
    "local_info": true,
    "local_custom_endpoints": true,
    "no_hardcoded_secrets": true,
    "neon_setup": true,
    "deploy_healthy": true,
    "live_health": true,
    "live_info": true,
    "live_capabilities_neon": true,
    "live_custom_endpoints": true,
    "live_signup": true,
    "live_signin": true
  },
  "failures": [],
  "known_issues": []
}
END_EVAL_REPORT_JSON
```

Write to: `<report_output_path>`
