# bd-3g1g.2.4 Sign-Off Record

Bead: `bd-3g1g.2.4`  
Contract pack: `docs/bd-3g1g.2.4-contract-pack-v1.md`  
Locked baseline version: `v1.0.0`  
Baseline lock date: `2026-02-17` (UTC)

## Approver Record

| Role | Approver | Date (UTC) | Scope |
|---|---|---|---|
| Phase-1 contract owner | `CoralDog` | `2026-02-17` | approved source baselines from `bd-3g1g.2`, `bd-3g1g.2.2`, `bd-3g1g.2.3` |
| Contract-pack publisher | `BrightGorge` | `2026-02-17` | published unified pack + sign-off lock record for `bd-3g1g.2.4` |

## Locked Baseline Scope

The following items are locked for downstream phases unless a revision bead is approved:

1. canonical service ownership map and route families
2. frontend-callable control-plane contract table
3. reserved `/w/{workspace_id}/...` precedence rules
4. explicit not-frontend-callable route families
5. shared error envelope and retry/conflict mutation semantics
6. scope/capability claim requirements for `workspace-core` + `pty-service`

## Revision Rules (Mandatory)

1. Later contract changes require an explicit revision issue; ad-hoc edits are not allowed.
2. Revision issues must update both the contract pack version and this sign-off record.
3. Phase implementation beads (`bd-3g1g.3+`) consume this locked baseline as normative.
