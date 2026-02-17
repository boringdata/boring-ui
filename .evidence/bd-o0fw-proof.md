# bd-o0fw: PI native right-rail agent integration

*2026-02-17T09:15:25Z by Showboat 0.5.0*

```bash
python3 -m pytest tests/unit/test_capabilities.py tests/unit/test_config.py -q > /tmp/pi_pytest.log && python3 - <<'PY'
import re
text=open('/tmp/pi_pytest.log').read()
m=re.search(r'(\d+) passed', text)
print({'pytest_ok': bool(m), 'passed': int(m.group(1)) if m else None})
PY
```

```output
{'pytest_ok': True, 'passed': 39}
```

```bash
PATH=/usr/bin:/bin:$PATH node ./node_modules/vitest/vitest.mjs run src/front/panels/CompanionPanel.test.jsx src/front/providers/companion/EmbeddedSessionToolbar.test.jsx > /tmp/pi_vitest.log 2>&1 && python3 - <<'PY'
import re
text=open('/tmp/pi_vitest.log').read()
m=re.search(r'Tests\s+(\d+) passed \((\d+)\)', text)
print({'vitest_ok': bool(m), 'tests_passed': int(m.group(1)) if m else None})
PY
```

```output
{'vitest_ok': True, 'tests_passed': 9}
```

```bash
PATH=/usr/bin:/bin:$PATH node ./node_modules/vite/bin/vite.js build > /tmp/pi_build.log 2>&1 && python3 - <<'PY'
import re
text=open('/tmp/pi_build.log').read()
built=bool(re.search(r'✓ built in', text))
mods=re.search(r'✓\s+(\d+) modules transformed\.', text)
print({'build_ok': built, 'modules_transformed': int(mods.group(1)) if mods else None})
PY
```

```output
{'build_ok': True, 'modules_transformed': 5833}
```

```bash
curl -s http://127.0.0.1:3456/api/capabilities > /tmp/pi_capabilities.json && python3 - <<'PY'
import json
with open('/tmp/pi_capabilities.json') as f:
    d=json.load(f)
print({k:d['features'].get(k) for k in ['files','pty','companion','pi']})
PY
```

```output
{'files': True, 'pty': True, 'companion': True, 'pi': True}
```

```bash
rodney open 'http://127.0.0.1:5190/?agent_mode=pi' >/tmp/rodney_pi_open.log && rodney waitidle >/tmp/rodney_pi_wait1.log && rodney waitidle >/tmp/rodney_pi_wait2.log && rodney js "(() => { const expand=document.querySelector('[aria-label=\"Expand agent panel\"]'); if (expand) expand.click(); const host=document.querySelector('[data-testid=pi-native-adapter] > div'); const root=host?.shadowRoot; const panel=root?.querySelector('pi-chat-panel'); const ai=root?.querySelector('agent-interface'); const me=ai?.querySelector('message-editor'); const ta=me?.querySelector('textarea'); return { hasPiRoot: !!document.querySelector('[data-testid=pi-native-adapter]'), hasPiChatPanel: !!panel, hasAgentInterface: !!ai, hasTextarea: !!ta, hasCompanionWrapper: !!document.querySelector('.companion-wrapper') }; })()"
```

```output
{
  "hasAgentInterface": true,
  "hasCompanionWrapper": false,
  "hasPiChatPanel": true,
  "hasPiRoot": true,
  "hasTextarea": true
}
```

```bash
rodney js "(() => { const host=document.querySelector('[data-testid=pi-native-adapter] > div'); const ta=host?.shadowRoot?.querySelector('message-editor textarea'); const box=ta?.parentElement; if(!ta || !box) return {ok:false}; ta.blur(); document.body.focus(); const before={border:getComputedStyle(box).borderColor}; ta.focus(); const after={border:getComputedStyle(box).borderColor}; return {ok:true,before,after,changed:before.border!==after.border}; })()"
```

```output
{
  "after": {
    "border": "rgba(174, 86, 48, 0.3)"
  },
  "before": {
    "border": "rgb(17, 24, 39)"
  },
  "changed": true,
  "ok": true
}
```

```bash
rodney screenshot .evidence/bd-o0fw-pi-expanded.png
```

```output
.evidence/bd-o0fw-pi-expanded.png
```

```bash
rodney js "(() => { const btn=document.querySelector('.companion-panel .terminal-header button[aria-label=\"Collapse agent panel\"]') || document.querySelector('.companion-panel .terminal-header button[aria-label=\"Collapse panel\"]') || document.querySelector('[aria-label=\"Collapse agent panel\"]'); if (btn) btn.click(); const collapsed = !!document.querySelector('[aria-label=\"Expand agent panel\"]'); return {clicked: !!btn, collapsed}; })()"
```

```output
{
  "clicked": true,
  "collapsed": false
}
```

```bash
rodney screenshot .evidence/bd-o0fw-pi-collapsed.png
```

```output
.evidence/bd-o0fw-pi-collapsed.png
```

```bash
rodney open 'http://127.0.0.1:5190/?agent_mode=companion' >/tmp/rodney_comp_open.log && rodney waitidle >/tmp/rodney_comp_wait1.log && rodney waitidle >/tmp/rodney_comp_wait2.log && rodney js "(async () => { const expand=document.querySelector('[aria-label=\"Expand agent panel\"]'); if (expand) { expand.click(); await new Promise(r=>setTimeout(r,120)); } const hasCompanionPanel = !!document.querySelector('[data-testid=companion-panel]'); const hasPiAdapter = !!document.querySelector('[data-testid=pi-native-adapter]'); const connecting = !!Array.from(document.querySelectorAll('*')).find(el => (el.textContent||'').includes('Connecting to Companion server')); return {hasCompanionPanel, hasPiAdapter, connecting}; })()"
```

```output
{
  "connecting": true,
  "hasCompanionPanel": true,
  "hasPiAdapter": false
}
```

```bash
rodney screenshot .evidence/bd-o0fw-companion-check.png
```

```output
.evidence/bd-o0fw-companion-check.png
```
