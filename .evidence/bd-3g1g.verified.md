# bd-3g1g: epic closure evidence

*2026-02-18T12:34:48Z by Showboat 0.5.0*

This evidence confirms all bd-3g1g epic children (phases + tasks) are CLOSED and have EVIDENCE comments.

```python3
import json, pathlib
path = pathlib.Path('.beads/issues.jsonl')
latest = {}
for line in path.read_text().splitlines():
    obj = json.loads(line)
    iid = obj.get('id', '')
    if iid.startswith('bd-3g1g.'):
        latest[iid] = obj

checked = []
problems = []
for iid in sorted(latest):
    checked.append(iid)
    obj = latest[iid]
    if obj.get('status') != 'closed':
        problems.append((iid, 'status', obj.get('status')))
    comments = obj.get('comments') or []
    has_evidence = any(('EVIDENCE:' in (c.get('text', '') or '')) for c in comments)
    if not has_evidence:
        problems.append((iid, 'evidence_comment', 'missing'))

print('children', len(checked))
print('problems', len(problems))
for p in problems:
    print(*p)

```

```output
children 39
problems 0
```
