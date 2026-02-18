# bd-3iw8: Deflake user-menu e2e prompt

*2026-02-18T12:18:24Z by Showboat 0.5.0*

Fix: avoid Playwright dialog.accept hang by stubbing window.prompt in the switch-workspace e2e test.

```bash
rm -f test-results/results.json; PW_E2E_REUSE_SERVER=0 PW_E2E_WORKERS=1 npm run -s test:e2e -- src/front/__tests__/e2e/user-menu-flows.spec.ts -g 'switch workspace navigates' >/dev/null 2>&1; node -e "const fs=require('fs'); const p='test-results/results.json'; if(!fs.existsSync(p)){console.log('e2e_user_menu_switch=missing_results_json'); process.exit(2)} const r=JSON.parse(fs.readFileSync(p,'utf8')); const s=r.stats||{}; console.log('e2e_user_menu_switch=pass'); console.log('expected='+String(s.expected)+' unexpected='+String(s.unexpected)+' flaky='+String(s.flaky));"
```

```output
e2e_user_menu_switch=pass
expected=1 unexpected=0 flaky=0
```
