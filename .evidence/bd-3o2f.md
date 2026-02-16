# bd-3o2f: Fix companion right-rail layout + collapse

*2026-02-16T19:45:49Z by Showboat 0.5.0*

Companion right-rail panel now shares collapse behavior with the agent chat panel and the embedded UI keeps its input visible above the bottom shell.

```bash {image}
![Companion right rail with input visible](.evidence/bd-3o2f-ui.png)
```

![Companion right rail with input visible](7a2b5152-2026-02-16.png)

```bash
python3 -c "import subprocess,sys; r=subprocess.run(['python3','-m','pytest','tests/unit/test_capabilities.py','-q','--disable-warnings','--maxfail=1'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True); print('pytest exit', r.returncode); sys.exit(r.returncode)"
```

```output
pytest exit 0
```

```bash {image}
![Companion collapsed](.evidence/bd-3o2f-ui-collapsed.png)
```

![Companion collapsed](6a0b0846-2026-02-16.png)

```bash {image}
![Companion expanded](.evidence/bd-3o2f-ui-expanded.png)
```

![Companion expanded](91cd4bfc-2026-02-16.png)
