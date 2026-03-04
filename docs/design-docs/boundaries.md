# Boundaries

Hard constraints on what boring-ui will NOT do.

## Scope Boundaries

1. **Not a full IDE**: boring-ui provides an IDE-like shell (file tree, editor, terminal, chat). It does not implement language servers, debuggers, or build system integration. These are extension points, not core features.

2. **Single source of truth for workspace business logic**: Auth/session, user identity, workspace lifecycle, membership/invites, and workspace settings belong to `boring-ui` core.

3. **boring-sandbox is optional edge-only infrastructure**: When present, `boring-sandbox` handles proxy/routing/provisioning/token injection and must not duplicate workspace/user business logic.

4. **No direct code coupling across front/back**: The frontend must never import backend modules or vice versa. The HTTP/WS API is the only integration surface.

## Design Boundaries

5. **No hardcoded hosted-routing patterns**: Feature code must not embed gateway-specific URL assumptions. Base paths are injected by runtime transport helpers.

6. **No broad glob rewrites**: Codemods and "fix everything" scripts require explicit approval. Changes are scoped and incremental.

7. **No file variants**: No `*_v2.*` files. Edit in place. If a module needs to be replaced, remove the old one and add the new one.

8. **No secrets in code**: Credentials come from Vault or environment variables. `.env` files are gitignored. No tokens in commits or logs.

## Runtime Boundaries

9. **Workspace plugins are sandboxed**: Disabled by default. When enabled, guarded by an explicit allowlist. They execute in-process, so the allowlist is a trust boundary.

10. **Filesystem stays workspace-level**: Agent runtimes (normal, companion, PI), `boring-macro`, and `boring-sandbox` do not own filesystem/git authority. They delegate to `workspace-core` in `boring-ui`.

11. **PTY providers are allowlisted**: Only configured providers in `APIConfig.pty_providers` can be spawned. No arbitrary command execution via PTY endpoint.
