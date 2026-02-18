# bd-mc55: Stabilize verification runner Playwright lifecycle

*2026-02-18T12:13:58Z by Showboat 0.5.0*

Set PW_E2E_REUSE_SERVER=0 and PW_E2E_WORKERS=1 for the Playwright step in scripts/bd_3g1g_verify.py to prevent intermittent ERR_CONNECTION_REFUSED and parallelism flake in the bd-3g1g.7.2 matrix runner.

```bash
python3 scripts/bd_3g1g_verify.py --skip-ubs --only playwright_e2e --out-dir .verify/bd-3g1g/evidence-bd-mc55-playwright
```

```output
.verify/bd-3g1g/evidence-bd-mc55-playwright/manifest.json
```
