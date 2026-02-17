#!/usr/bin/env bash
set -euo pipefail

is_bun_node() {
  node -e "process.exit(process.versions?.bun ? 0 : 1)" >/dev/null 2>&1
}

find_real_node_dir() {
  local candidate
  while IFS= read -r candidate; do
    if [[ -z "$candidate" || "$candidate" == *"/.bun/"* ]]; then
      continue
    fi
    if "$candidate" -e "process.exit(process.versions?.bun ? 1 : 0)" >/dev/null 2>&1; then
      dirname "$candidate"
      return 0
    fi
  done < <(which -a node 2>/dev/null | awk '!seen[$0]++')
  return 1
}

if is_bun_node; then
  if node_dir="$(find_real_node_dir)"; then
    export PATH="${node_dir}:${PATH}"
    hash -r
  else
    echo "error: Playwright e2e requires Node.js. 'node' resolves to Bun and no alternate Node binary was found on PATH." >&2
    exit 1
  fi
fi

npx playwright test "$@"
