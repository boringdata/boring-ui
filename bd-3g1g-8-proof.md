# bd-3g1g.8 Gate Commands Proof

*2026-02-19T13:41:56Z by Showboat 0.5.0*

```bash
python3 -m pytest -q tests/unit
```

```output
........................................................................ [ 27%]
........................................................................ [ 54%]
........................................................................ [ 82%]
..............................................                           [100%]
262 passed in 5.96s
```

```bash
python3 scripts/bd_3g1g_verify.py --skip-ubs --only pytest_unit
```

```output
/home/ubuntu/projects/boring-ui/.verify/bd-3g1g/20260219T134218Z/manifest.json
```
