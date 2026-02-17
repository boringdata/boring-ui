# bd-30zp: Hide companion session dropdown

*2026-02-16T08:22:52Z by Showboat 0.5.0*

Hid the embedded companion session dropdown; screenshot below shows companion chat in right rail with no session selector.

```bash {image}
![Companion embedded UI without session dropdown](.evidence/bd-30zp-ui.png)
```

![Companion embedded UI without session dropdown](1904b5d9-2026-02-16.png)

```bash
python3 -c "import subprocess,sys; r=subprocess.run(['python3','-m','pytest','tests/unit/test_capabilities.py','-q','--disable-warnings','--maxfail=1'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True); print('pytest exit', r.returncode); sys.exit(r.returncode)"
```

```output
pytest exit 0
```
