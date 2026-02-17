#!/usr/bin/env bash
set -euo pipefail

BACKEND_URL="${1:-http://0.0.0.0:3456}"

python3 - <<'PY' "$BACKEND_URL"
import json,sys,urllib.request
base=sys.argv[1].rstrip('/')

def get(path):
    url=f"{base}{path}"
    with urllib.request.urlopen(url, timeout=10) as r:
        body=r.read().decode('utf-8')
        return r.getcode(), json.loads(body)

health_code, health = get('/health')
cap_code, caps = get('/api/capabilities')
features = caps.get('features', {})
services = caps.get('services', {})

print(json.dumps({
    'backend_url': base,
    'health_status_code': health_code,
    'health_status': health.get('status'),
    'capabilities_status_code': cap_code,
    'features_subset': {
        'files': features.get('files'),
        'pty': features.get('pty'),
        'companion': features.get('companion'),
        'pi': features.get('pi'),
    },
    'services': services,
    'notes': [
        'PI mode in this branch is embedded in frontend; no dedicated local /api/pi or /ws/pi endpoint exists.',
        'Model streaming is handled by pi-ai providers directly from browser context.'
    ]
}, indent=2))
PY
