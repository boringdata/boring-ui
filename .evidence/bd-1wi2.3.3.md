# bd-1wi2.3.3: Add companion panel to DockView layout in App.jsx

*2026-02-15T08:58:02Z by Showboat 0.5.0*

```bash
python3 -m pytest tests/unit/test_config.py tests/unit/test_capabilities.py -q 2>&1 | grep 'passed' | sed 's/in .*//' 
```

```output
29 passed 
```

```bash
grep -c 'companion' src/front/App.jsx
```

```output
21
```

```bash
git log --oneline -4
```

```output
fbc9a12 fix(companion): handle race between layout restore and capabilities load (bd-1wi2.3.3)
f3940a6 fix(companion): defer panel removal until capabilities are loaded (bd-1wi2.3.3)
4bb9395 fix(companion): address review findings for App.jsx companion panel (bd-1wi2.3.3)
816c1ca feat(companion): add companion panel creation to DockView layout (bd-1wi2.3.3)
```
