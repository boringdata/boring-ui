# Strategy and Plan: Eval for Autonomous Child App Creation

## Goal

Design an eval that measures whether an agent can create, configure, deploy, verify, and report on a brand-new children's app using platform credentials from Vault, with a dedicated app name, while following best practices and leaving behind a fully functional result.

## Strategy

This should be an end-to-end autonomy eval, not just a scaffold test.

The agent must:

1. Create a fresh app with a unique dedicated name.
2. Use Vault-backed credentials instead of hardcoded secrets.
3. Configure and deploy the app using supported platform workflows.
4. Verify the app locally and after deployment.
5. Return a concrete operator-grade report with evidence.

The harness must:

1. Generate the dedicated app name.
2. Prompt the agent with explicit constraints.
3. Verify local structure, security hygiene, deployed behavior, and report quality.
4. Score with hard gates and critical auto-fail conditions.
5. Clean up created resources.

## Dedicated Naming Contract

Use a deterministic, unique name per run:

- `child-eval-<unix-ts>`

Derived values:

- app slug: `child-eval-<unix-ts>`
- python module: `child_eval_<unix_ts>`
- deployment app name: `child-eval-<unix-ts>`

## Agent Task Contract

The agent prompt should require the following sequence:

1. Scaffold a new child app with the dedicated name.
2. Keep all changes isolated to the new app directory.
3. Configure the app for a children's experience.
4. Fetch required credentials from Vault or configure Vault-backed deploy secrets.
5. Add custom verification routes.
6. Run local validation.
7. Provision hosted dependencies if required.
8. Deploy the app.
9. Validate the live deployment.
10. Return a final report with exact evidence.

Required custom routes:

- `GET /health` -> `{"ok": true, "app": "<dedicated-name>", "custom": true}`
- `GET /info` -> `{"name": "<dedicated-name>", "audience": "children"}`

## Verification Dimensions

### 1. Build correctness

- project directory exists
- app config exists and parses
- app name matches the prompt
- app entrypoint exists
- custom routes exist
- children's branding or metadata is present

### 2. Secure configuration

- no hardcoded secrets in source or config
- deploy secrets use Vault references
- `.env` is ignored if present
- deployment target config is complete
- auth and backend configuration are internally consistent

### 3. Functional validation

- local validation command succeeds
- local server starts
- local `/health` and `/info` respond correctly
- deployed root URL responds
- deployed `/health` and `/info` respond correctly
- auth or core platform APIs work if required by the scaffold

### 4. Agent behavior quality

- used the dedicated name correctly
- stayed within allowed scope
- performed real verification instead of assuming success
- reported exact evidence
- called out issues or residual risks honestly

## Scoring

| Category | Weight | Gate |
|---|---:|---:|
| Build correctness | 20% | 75% |
| Secure configuration | 25% | 80% |
| Functional validation | 35% | 70% |
| Agent behavior quality | 20% | 70% |

Pass policy:

- `PASS`: overall >= 80 and all gates met
- `PARTIAL`: overall >= 60 and no critical security failure
- `FAIL`: otherwise

Critical auto-fail conditions:

- literal secrets in tracked files
- deployment required but no live URL produced
- live deployment unreachable
- custom verification routes missing
- agent claims success without enough evidence to verify

## Evidence Requirements

The final agent response should include:

- app name
- local project path
- deployed URL
- platform app identifier
- any created database or auth project identifiers
- summary of Vault-backed secret configuration
- validation commands run
- local verification results
- deployed verification results
- known issues or residual risks

The harness should persist:

- raw prompt
- raw agent final response
- scorecard
- command outputs
- key HTTP responses
- cleanup results

## Cleanup

Cleanup should run even on failure and should attempt to remove:

- deployed app
- created backing services
- temporary local project directory

Cleanup errors should be recorded separately from the eval result.

## Implementation Plan

### Phase 1: Prompt design

1. Define the naming contract.
2. Define the exact agent instructions.
3. Define the exact final-response contract.
4. Define explicit allowed and forbidden behaviors.

### Phase 2: Harness

1. Generate `eval_id` and dedicated app name.
2. Launch the agent with the generated prompt.
3. Capture stdout, stderr, exit status, and timeout state.
4. Parse deployment URL and resource identifiers from the response.

### Phase 3: Verification modules

1. Build local scaffold checks.
2. Build security and Vault-reference checks.
3. Build local runtime checks.
4. Build live deployment checks.
5. Build response-quality checks.

### Phase 4: Scoring and gates

1. Implement per-check weights.
2. Implement category gates.
3. Implement critical auto-fail logic.
4. Emit a machine-readable evidence bundle.

### Phase 5: Cleanup and repeatability

1. Tear down all created resources.
2. Ensure timestamped names prevent collisions.
3. Verify reruns are isolated.

## Recommendation

Implement this as a strict end-to-end benchmark where the agent must both do the work and prove it did the work, while the harness independently verifies the result. That is the right shape for measuring real autonomous delivery quality.
