#!/usr/bin/env bash
set -euo pipefail

# Native Companion backend launcher.
# Defaults to port 3456 to match existing boring-ui companion wiring.
PORT="${PORT:-3456}"
COMPANION_PACKAGE="${COMPANION_PACKAGE:-the-companion@0.46.0}"

# the-companion reads PORT from env and exposes the richer API expected by
# src/front/providers/companion/upstream/* (relaunch/archive/unarchive/etc.).
exec env PORT="$PORT" bunx "$COMPANION_PACKAGE" serve
