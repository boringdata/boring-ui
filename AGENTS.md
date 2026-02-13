

<!-- br-agent-instructions-v1 -->

---

## Beads Workflow Integration

This project uses [beads_rust](https://github.com/Dicklesworthstone/beads_rust) (`br`/`bd`) for issue tracking. Issues are stored in `.beads/` and tracked in git.

### Essential Commands

```bash
# View ready issues (unblocked, not deferred)
br ready              # or: bd ready

# List and search
br list --status=open # All open issues
br show <id>          # Full issue details with dependencies
br search "keyword"   # Full-text search

# Create and update
br create --title="..." --description="..." --type=task --priority=2
br update <id> --status=in_progress
br close <id> --reason="Completed"
br close <id1> <id2>  # Close multiple issues at once

# Sync with git
br sync --flush-only  # Export DB to JSONL
br sync --status      # Check sync status
```

### Workflow Pattern

1. **Start**: Run `br ready` to find actionable work
2. **Claim**: Use `br update <id> --status=in_progress`
3. **Work**: Implement the task
4. **Complete**: Use `br close <id>`
5. **Sync**: Always run `br sync --flush-only` at session end

### Key Concepts

- **Dependencies**: Issues can block other issues. `br ready` shows only unblocked work.
- **Priority**: P0=critical, P1=high, P2=medium, P3=low, P4=backlog (use numbers 0-4, not words)
- **Types**: task, bug, feature, epic, chore, docs, question
- **Blocking**: `br dep add <issue> <depends-on>` to add dependencies

### Session Protocol

**Before ending any session, run this checklist:**

```bash
git status              # Check what changed
git add <files>         # Stage code changes
br sync --flush-only    # Export beads changes to JSONL
git commit -m "..."     # Commit everything
git push                # Push to remote
```

### Best Practices

- Check `br ready` at session start to find available work
- Update status as you work (in_progress → closed)
- Create new issues with `br create` when you discover tasks
- Use descriptive titles and set appropriate priority/type
- Always sync before ending session

### Definition Of Done (DoD Template, Required)

All new issues created on/after `2026-02-13T22:00:00Z` must include the DoD sections below in the issue **description**. New issues are blocked from being merged/closed without these sections being present.

Template (copy into every new bead description and fill it in as you work):

````md
## Acceptance Criteria
- [ ] User-visible behaviors (what should happen, status codes, UI state, etc.)

## Evidence
- Commit(s): <git sha(s)> (or PR: <link>)
- If UI changed: screenshots or screen recording path(s)
- If bug: exact repro steps + input + expected vs actual

## Verification
Commands:
```bash
# paste exact commands run (tests/lints/builds)
```
Expected:
- What "success" looks like (exit code, key output lines, URLs, screenshots, etc.)

## Rollback
- If this breaks: revert commit(s) <sha> (or PR) and/or revert files:
- Risk notes (what might regress / what to watch)
````

Automated check:
- `python3 scripts/validate_beads_dod.py`

### Supabase Credentials (How To Get)

Fetch credentials from the agent secret store using these paths:

- `Project URL`: `secret/agent/boring-ui-supabase-project-url`
- `Publishable key`: `secret/agent/boring-ui-supabase-publishable-key`
- `Service role key`: `secret/agent/boring-ui-supabase-service-role-key`
- `DB password`: `secret/agent/boring-ui-supabase`
- `DB connection URL`: `secret/agent/boring-ui-supabase-db-url`

Recommended env var mapping:

- `SUPABASE_URL` <= `secret/agent/boring-ui-supabase-project-url`
- `SUPABASE_PUBLISHABLE_KEY` <= `secret/agent/boring-ui-supabase-publishable-key`
- `SUPABASE_SERVICE_ROLE_KEY` <= `secret/agent/boring-ui-supabase-service-role-key`
- `SUPABASE_DB_PASSWORD` <= `secret/agent/boring-ui-supabase`
- `DATABASE_URL` <= `secret/agent/boring-ui-supabase-db-url`

Security notes:

- Never commit secret values to git, issue comments, logs, or screenshots.
- Keep values in environment variables or local untracked `.env` files only.
- Rotate and re-fetch secrets if exposure is suspected.

<!-- end-br-agent-instructions -->
