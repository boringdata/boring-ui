#!/usr/bin/env bash
set -euo pipefail

APP_NAME="${1:-boring-ui}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUI_APP_TOML="${BUI_APP_TOML:-${REPO_ROOT}/boring.app.toml}"
FLY_BIN="${FLYCTL_BIN:-}"

if [[ -z "${FLY_BIN}" ]]; then
  if command -v flyctl >/dev/null 2>&1; then
    FLY_BIN="$(command -v flyctl)"
  elif command -v fly >/dev/null 2>&1; then
    FLY_BIN="$(command -v fly)"
  else
    echo "flyctl (or fly) is required on PATH" >&2
    exit 1
  fi
fi

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "missing required command: $1" >&2
    exit 1
  fi
}

vault_field() {
  local path="$1"
  local field="$2"
  vault kv get -field="$field" "$path"
}

app_toml_value() {
  local dotted_key="$1"
  python3 - "$BUI_APP_TOML" "$dotted_key" <<'PY'
from __future__ import annotations

import sys
import tomllib
from pathlib import Path

toml_path = Path(sys.argv[1])
key_path = sys.argv[2].split(".")

data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
value = data
for key in key_path:
    value = value[key]
print(value)
PY
}

require_cmd vault
require_cmd python3

declare -a pairs=()

pairs+=("DATABASE_URL=$(vault_field "secret/agent/app/boring-ui/prod" "database_url")")
pairs+=("BORING_UI_SESSION_SECRET=$(vault_field "secret/agent/app/boring-ui/prod" "session_secret")")
pairs+=("BORING_SETTINGS_KEY=$(vault_field "secret/agent/app/boring-ui/prod" "settings_key")")
pairs+=("ANTHROPIC_API_KEY=$(vault_field "secret/agent/anthropic" "api_key")")
pairs+=("RESEND_API_KEY=$(vault_field "secret/agent/services/resend" "api_key")")
pairs+=("NEON_AUTH_BASE_URL=$(app_toml_value "deploy.neon.auth_url")")
pairs+=("NEON_AUTH_JWKS_URL=$(app_toml_value "deploy.neon.jwks_url")")
pairs+=("GITHUB_APP_ID=$(vault_field "secret/agent/services/boring-ui-app" "app_id")")
pairs+=("GITHUB_APP_CLIENT_ID=$(vault_field "secret/agent/services/boring-ui-app" "client_id")")
pairs+=("GITHUB_APP_CLIENT_SECRET=$(vault_field "secret/agent/services/boring-ui-app" "client_secret")")
pairs+=("GITHUB_APP_PRIVATE_KEY=$(vault_field "secret/agent/services/boring-ui-app" "pem")")
pairs+=("GITHUB_APP_SLUG=$(vault_field "secret/agent/services/boring-ui-app" "slug")")

"$FLY_BIN" secrets set --app "$APP_NAME" "${pairs[@]}"
