

<!-- br-agent-instructions-v1 -->

---

## Beads Workflow Integration

This project uses [beads_rust](https://github.com/Dicklesworthstone/beads_rust) (`br`/`bd`) for issue tracking. Issues are stored in `.beads/` and tracked in git.

### Worker Execution Loop

Repeat until no beads remain:

1. **Pick & claim**: `bv --robot-next` → `br show <id>` (verify acceptance criteria + deps exist, fix before coding) → `br update <id> --claim --actor <name>` + announce in Agent Mail.
2. **Implement**: only the scoped bead — no unrelated refactors, **no stubs** (`pass`, `TODO`, `NotImplementedError`). If a piece can't be completed, split into a new bead. Self-review changed code: "Read over all new code you just wrote and existing code you modified with fresh eyes, looking carefully for any obvious bugs, errors, problems, issues, or confusion. Fix anything you uncover. Use ultrathink." Run verification commands (tests/lints). If no tests exist, add at least one.
3. **Commit & review**: commit only this bead's files (message MUST include bead-id + acceptance criteria). Then request a review: `roborev review HEAD` and iterate — read the review with `roborev show HEAD`, fix findings, commit the fix, review again — until the review passes (max 10 iterations). Use a cross-model reviewer (CC workers → `--agent codex`, Codex workers → `--agent claude`).
4. **Prove**: build evidence with Showboat (see guidelines below). `showboat verify` before closing. Link to bead: `br comments add <id> --message "EVIDENCE: .evidence/<bead-id>.md; review=roborev-passed"`.
5. **Close & notify**: `br close <id> --reason "implemented + reviewed + verified" --actor <name>`. Send Agent Mail summary (what changed, commit hash). Loop back to step 1.

### Evidence & Proof (Showboat + Rodney)

Use [Showboat](https://simonwillison.net/2026/Feb/10/showboat-and-rodney/) to capture proof, [Rodney](https://github.com/simonw/rodney) for visual proof via CLI browser automation ([blog post](https://simonwillison.net/2026/Feb/10/showboat-and-rodney/)). Run `showboat --help` / `rodney --help` for full usage.

**Rodney** is a CLI browser tool (Chrome DevTools Protocol via Rod). Key commands: `rodney start`, `rodney open <url>`, `rodney screenshot <file>`, `rodney click '<selector>'`, `rodney js '<code>'`, `rodney stop`. Install: `uvx rodney` or `uv tool install rodney`.

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

<!-- end-br-agent-instructions -->
