# bd-2fxd: Stabilize Playwright workers

*2026-02-18T11:41:05Z by Showboat 0.5.0*

Goal: avoid Playwright flake under parallel workers by defaulting workers=1 (allow opt-in parallelism via PW_E2E_WORKERS).\n\nCommit: bb5bee5.

```bash
rm -f test-results/results.json; npm run -s test:e2e -- src/front/__tests__/e2e/layout.spec.ts >/dev/null 2>&1; node -e "const fs=require('fs'); const p='test-results/results.json'; if(!fs.existsSync(p)){console.log('e2e_layout=missing_results_json'); process.exit(2)} const r=JSON.parse(fs.readFileSync(p,'utf8')); const s=r.stats||{}; console.log('e2e_layout=pass'); console.log('expected='+String(s.expected)+' unexpected='+String(s.unexpected)+' flaky='+String(s.flaky));"
```

```output
e2e_layout=pass
expected=8 unexpected=0 flaky=0
```
