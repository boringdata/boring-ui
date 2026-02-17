# bd-1q50: review hardening follow-up

*2026-02-16T22:05:38Z by Showboat 0.5.0*

Follow-up hardening for roborev findings: workspace plugin execution is now opt-in with optional allowlist, watcher avoids root fallback, PI iframe sandbox no longer uses allow-same-origin, workspace pane loader validates paths, and plugin WS reconnect uses exponential backoff + capability gating.

```bash
set -o pipefail; python3 -m pytest tests/unit/test_config.py tests/unit/test_api_config_companion_url.py tests/unit/test_capabilities.py tests/integration/test_create_app.py -q | sed -E 's/in [0-9.]+s/in <time>/'
```

```output
.............................................................            [100%]
61 passed in <time>
```

```bash
set -o pipefail; npm run build 2>&1 | sed -E 's/built in [0-9.]+s/built in <time>/'
```

```output

> boring-ui@0.1.0 build
> vite build

vite v5.4.21 building for production...
transforming...
✓ 2979 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                     0.98 kB │ gzip:   0.51 kB
dist/assets/index-BcW9unAf.css    190.77 kB │ gzip:  29.84 kB
dist/assets/index-Dba_ciOb.js   2,210.16 kB │ gzip: 648.10 kB

(!) Some chunks are larger than 500 kB after minification. Consider:
- Using dynamic import() to code-split the application
- Use build.rollupOptions.output.manualChunks to improve chunking: https://rollupjs.org/configuration-options/#output-manualchunks
- Adjust chunk size limit for this warning via build.chunkSizeWarningLimit.
✓ built in <time>
```

```bash {image}
.evidence/bd-1q50-pi-expanded.png
```

![f7dddaa2-2026-02-16](f7dddaa2-2026-02-16.png)

```bash {image}
.evidence/bd-1q50-pi-collapsed.png
```

![23cd0899-2026-02-16](23cd0899-2026-02-16.png)

```bash
set -o pipefail; python3 -m pytest tests/unit/test_workspace_plugins.py -q | sed -E 's/in [0-9.]+s/in <time>/'
```

```output
..                                                                       [100%]
2 passed in <time>
```
