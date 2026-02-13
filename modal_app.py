"""Compatibility shim for legacy Modal deployments.

Bead: bd-1joj.2 (CP1)

Prefer:
  modal deploy src/control_plane/modal/modal_app.py
"""

from __future__ import annotations

from control_plane.modal.modal_app import app, fastapi_app  # re-export

__all__ = ["app", "fastapi_app"]

