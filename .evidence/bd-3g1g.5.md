# Evidence: bd-3g1g.5

*2026-02-18T09:36:30Z*

Phase 3 is complete when all Phase 3 child beads (`bd-3g1g.5.1`..`bd-3g1g.5.5`) are closed and their per-bead evidence exists.

```bash
python3 - <<'PY'
import json

ids = [
    "bd-3g1g.5.1",
    "bd-3g1g.5.2",
    "bd-3g1g.5.3",
    "bd-3g1g.5.4",
    "bd-3g1g.5.5",
]

rows = {}
with open(".beads/issues.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        if obj.get("id") in ids:
            rows[obj["id"]] = obj

for issue_id in ids:
    print(f"{issue_id}\t{rows[issue_id]['status']}")

if all(rows[issue_id]["status"] == "closed" for issue_id in ids):
    print("ALL_CLOSED")
PY
```

```output
bd-3g1g.5.1	closed
bd-3g1g.5.2	closed
bd-3g1g.5.3	closed
bd-3g1g.5.4	closed
bd-3g1g.5.5	closed
ALL_CLOSED
```

```bash
ls -1 .evidence/bd-3g1g.5.[1-5].md 2>/dev/null | LC_ALL=C sort
```

```output
.evidence/bd-3g1g.5.1.md
.evidence/bd-3g1g.5.2.md
.evidence/bd-3g1g.5.3.md
.evidence/bd-3g1g.5.4.md
.evidence/bd-3g1g.5.5.md
```
