# 9. Build & Packaging

[< Back to Index](README.md) | [Prev: Database](08-database.md) | [Next: Testing >](10-testing.md)

---

## 9.1 Frontend Build

```bash
cd src/web
npm install
npm run build -- --outDir dist-front
```

Output: `src/web/dist-front/` with `index.html` + hashed JS/CSS assets.

For core mode deploy, `deploy.sh` does this automatically when `AUTO_BUILD=1`.

## 9.2 Wheel Build (for Edge Deploy)

Edge mode requires a Python wheel containing your backend + boring-ui backend + built frontend assets. The wheel is then bundled into a tarball for boring-sandbox.

### `pyproject.toml`

```toml
[project]
name = "my-app"
requires-python = ">=3.8"

dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.27",
    "httpx>=0.27",
    "websockets>=13",
]

[tool.maturin]
bindings = "bin"
python-packages = [
    "my_app_package",
    "src/web/backend",
    "interface/boring-ui/src/back/boring_ui",
]
include = [
    { path = "my_app_package/web_static/**", format = "wheel" },
]
```

### `scripts/build_web_wheel.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${1:-${ROOT_DIR}/dist}"
STATIC_STAGE_DIR="${ROOT_DIR}/my_app_package/web_static"
BORING_UI_ROOT="${ROOT_DIR}/interface/boring-ui"

# Check boring-ui helper exists
if [[ ! -x "${BORING_UI_ROOT}/scripts/package_app_assets.py" ]]; then
  echo "[build] missing boring-ui helper — ensure submodule is initialized" >&2
  exit 1
fi

mkdir -p "${OUT_DIR}"

# Stage frontend assets using boring-ui helper
python3 "${BORING_UI_ROOT}/scripts/package_app_assets.py" \
  --frontend-dir "${ROOT_DIR}/src/web" \
  --static-dir "${STATIC_STAGE_DIR}"

# Build wheel
cd "${ROOT_DIR}"
if command -v maturin >/dev/null 2>&1; then
  maturin build --release --bindings bin --out "${OUT_DIR}"
else
  uv run --with maturin maturin build --release --bindings bin --out "${OUT_DIR}"
fi

echo "[build] wheel: $(ls -1t "${OUT_DIR}"/*.whl | head -1)"
```

### Build Flow

```
npm run build          →  src/web/dist-front/
                              │
package_app_assets.py  →  my_app_package/web_static/  (staged copy)
                              │
maturin build          →  dist/my_app-0.1.0-*.whl
                              │
build_macro_bundle.sh  →  artifacts/my-app-bundle.tar.gz  (edge only)
```

## 9.3 Smoke Tests

### `scripts/smoke_test.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:?Usage: smoke_test.sh <base-url>}"
PASS=0; FAIL=0

check() {
  local desc="$1" url="$2" expected="$3"
  local status
  status=$(curl -s -o /dev/null -w '%{http_code}' "${url}")
  if [[ "${status}" == "${expected}" ]]; then
    echo "  PASS: ${desc}"
    ((PASS++))
  else
    echo "  FAIL: ${desc} (got ${status}, expected ${expected})"
    ((FAIL++))
  fi
}

echo "Smoke testing ${BASE_URL}"
check "capabilities" "${BASE_URL}/api/capabilities" "200"
check "my-domain items" "${BASE_URL}/api/v1/my-domain/items" "200"
check "static index" "${BASE_URL}/" "200"

echo ""
echo "Results: ${PASS} passed, ${FAIL} failed"
[[ ${FAIL} -eq 0 ]] || exit 1
```

Usage:
```bash
# Against local dev
./scripts/smoke_test.sh http://localhost:8000

# Against deployed app
./scripts/smoke_test.sh https://my-app.modal.run
```
