# Sprite Deployment Runbook

This project is deployed to Sprites as a single service that serves:
- FastAPI backend (`/api/*`, `/ws/*`)
- built frontend static assets (`dist/`)

Target sprite used in this environment: `test-option-2`.

## Quick Start

```bash
./deploy/sprite/scripts/deploy.sh test-option-2
sprite -s test-option-2 url update --auth public
curl -i https://test-option-2-bm6zi.sprites.app/health
```

## What `deploy.sh` Does

`deploy/sprite/scripts/deploy.sh` performs:
1. Frontend production build (`npm ci && npm run build`)
2. Backend wheel build (`pip wheel`)
3. Artifact bundle creation (`dist/` + backend sources + wheel)
4. Upload/extract bundle inside sprite
5. Backend install in sprite (`pip install --force-reinstall`)
6. Service recreate via `sprite-env services` on `http_port=8000`
7. URL display

## Runtime Command Used In Sprite

The service runs with:

```bash
cd /home/sprite/boring-ui \
  && PYTHONPATH=/home/sprite/boring-ui/src/back \
     BORING_UI_STATIC_DIR=/home/sprite/boring-ui/dist \
     python3 -m uvicorn boring_ui.runtime:app --host 0.0.0.0 --port 8000
```

Why:
- `python3 -m uvicorn` avoids PATH issues (`uvicorn: command not found`)
- `PYTHONPATH=.../src/back` ensures latest uploaded source is importable
- `BORING_UI_STATIC_DIR` enables SPA static serving from backend

## Files Added For Deployment

- `deploy/sprite/scripts/deploy.sh`
- `src/back/boring_ui/runtime.py`

## Verified Health Check

Expected response:

```json
{"status":"ok","workspace":"/home/sprite","features":{"files":true,"git":true,"pty":true,"chat_claude_code":true,"stream":true,"approval":true}}
```

Endpoint:

```bash
curl -i https://test-option-2-bm6zi.sprites.app/health
```

## WebSocket Endpoints

Frontend uses:
- `wss://<sprite>/ws/pty?...`
- `wss://<sprite>/ws/claude-stream?...`

Backend serves these routes under `/ws`.

## Known Findings And Fixes

1. Sprite URL auth may still redirect briefly after setting `public`
- Symptom: `302` to `sprites.dev/auth/sprite`
- Fix: wait a few seconds and re-test

2. Sprites `/services/{name}` API can return `service name required`
- Workaround used: manage services from inside sprite with `sprite-env services`

3. Wheel version reuse can leave stale code (`0.1.0` unchanged)
- Fix in script: `pip install --force-reinstall ./boring_ui-*.whl`
- Additional hardening: runtime import via `PYTHONPATH` source path

4. Intermittent `sprite exec -file` upload timeout
- Symptom: `fs/write ... context deadline exceeded`
- Fix: rerun deployment command

5. WebSocket `1006` during initial page load
- Seen when client reconnects rapidly during startup/errors
- Confirm backend is up first: `/health` must return `200`
- Then inspect service logs:
  ```bash
  sprite exec -s test-option-2 bash -lc 'tail -n 200 /.sprite/logs/services/app.log'
  ```

## Restart And Recycle

Restart service:

```bash
sprite exec -s test-option-2 bash -lc 'sprite-env services restart app'
```

Full recycle:

```bash
sprite destroy -force test-option-2
sprite create test-option-2
./deploy/sprite/scripts/deploy.sh test-option-2
sprite -s test-option-2 url update --auth public
```
