# bd-3g1g.7.2 - Phase 5 Verification Matrix

*2026-02-18T11:55:52Z by Showboat 0.5.0*

Evidence for bd-3g1g.7.2 (Phase 5 cutover verification matrix).

Notes:
- UBS is skipped here (runner flag) due to environment instability; all other verification dimensions are executed.
- Playwright is run with CI-like settings and fixed high ports to avoid cross-agent port collisions.

```bash
CI=1 PW_E2E_PORT=49173 PW_E2E_API_PORT=49180 VITE_API_URL=http://127.0.0.1:49180 python3 scripts/bd_3g1g_verify.py --out-dir .verify/bd-3g1g/phase5-bd-3g1g.7.2-evidence --skip-ubs
```

```output
.verify/bd-3g1g/phase5-bd-3g1g.7.2-evidence/manifest.json
```

```bash
python3 -c 'import json;from pathlib import Path;m=json.loads(Path(".verify/bd-3g1g/phase5-bd-3g1g.7.2-evidence/manifest.json").read_text());print("overall_ok=",m.get("overall_ok"));[print("{}: exit_code={}".format(r["name"], r["exit_code"])) for r in m.get("results", [])]'
```

```output
overall_ok= True
static_forbidden_routes: exit_code=0
pytest_unit: exit_code=0
pytest_integration: exit_code=0
vitest: exit_code=0
playwright_e2e: exit_code=0
```

```bash
git show -s --format='%H %s' 0bf12bf
```

```output
0bf12bf3686a70331fde33741c086d9aae130dec bd-3g1g.7.2: deflake user-menu /w navigation expectations
```

```bash
python3 -c 'import re;from pathlib import Path;vitest=Path(".verify/bd-3g1g/phase5-bd-3g1g.7.2-evidence/logs/vitest.log").read_text(errors="ignore");files=re.search(r"Test Files\s+\d+\s+passed\s*\(\d+\)",vitest);tests=re.search(r"Tests\s+\d+\s+passed\s*\(\d+\)",vitest);print("vitest:",(files.group(0) if files else "(missing)"),";",(tests.group(0) if tests else "(missing)"))'
```

```output
vitest: Test Files  24 passed (24) ; Tests  301 passed (301)
```
