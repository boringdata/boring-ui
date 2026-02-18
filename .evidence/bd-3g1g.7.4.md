# bd-3g1g.7.4: epic completion audit

*2026-02-18T12:32:32Z by Showboat 0.5.0*

This evidence proves all non-parent children in the bd-3g1g epic are CLOSED with EVIDENCE comments, so the remaining parent/closure beads can be safely closed.

```python3
import json, pathlib
path = pathlib.Path('.beads/issues.jsonl')
latest = {}
for line in path.read_text().splitlines():
    obj = json.loads(line)
    iid = obj.get('id', '')
    if iid.startswith('bd-3g1g'):
        latest[iid] = obj

exclude = {'bd-3g1g', 'bd-3g1g.7', 'bd-3g1g.7.4'}
checked = []
problems = []
for iid in sorted(latest):
    if iid in exclude:
        continue
    checked.append(iid)
    obj = latest[iid]
    if obj.get('status') != 'closed':
        problems.append((iid, 'status', obj.get('status')))
    comments = obj.get('comments') or []
    has_evidence = any(('EVIDENCE:' in (c.get('text', '') or '')) for c in comments)
    if not has_evidence:
        problems.append((iid, 'evidence_comment', 'missing'))

print('checked', len(checked))
print('problems', len(problems))
for p in problems:
    print(*p)

```

```output
checked 37
problems 0
```
