# bd-3g1g.1.4 Traceability Notes (Plan -> Beads)

Bead: `bd-3g1g.1.4`

Purpose: provide a self-contained traceability map so implementers can execute from beads plus linked artifacts without reopening the source plan documents.

Primary source plan:
- `docs/SERVICE_SPLIT_AND_LEGACY_CLEANUP_PLAN.md`

Supporting artifacts:
- `docs/bd-3g1g-phase0-baseline.md`
- `docs/bd-3g1g-phase1-contract-freeze.md`
- `docs/bd-3g1g.1.2-canonical-ownership-matrix.md`
- `docs/bd-3g1g.1.3-phase-gate-dependency-graph.md`

## Reference Legend

Goals (`## Goals`):
- `G1`: service split by explicit ownership.
- `G2`: control-plane decoupling from feature code.
- `G3`: legacy route/code cleanup with direct cutover.
- `G4`: frontend auth/workspace UX contracts (sidebar user menu).

Non-goals (`## Non-Goals (This Plan)`):
- `N1`: no unrelated UI behavior rewrites.
- `N2`: no new providers beyond normal/companion/pi.
- `N3`: no workspace-core internal rewrites beyond boundary/policy correctness.

Architecture rules (`## Architecture Rules`):
- `AR1`: no hardcoded control-plane patterns in feature code.
- `AR2`: frontend networking goes through shared transport helpers.
- `AR3`: base path/workspace prefix is runtime-injected.
- `AR4`: companion/pi remain agent-domain runtime services.
- `AR5`: workspace-core is sole filesystem/git owner.
- `AR6`: pty-service is sole PTY/terminal WS owner.
- `AR7`: one canonical HTTP versioning + error envelope policy.
- `AR8`: user/session/workspace UI uses canonical control-plane APIs only.

Service boundaries (`## Service Boundaries` + boundary enforcement):
- `SB1`: `front`.
- `SB2`: `workspace-core`.
- `SB3`: `pty-service`.
- `SB4`: `agent-normal`.
- `SB5`: `agent-companion`.
- `SB6`: `agent-pi`.

Risks (`## Risks and Mitigations`):
- `R1`: hidden legacy callsites.
- `R2`: mixed-mode migration regressions.
- `R3`: scope/policy drift.
- `R4`: transport boot timing races.

Verification matrix (`## Verification Matrix`):
- `VM1`: static checks for forbidden direct routes.
- `VM2`: contract/unit tests.
- `VM3`: integration tests for delegated actions.
- `VM4`: failure-path tests.
- `VM5`: performance smoke.
- `VM6`: UX smoke.

## Bead Traceability Matrix (Phase + Subtask)

| Bead | Why this exists | Goals | Non-goals | Architecture + boundaries | Risks | Verification matrix | Evidence + linked artifacts |
|---|---|---|---|---|---|---|---|
| `bd-3g1g.1` | establish complete baseline and executable graph before implementation | `G1,G2,G3` | `N1,N2,N3` | `AR1,AR2,AR3,SB1,SB2,SB3` | `R1,R2` | `VM1,VM2` | unit + integration + e2e + logging evidence package (`.evidence/bd-3g1g.1*.md`) |
| `bd-3g1g.1.1` | inventory all route/callsite families to remove unknown ownership | `G1,G2,G3` | `N1,N2,N3` | `AR1,AR2,SB1,SB2,SB3,SB4,SB5,SB6` | `R1` | `VM1,VM2` | `docs/ROUTE_CALLSITE_INVENTORY_bd-3g1g.1.1.md`, `tests/unit/test_bd_3g1g_1_1_route_inventory.py`, `.evidence/bd-3g1g.1.1.md` |
| `bd-3g1g.1.2` | freeze current-to-canonical ownership/disposition matrix | `G1,G2,G3` | `N1,N2,N3` | `AR1,AR5,AR6,SB1,SB2,SB3,SB4,SB5,SB6` | `R1,R2` | `VM1,VM2` | `docs/bd-3g1g.1.2-canonical-ownership-matrix.md`, `tests/unit/test_bd_3g1g_1_2_canonical_ownership_matrix.py`, `.evidence/bd-3g1g.1.2.md` |
| `bd-3g1g.1.3` | encode phase gates as hard dependencies | `G1,G2,G3` | `N1,N2,N3` | `AR1,AR2,AR5,AR6,SB1,SB2,SB3` | `R2,R4` | `VM1,VM2` | `docs/bd-3g1g.1.3-phase-gate-dependency-graph.md`, `tests/unit/test_bd_3g1g_1_3_phase_gate_dependencies.py`, `.evidence/bd-3g1g.1.3.md` |
| `bd-3g1g.1.4` | preserve plan rationale inside bead workflow artifacts | `G1,G2,G3,G4` | `N1,N2,N3` | `AR1,AR2,AR5,AR6,AR8,SB1,SB2,SB3` | `R1,R2,R3,R4` | `VM1,VM2,VM3,VM4,VM5,VM6` | `docs/bd-3g1g.1.4-traceability-notes.md`, `tests/unit/test_bd_3g1g_1_4_traceability_notes.py`, `.evidence/bd-3g1g.1.4.md` |
| `bd-3g1g.2` | freeze contracts before transport or ownership implementation | `G1,G2,G3` | `N1,N2,N3` | `AR5,AR6,AR7,SB2,SB3,SB4,SB5,SB6` | `R2,R3` | `VM2,VM4` | unit + integration + e2e + logging evidence package (`.evidence/bd-3g1g.2*.md`) |
| `bd-3g1g.2.1` | finalize canonical normal/companion/pi route families | `G1,G2,G3` | `N2` | `AR4,AR7,SB4,SB5,SB6` | `R2` | `VM2` | `docs/SERVICE_SPLIT_AND_LEGACY_CLEANUP_PLAN.md` (finalized section), `tests/unit/test_bd_3g1g_2_1_agent_prefix_contract.py`, `.evidence/bd-3g1g.2.1.md` |
| `bd-3g1g.2.2` | define deny-by-default claim model for owner services | `G1,G2,G3` | `N3` | `AR5,AR6,AR7,SB2,SB3` | `R3` | `VM2,VM4` | `docs/bd-3g1g.2.2-scope-capability-claim-model.md`, `tests/unit/test_bd_3g1g_2_2_scope_claim_model.py`, `.evidence/bd-3g1g.2.2.md` |
| `bd-3g1g.2.3` | standardize HTTP error envelope + retry-safe mutation semantics | `G1,G2,G3` | `N3` | `AR7,SB2,SB3,SB4,SB5,SB6` | `R2,R3` | `VM2,VM4` | phase-1 contract artifact updates + guard tests + `.evidence/bd-3g1g.2.3.md` |
| `bd-3g1g.2.4` | publish versioned contract pack + sign-off baseline | `G1,G2,G3,G4` | `N1,N2,N3` | `AR1,AR2,AR5,AR6,AR7,AR8,SB1,SB2,SB3,SB4,SB5,SB6` | `R2,R3` | `VM2,VM4,VM6` | contract pack snapshot docs + sign-off record + `.evidence/bd-3g1g.2.4.md` |
| `bd-3g1g.3` | enforce shared frontend transport boundary | `G2,G3` | `N1,N2` | `AR1,AR2,AR3,SB1` | `R1,R2,R4` | `VM1,VM2,VM6` | unit + integration + e2e + logging evidence package (`.evidence/bd-3g1g.3*.md`) |
| `bd-3g1g.3.1` | migrate live callsites to shared helpers | `G2,G3` | `N1,N2` | `AR1,AR2,AR3,SB1` | `R1,R4` | `VM1,VM2` | `src/front/utils/transport.js`, `src/front/utils/apiBase.js`, `src/front/utils/transport.test.js`, `.evidence/bd-3g1g.3.1.md` |
| `bd-3g1g.3.2` | remove remaining direct feature-level route construction | `G2,G3` | `N1,N2` | `AR1,AR2,AR3,SB1` | `R1,R2` | `VM1,VM2` | direct-callsite removals + static assertions + `.evidence/bd-3g1g.3.2.md` |
| `bd-3g1g.3.3` | lock forbidden route literal patterns with static checks | `G2,G3` | `N1,N2` | `AR1,AR2,AR3,SB1` | `R1` | `VM1` | static check scripts/tests + `.evidence/bd-3g1g.3.3.md` |
| `bd-3g1g.3.4` | verify canonical transport behavior regression coverage | `G2,G3` | `N1,N2` | `AR2,AR3,AR7,SB1` | `R2,R4` | `VM2,VM4` | transport regression tests + `.evidence/bd-3g1g.3.4.md` |
| `bd-3g1g.3.5` | enforce initialization gates against boot races | `G2,G3` | `N1,N2` | `AR2,AR3,SB1` | `R4` | `VM2,VM4,VM6` | boot-race tests/checks + `.evidence/bd-3g1g.3.5.md` |
| `bd-3g1g.4` | align sidebar user menu flows to canonical control-plane contracts | `G2,G4` | `N1,N2` | `AR2,AR3,AR8,SB1` | `R2,R4` | `VM2,VM6` | unit + integration + e2e + logging evidence package (`.evidence/bd-3g1g.4*.md`) |
| `bd-3g1g.4.1` | place menu shell in sidebar hierarchy per UX contract | `G4` | `N1` | `AR8,SB1` | `R2` | `VM2,VM6` | `docs/SIDEBAR_USER_MENU_PLAN.md`, menu component/tests, `.evidence/bd-3g1g.4.1.md` |
| `bd-3g1g.4.2` | wire me/workspaces/logout/runtime/settings canonical flows | `G2,G4` | `N1,N2` | `AR2,AR8,SB1` | `R1,R2` | `VM2,VM6` | control-plane flow wiring + integration tests + `.evidence/bd-3g1g.4.2.md` |
| `bd-3g1g.4.3` | implement failure UX without legacy fallback | `G2,G4` | `N1,N2` | `AR1,AR2,AR8,SB1` | `R2,R4` | `VM4,VM6` | failure-state UX tests + `.evidence/bd-3g1g.4.3.md` |
| `bd-3g1g.4.4` | add integration coverage for success/failure menu paths | `G2,G4` | `N1,N2` | `AR2,AR8,SB1` | `R2` | `VM3,VM4,VM6` | integration suite + logs + `.evidence/bd-3g1g.4.4.md` |
| `bd-3g1g.5` | consolidate ownership so workspace-core/pty-service are sole authorities | `G1,G3` | `N2,N3` | `AR5,AR6,AR7,SB2,SB3` | `R1,R3` | `VM2,VM4,VM5` | unit + integration + e2e + logging evidence package (`.evidence/bd-3g1g.5*.md`) |
| `bd-3g1g.5.1` | remove legacy file/git handlers and aliases | `G1,G3` | `N3` | `AR5,SB2` | `R1,R2` | `VM1,VM2` | removed legacy routes + canonical tests + `.evidence/bd-3g1g.5.1.md` |
| `bd-3g1g.5.2` | enforce PTY ownership only in pty-service | `G1,G3` | `N3` | `AR6,SB3` | `R2,R3` | `VM2,VM4` | PTY routing/ownership checks + `.evidence/bd-3g1g.5.2.md` |
| `bd-3g1g.5.3` | align registry/capabilities metadata to canonical ownership | `G1,G3` | `N3` | `AR5,AR6,SB2,SB3` | `R1,R3` | `VM2` | metadata updates + guard tests + `.evidence/bd-3g1g.5.3.md` |
| `bd-3g1g.5.4` | add owner contract tests for workspace-core and pty-service | `G1,G3` | `N3` | `AR5,AR6,AR7,SB2,SB3` | `R2,R3` | `VM2,VM4` | contract suites + `.evidence/bd-3g1g.5.4.md` |
| `bd-3g1g.5.5` | update docs to remove conflicting legacy ownership statements | `G1,G3` | `N1,N2,N3` | `AR5,AR6,AR7,SB2,SB3` | `R1,R2` | `VM1,VM2` | docs updates + verification links + `.evidence/bd-3g1g.5.5.md` |
| `bd-3g1g.6` | keep agent services runtime-only with delegated side effects | `G1,G3` | `N2,N3` | `AR4,AR5,AR6,SB4,SB5,SB6` | `R2,R3` | `VM2,VM3,VM4` | unit + integration + e2e + logging evidence package (`.evidence/bd-3g1g.6*.md`) |
| `bd-3g1g.6.1` | migrate normal agent to delegated workspace/PTY calls | `G1,G3` | `N2,N3` | `AR4,AR5,AR6,SB4` | `R2,R3` | `VM2,VM3,VM4` | delegated normal-agent flows + `.evidence/bd-3g1g.6.1.md` |
| `bd-3g1g.6.2` | migrate companion agent to delegated workspace/PTY calls | `G1,G3` | `N2,N3` | `AR4,AR5,AR6,SB5` | `R2,R3` | `VM2,VM3,VM4` | delegated companion flows + `.evidence/bd-3g1g.6.2.md` |
| `bd-3g1g.6.3` | migrate PI agent to delegated workspace/PTY calls | `G1,G3` | `N2,N3` | `AR4,AR5,AR6,SB6` | `R2,R3` | `VM2,VM3,VM4` | delegated PI flows + `.evidence/bd-3g1g.6.3.md` |
| `bd-3g1g.6.4` | enforce deny-by-default boundary policy behavior | `G1,G3` | `N2,N3` | `AR5,AR6,AR7,SB2,SB3` | `R3` | `VM2,VM4` | boundary policy failure-path tests + `.evidence/bd-3g1g.6.4.md` |
| `bd-3g1g.6.5` | prove delegation parity across all three agent services | `G1,G3` | `N2,N3` | `AR4,AR5,AR6,SB4,SB5,SB6` | `R2,R3` | `VM3,VM4,VM6` | cross-agent integration + e2e logs + `.evidence/bd-3g1g.6.5.md` |
| `bd-3g1g.7` | complete direct cutover and publish auditable closeout | `G1,G2,G3,G4` | `N1,N2,N3` | `AR1,AR2,AR5,AR6,AR7,AR8,SB1,SB2,SB3,SB4,SB5,SB6` | `R1,R2,R3,R4` | `VM1,VM2,VM3,VM4,VM5,VM6` | unit + integration + e2e + logging evidence package (`.evidence/bd-3g1g.7*.md`) |
| `bd-3g1g.7.1` | remove remaining legacy fallback paths | `G2,G3` | `N1,N2` | `AR1,AR2,AR8,SB1,SB2,SB3` | `R1,R2` | `VM1,VM2` | fallback-removal diffs + guard tests + `.evidence/bd-3g1g.7.1.md` |
| `bd-3g1g.7.2` | execute verification matrix and collect evidence bundle | `G1,G2,G3,G4` | `N1,N2,N3` | `AR1,AR2,AR5,AR6,AR8,SB1,SB2,SB3,SB4,SB5,SB6` | `R2,R3,R4` | `VM1,VM2,VM3,VM4,VM5,VM6` | full verification run logs + artifact manifest + `.evidence/bd-3g1g.7.2.md` |
| `bd-3g1g.7.3` | publish final migration summary for maintainers | `G1,G2,G3,G4` | `N1,N2,N3` | `AR5,AR6,AR7,AR8,SB1,SB2,SB3,SB4,SB5,SB6` | `R2` | `VM2,VM6` | closeout summary doc + `.evidence/bd-3g1g.7.3.md` |
| `bd-3g1g.7.4` | audit epic completeness and close orphaned bookkeeping | `G1,G3` | `N1,N2,N3` | `AR5,AR6,AR7,SB1,SB2,SB3,SB4,SB5,SB6` | `R2` | `VM2` | closure audit checklist + `.evidence/bd-3g1g.7.4.md` |
| `bd-3g1g.7.5` | build repeatable verification runner and structured log manifest | `G1,G2,G3,G4` | `N1,N2,N3` | `AR1,AR2,AR7,AR8,SB1,SB2,SB3,SB4,SB5,SB6` | `R2,R4` | `VM1,VM2,VM3,VM4,VM5,VM6` | verification runner + structured logs + `.evidence/bd-3g1g.7.5.md` |

## Usage Guidance for Implementers

1. Start from `br show <bead-id>` and this matrix row for rationale and constraints.
2. Implement only the scoped bead; keep evidence scoped to `.evidence/<bead-id>.md`.
3. For any contract/boundary change, open a new bead instead of drifting scope.
4. Reviewer closure gate: no close without test/log evidence and independent review.
