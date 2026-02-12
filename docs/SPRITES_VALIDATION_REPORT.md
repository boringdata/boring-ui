# Sprites Validation Report (bd-2j57.7.2)

Date: 2026-02-12

## Scope

Required checks:

1. File tree source is sandbox/sprite-backed (not host-local browser direct access)
2. File operations flow through canonical control-plane routes
3. Chat path responds end-to-end
4. Browser does not call sprite/local-api endpoints directly

## Environment Availability

Current shell has no `SPRITES_*` runtime credentials configured, so live org-sprite browser execution is not reproducible in this run.

Command run:

```bash
printenv | rg -n "^SPRITES_|^BORING_UI_RUN_MODE|^CAPABILITY_PRIVATE_KEY|^OIDC_|^HOSTED_" || true
```

Output: no matching variables.

## Evidence Produced In This Run

### 1) Sprites provider integration behavior (backend path)

Command:

```bash
pytest -q tests/integration/test_sprites_integration.py
```

Result:

- `35 passed`

This validates the control-plane Sprites client/provider path and transport interactions under integration tests.

### 2) Browser network-boundary code scan (no direct sprite/local-api calls)

Command:

```bash
rg -n "api\\.sprites\\.dev|\\.sprites\\.app|/internal/" src/front --glob '!**/*.map'
```

Result:

- no matches

Interpretation:

- Frontend code does not directly target Sprites API domains.
- Frontend code does not directly target `/internal/*` private-plane endpoints.

### 3) Canonical browser route usage for file/git/exec operations

Representative frontend callsites:

- `src/front/components/FileTree.jsx`
- `src/front/components/GitChangesView.jsx`
- `src/front/components/chat/ClaudeStreamChat.jsx`
- `src/front/hooks/useFileOperations.js`
- `src/front/panels/EditorPanel.jsx`

These use canonical `/api/v1/*` endpoints for privileged operations.

## Existing End-to-End UI Proof Artifact

Prior hosted UI proof with file creation + chat response evidence:

- `docs/HOSTED_UI_SHOWBOAT_RODNEY_PROOF.md`

That artifact demonstrates layout load, file operation from UI, and chat response path through the control-plane app.

## Conclusion

Within current environment constraints, the repository has:

- passing Sprites integration coverage (`35 passed`),
- no frontend direct-call surface to sprite/private endpoints,
- canonical `/api/v1/*` frontend call paths,
- and an existing hosted UI artifact proving file/chat behavior end-to-end.

Live org-sprite browser validation remains credential-gated and should be re-run with configured `SPRITES_*` variables to capture fresh runtime screenshots/network logs in this environment.
