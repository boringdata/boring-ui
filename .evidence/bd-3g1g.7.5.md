# Evidence: bd-3g1g.7.5

*2026-02-18T10:42:32Z by Showboat 0.5.0*

Implements a repeatable verification runner (`scripts/bd_3g1g_verify.py`) that emits structured logs + a machine-readable manifest.

Evidence below shows:
- the runner exposes a stable step plan (via `--list-steps` and the dry-run unit test)
- a small end-to-end run (subset of steps) produces a manifest and per-step logs

```bash
python3 -m pytest -q tests/unit/test_bd_3g1g_7_5_verification_runner.py | sed -E 's/ in [0-9.]+s$//'
```

```output
..                                                                       [100%]
2 passed
```

```bash
python3 scripts/bd_3g1g_verify.py --list-steps --skip-ubs
```

```output
static_forbidden_routes
pytest_unit
pytest_integration
vitest
playwright_e2e
```

```bash
python3 scripts/bd_3g1g_verify.py --only static_forbidden_routes,pytest_unit --skip-ubs --skip-vitest --skip-e2e --out-dir .verify/bd-3g1g/evidence-bd-3g1g.7.5
```

```output
.verify/bd-3g1g/evidence-bd-3g1g.7.5/manifest.json
```

```bash
python3 - <<'PY'
import json
from pathlib import Path
m = json.loads(Path('.verify/bd-3g1g/evidence-bd-3g1g.7.5/manifest.json').read_text(encoding='utf-8'))
print('overall_ok', m.get('overall_ok'))
for r in m.get('results', []):
    print(r.get('name'), r.get('exit_code'))
PY
```

```output
overall_ok True
static_forbidden_routes 0
pytest_unit 0
```
