# bd-1q50: Integrate Pi Agent as right-rail web provider

*2026-02-16T22:00:14Z by Showboat 0.5.0*

Implemented PI as an alternate right-rail agent provider with mode-aware panel wiring in App.jsx (agent_mode=pi), backend capabilities (features.pi, services.pi), and provider-aware CompanionPanel rendering. Added backend unit/integration coverage and captured expanded/collapsed UI screenshots for agent_mode=pi.

```bash
set -o pipefail; python3 -m pytest tests/unit/test_config.py tests/unit/test_api_config_companion_url.py tests/unit/test_capabilities.py -q | sed -E 's/in [0-9.]+s/in <time>/'
```

```output
.....................................                                    [100%]
=============================== warnings summary ===============================
tests/unit/test_capabilities.py::TestCapabilitiesEndpoint::test_capabilities_returns_json
tests/unit/test_capabilities.py::TestCapabilitiesEndpoint::test_capabilities_has_version
tests/unit/test_capabilities.py::TestCapabilitiesEndpoint::test_capabilities_has_features
tests/unit/test_capabilities.py::TestCapabilitiesEndpoint::test_capabilities_has_routers
tests/unit/test_capabilities.py::TestCapabilitiesEndpoint::test_capabilities_features_match_routers
tests/unit/test_capabilities.py::TestCapabilitiesEndpoint::test_capabilities_minimal_features
tests/unit/test_capabilities.py::TestCapabilitiesEndpoint::test_capabilities_with_selective_routers
tests/unit/test_capabilities.py::TestHealthEndpointFeatures::test_health_includes_features
tests/unit/test_capabilities.py::TestHealthEndpointFeatures::test_health_features_match_selective_routers
  /home/ubuntu/projects/boring-ui/src/back/boring_ui/api/app.py:196: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    @app.on_event("startup")

tests/unit/test_capabilities.py::TestCapabilitiesEndpoint::test_capabilities_returns_json
tests/unit/test_capabilities.py::TestCapabilitiesEndpoint::test_capabilities_has_version
tests/unit/test_capabilities.py::TestCapabilitiesEndpoint::test_capabilities_has_features
tests/unit/test_capabilities.py::TestCapabilitiesEndpoint::test_capabilities_has_routers
tests/unit/test_capabilities.py::TestCapabilitiesEndpoint::test_capabilities_features_match_routers
tests/unit/test_capabilities.py::TestCapabilitiesEndpoint::test_capabilities_minimal_features
tests/unit/test_capabilities.py::TestCapabilitiesEndpoint::test_capabilities_with_selective_routers
tests/unit/test_capabilities.py::TestHealthEndpointFeatures::test_health_includes_features
tests/unit/test_capabilities.py::TestHealthEndpointFeatures::test_health_features_match_selective_routers
  /home/ubuntu/.local/lib/python3.13/site-packages/fastapi/applications.py:4576: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    return self.router.on_event(event_type)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
37 passed, 18 warnings in <time>
```

```bash
set -o pipefail; python3 -m pytest tests/integration/test_create_app.py -q | sed -E 's/in [0-9.]+s/in <time>/'
```

```output
......................                                                   [100%]
=============================== warnings summary ===============================
tests/integration/test_create_app.py: 22 warnings
  /home/ubuntu/projects/boring-ui/src/back/boring_ui/api/app.py:196: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    @app.on_event("startup")

tests/integration/test_create_app.py: 22 warnings
  /home/ubuntu/.local/lib/python3.13/site-packages/fastapi/applications.py:4576: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    return self.router.on_event(event_type)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
22 passed, 44 warnings in <time>
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
dist/assets/index-BSqLMHDU.js   2,209.65 kB │ gzip: 647.90 kB

(!) Some chunks are larger than 500 kB after minification. Consider:
- Using dynamic import() to code-split the application
- Use build.rollupOptions.output.manualChunks to improve chunking: https://rollupjs.org/configuration-options/#output-manualchunks
- Adjust chunk size limit for this warning via build.chunkSizeWarningLimit.
✓ built in <time>
```

```bash {image}
.evidence/bd-1q50-pi-expanded.png
```

![d96ca608-2026-02-16](d96ca608-2026-02-16.png)

```bash {image}
.evidence/bd-1q50-pi-collapsed.png
```

![980a4a43-2026-02-16](980a4a43-2026-02-16.png)

Frontend Vitest execution is currently blocked in this container runtime by worker-process incompatibility (tinypool/port.addListener + channel.unref errors). Backend tests and production build were used for verification.
