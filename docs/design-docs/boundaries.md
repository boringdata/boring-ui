# Boundaries

Hard constraints on what boring-ui will NOT do.

## Scope Boundaries

1. **Not a full IDE**: boring-ui provides an IDE-like shell (file tree, editor, terminal, chat). It does not implement language servers, debuggers, or build system integration. These are extension points, not core features.

2. **Not a control plane**: Auth, session management, workspace lifecycle, and gateway routing belong to boring-sandbox. boring-ui is the UI and runtime backend, not the orchestration layer.

3. **Not a standalone deployment target**: In hosted mode, boring-ui runs behind the boring-sandbox gateway. It does not implement its own auth, user management, or multi-tenancy.

4. **No direct code coupling across front/back**: The frontend must never import backend modules or vice versa. The HTTP/WS API is the only integration surface.

## Design Boundaries

5. **No hardcoded control-plane patterns**: Feature code must not embed gateway URL patterns (e.g., `/w/{id}/...`). Base paths are injected by the hosting runtime via transport helpers.

6. **No broad glob rewrites**: Codemods and "fix everything" scripts require explicit approval. Changes are scoped and incremental.

7. **No file variants**: No `*_v2.*` files. Edit in place. If a module needs to be replaced, remove the old one and add the new one.

8. **No secrets in code**: Credentials come from Vault or environment variables. `.env` files are gitignored. No tokens in commits or logs.

## Runtime Boundaries

9. **Workspace plugins are sandboxed**: Disabled by default. When enabled, guarded by an explicit allowlist. They execute in-process, so the allowlist is a trust boundary.

10. **Agent services don't own filesystem**: Agent runtimes (normal, companion, PI) delegate file/git operations to workspace-core. They cannot bypass path validation or policy checks.

11. **PTY providers are allowlisted**: Only configured providers in `APIConfig.pty_providers` can be spawned. No arbitrary command execution via PTY endpoint.
