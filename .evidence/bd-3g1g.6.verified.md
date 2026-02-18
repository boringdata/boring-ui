# Evidence: bd-3g1g.6

*2026-02-18T10:34:10Z*

Phase 4 is complete when all Phase 4 child beads (`bd-3g1g.6.1`..`bd-3g1g.6.5`) are closed and their per-bead evidence exists.

```bash
python3 - <<'PY'
import json

ids = [
    "bd-3g1g.6.1",
    "bd-3g1g.6.2",
    "bd-3g1g.6.3",
    "bd-3g1g.6.4",
    "bd-3g1g.6.5",
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
    row = rows.get(issue_id)
    if row is None:
        print(f"{issue_id}\tmissing")
        continue
    print(f"{issue_id}\t{row['status']}")

missing = [issue_id for issue_id in ids if issue_id not in rows]
if missing:
    raise SystemExit(1)

if all(rows[issue_id]["status"] == "closed" for issue_id in ids):
    print("ALL_CLOSED")
else:
    raise SystemExit(1)
PY
```

```output
bd-3g1g.6.1	closed
bd-3g1g.6.2	closed
bd-3g1g.6.3	closed
bd-3g1g.6.4	closed
bd-3g1g.6.5	closed
ALL_CLOSED
```

```bash
ls -1 .evidence/bd-3g1g.6.1*.md .evidence/bd-3g1g.6.2*.md .evidence/bd-3g1g.6.3*.md .evidence/bd-3g1g.6.4*.md .evidence/bd-3g1g.6.5*.md 2>/dev/null | LC_ALL=C sort
```

```output
.evidence/bd-3g1g.6.1.md
.evidence/bd-3g1g.6.1.verified.md
.evidence/bd-3g1g.6.2.md
.evidence/bd-3g1g.6.3.md
.evidence/bd-3g1g.6.3.verified.md
.evidence/bd-3g1g.6.4.md
.evidence/bd-3g1g.6.4.verified.md
.evidence/bd-3g1g.6.5.md
.evidence/bd-3g1g.6.5.verified.md
```
