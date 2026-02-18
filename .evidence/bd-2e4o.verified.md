# Evidence: bd-2e4o

**

## Problem
`br` CLI started failing with `CONFIG_ERROR` due to invalid JSON in `.beads/issues.jsonl` (corrupt trailing line 620).

## Fix
Removed the single corrupt line so `.beads/issues.jsonl` is valid JSONL again.

## Verification
- JSONL parse check:
  - `python3 -c 'import json; [json.loads(l) for l in open(\".beads/issues.jsonl\") if l.strip()]'` (pass)
- Beads CLI:
  - `br ready` (pass)
