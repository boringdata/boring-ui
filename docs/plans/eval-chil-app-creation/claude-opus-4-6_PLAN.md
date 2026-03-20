# Eval: End-to-End Child App Creation & Deployment

## Context

Automated evaluation harness that tests whether an AI agent can create, configure, and deploy a new boring-ui child app from scratch. The eval:
1. Generates a prompt that instructs an agent to use `bui init`, configure Vault secrets, add a custom router, run `bui neon setup`, and `bui deploy`
2. Runs a verification harness against the result (local files + live deployment)
3. Scores the agent across scaffolding, local-dev, deployment, functionality, and security
4. Cleans up all resources (Modal app, Neon project, local files)

---

## File Structure

```
tests/eval/
  __init__.py
  eval_child_app.py          # Orchestrator: prompt -> verify -> score -> cleanup
  agent_prompt.py             # Generates the agent prompt template
  checks/
    __init__.py
    scaffolding.py            # Phase A: local file structure checks
    local_dev.py              # Phase B: bui doctor + dev server health
    deployment.py             # Phase C: live deployment smoke (reuses smoke_lib)
    security.py               # Phase D: no leaked secrets, best practices
  scoring.py                  # Weighted scoring + gate thresholds
  cleanup.py                  # Teardown: Neon, Modal, Vault, local files
```

---

## Phase A: Agent Prompt (`agent_prompt.py`)

Generates a self-contained prompt with a timestamped app name (`eval-{ts}`). The prompt instructs the agent to:

1. **Scaffold**: `bui init eval-{ts}` in `/home/ubuntu/projects/`
2. **Configure .env**: Fetch `ANTHROPIC_API_KEY` from Vault, set `BORING_UI_SESSION_SECRET`
3. **Add custom router**: Create `src/eval_{ts_under}/routers/status.py` with:
   - `GET /health` -> `{"ok": true, "app": "eval-{ts}", "custom": true}`
   - `GET /info` -> `{"name": "eval-{ts}", "version": "0.1.0"}`
   - Mount it in `boring.app.toml` `[backend].routers`
4. **Doctor**: Run `bui doctor` to validate setup
5. **Neon setup**: Run `bui neon setup` to provision DB + auth
6. **Configure deploy**: Set `[deploy].platform = "modal"`, `[deploy.modal].app_name`, branding
7. **Deploy**: Run `bui deploy`
8. **Report**: Output the deployed URL and Neon project ID

Constraints embedded in prompt:
- Do NOT modify `../boring-ui/`
- Do NOT hardcode secrets in committed files
- Use only `bui` CLI for all operations

---

## Phase B: Verification Checks

### B1 - Scaffolding (`checks/scaffolding.py`) — weight ~37

| Check | W | What |
|-------|---|------|
| `scaff.dir_exists` | 3 | Project dir exists |
| `scaff.toml_exists` | 3 | `boring.app.toml` present |
| `scaff.toml_valid` | 3 | Parses with `tomllib` |
| `scaff.toml_name` | 2 | `[app].name` matches |
| `scaff.toml_id` | 2 | `[app].id` matches |
| `scaff.pyproject` | 2 | `pyproject.toml` valid |
| `scaff.app_entry` | 3 | `src/<pyname>/app.py` exists and has `create_app` |
| `scaff.routers_dir` | 1 | `src/<pyname>/routers/` exists |
| `scaff.custom_router` | 3 | `status.py` defines both endpoints |
| `scaff.custom_mounted` | 3 | Router referenced in TOML `[backend].routers` or `app.py` |
| `scaff.gitignore` | 2 | `.gitignore` includes `.env`, `__pycache__` |
| `scaff.env_file` | 2 | `.env` exists and is non-empty |
| `scaff.env_in_gitignore` | 3 | `.env` listed in `.gitignore` |
| `scaff.panels_dir` | 1 | `panels/` exists |
| `scaff.frontend_branding` | 2 | `[frontend.branding].name` set |
| `scaff.deploy_platform` | 2 | `[deploy].platform` set to "modal" |

### B2 - Local Dev (`checks/local_dev.py`) — weight ~31

| Check | W | What |
|-------|---|------|
| `local.doctor_exit_0` | 5 | `bui doctor` exits 0 |
| `local.doctor_no_errors` | 3 | No ERROR lines in output |
| `local.dev_starts` | 5 | `bui dev --backend-only` starts, `/health` responds within 30s |
| `local.dev_config` | 2 | `/api/config` returns valid JSON |
| `local.dev_capabilities` | 3 | `/api/capabilities` has `features` + `routers` keys |
| `local.dev_custom_health` | 4 | Custom router `/health` returns `{"ok": true, "custom": true}` |
| `local.dev_custom_info` | 3 | Custom router `/info` returns correct name+version |
| `local.dev_auth_provider` | 2 | Capabilities auth.provider matches TOML |
| `local.dev_clean_shutdown` | 2 | Dev server shuts down on SIGTERM without error |
| `local.dev_no_stderr_errors` | 2 | No Python tracebacks in stderr |

### B3 - Deployment (`checks/deployment.py`) — weight ~70

Reuses `smoke_lib.SmokeClient`, `smoke_lib.session_bootstrap`, `smoke_lib.workspace`, `smoke_lib.files`, `smoke_lib.git`.

| Check | W | What |
|-------|---|------|
| `deploy.neon_configured` | 3 | TOML has `[deploy.neon].project` non-empty |
| `deploy.neon_jwks_reachable` | 3 | JWKS URL responds 200 |
| `deploy.secrets_valid` | 3 | `[deploy.secrets]` entries have `vault` + `field` |
| `deploy.modal_app_exists` | 5 | `modal app list` shows the app |
| `deploy.health_200` | 5 | `GET /health` -> 200 |
| `deploy.config_200` | 3 | `GET /api/config` -> valid JSON |
| `deploy.caps_200` | 3 | `GET /api/capabilities` -> valid JSON |
| `deploy.caps_auth_neon` | 3 | Capabilities auth.provider == "neon" |
| `deploy.caps_features` | 2 | Capabilities has `files` feature |
| `deploy.branding_match` | 2 | Capabilities branding matches TOML |
| `deploy.auth_signup` | 4 | Neon signup creates account (via `smoke_lib.auth`) |
| `deploy.auth_signin` | 4 | Neon signin returns `boring_session` cookie |
| `deploy.session_valid` | 3 | `/api/v1/me` returns user info |
| `deploy.workspace_create` | 4 | Workspace creation succeeds |
| `deploy.file_write` | 3 | File write in workspace |
| `deploy.file_read` | 3 | File read-back matches |
| `deploy.file_delete` | 2 | File delete succeeds |
| `deploy.git_cycle` | 3 | Init + add + commit cycle works |
| `deploy.custom_router_live` | 4 | Custom router responds on live app |
| `deploy.frontend_html` | 3 | `GET /` returns HTML with `id="root"` |
| `deploy.auth_logout` | 2 | Logout invalidates session |
| `deploy.auth_guard` | 2 | Unauthenticated request to `/api/v1/me` returns 401 |

### B4 - Security (`checks/security.py`) — weight ~29

| Check | W | What |
|-------|---|------|
| `sec.no_secrets_in_toml` | 5 | No literal API keys in `boring.app.toml` (regex: `sk-ant-`, `Bearer`, passwords) |
| `sec.no_secrets_in_source` | 5 | No hardcoded keys in `src/**/*.py` |
| `sec.env_not_tracked` | 4 | `.env` not in git index |
| `sec.session_secret_vault_ref` | 4 | Deploy secrets use Vault ref for session secret, not literal |
| `sec.vault_refs_complete` | 3 | All `[deploy.secrets]` have both `vault` and `field` |
| `sec.gitignore_boring_dir` | 2 | `.boring/` in `.gitignore` |
| `sec.pyproject_version` | 1 | `pyproject.toml` has version |
| `sec.backend_entry_valid` | 2 | `[backend].entry` resolves to real file |
| `sec.auth_provider_neon` | 3 | Auth set to "neon" not "local" for deployed app |

---

## Phase C: Scoring (`scoring.py`)

```
Categories + weights toward overall:
  scaffolding  20%  (gate: 70%)
  local_dev    20%  (gate: 50%)
  deployment   40%  (gate: 40%)
  security     20%  (gate: 60%)
```

- Category score = sum(passed check weights) / sum(all check weights) * 100
- Gate = minimum category score to not flag critical failure
- Overall = weighted average of category scores
- Result: PASS (overall >= 70, all gates met), PARTIAL (overall >= 50), FAIL

---

## Phase D: Cleanup (`cleanup.py`)

Each step independent (try/except), all run even if earlier steps fail:

1. `modal app stop eval-{ts}` — stop Modal app
2. `bui neon destroy --force` — delete Neon project + Vault secrets
3. `shutil.rmtree(project_root)` — delete local files
4. Collect + report any cleanup errors in evidence

---

## Phase E: Orchestrator (`eval_child_app.py`)

```
1. Generate eval_id = "eval-{unix_ts}"
2. Generate agent prompt from template
3. Launch agent (pluggable callback — Claude Code subprocess, API, or mock)
4. Wait for completion or timeout (default 15min)
5. Extract deployed_url from agent output
6. Run Phase B checks in order: scaffolding -> local_dev -> deployment -> security
   - Skip local_dev if scaffolding gate fails
   - Skip deployment if no deployed URL
   - Security always runs
7. Compute scores
8. Write evidence JSON (compatible with smoke_lib report format)
9. Run cleanup (unless --skip-cleanup)
10. Print summary + return exit code
```

CLI:
```bash
python tests/eval/eval_child_app.py                        # Full eval
python tests/eval/eval_child_app.py --skip-deploy          # Local-only (fast)
python tests/eval/eval_child_app.py --skip-cleanup         # Keep resources for debugging
python tests/eval/eval_child_app.py --eval-id eval-test-1  # Custom ID
python tests/eval/eval_child_app.py --evidence-dir ./out   # Custom evidence path
python tests/eval/eval_child_app.py --agent-timeout 600    # Custom timeout
```

---

## Key Files to Reuse

| Purpose | Path |
|---------|------|
| HTTP client + recording | `tests/smoke/smoke_lib/client.py` (SmokeClient, StepResult) |
| Neon auth flows | `tests/smoke/smoke_lib/auth.py` |
| Session bootstrap | `tests/smoke/smoke_lib/session_bootstrap.py` |
| Workspace helpers | `tests/smoke/smoke_lib/workspace.py` |
| File CRUD helpers | `tests/smoke/smoke_lib/files.py` |
| Git cycle helpers | `tests/smoke/smoke_lib/git.py` |
| Vault secret access | `tests/smoke/smoke_lib/secrets.py` |
| Runner pattern | `tests/smoke/run_all.py` |
| Existing child app smoke | `tests/smoke/smoke_child_app.py` |
| Root TOML example | `boring.app.toml` |
| Go child app example | `examples/child-app-go/boring.app.toml` |

---

## Evidence Output

```json
{
  "eval_id": "eval-1742472000",
  "timestamp": "2026-03-20T12:00:00Z",
  "overall_score": 87.5,
  "overall_pass": true,
  "categories": {
    "scaffolding": {"score": 95.0, "gate_met": true},
    "local_dev": {"score": 90.0, "gate_met": true},
    "deployment": {"score": 82.0, "gate_met": true},
    "security": {"score": 86.0, "gate_met": true}
  },
  "checks": [
    {"id": "scaff.dir_exists", "category": "scaffolding", "weight": 3, "passed": true, "detail": ""}
  ],
  "deployed_url": "https://...",
  "cleanup_errors": [],
  "total_elapsed_s": 423.7
}
```

---

## Verification of the Eval Itself

1. **Unit test the harness**: Run with `--skip-deploy` against a manually-scaffolded app to verify checks work
2. **Dry run**: Run with a mock agent that executes the prompt steps manually, confirm all checks pass
3. **Full run**: Launch with real agent, observe scoring, verify cleanup removes all resources
4. **Idempotency**: Run twice in sequence, confirm no resource collisions (timestamped IDs)
