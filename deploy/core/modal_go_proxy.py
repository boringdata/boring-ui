"""Core mode: static frontend + reverse proxy to Go backend on Modal.

Serves the built SPA from dist/ and proxies /api, /auth, /ws to the
Go backend (boring-ui-go). No Go code changes needed.

Usage:
    GO_BACKEND_URL=https://julien-hurault--boring-ui-go-web.modal.run \
    modal deploy deploy/core/modal_go_proxy.py
"""
from __future__ import annotations

import os
from pathlib import Path

import modal

_app_name = os.environ.get("BUI_MODAL_APP_NAME", "boring-ui")
_go_backend_url = os.environ.get(
    "GO_BACKEND_URL",
    "https://julien-hurault--boring-ui-go-web.modal.run",
)

app = modal.App(_app_name)

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("starlette>=0.40", "httpx>=0.27", "uvicorn>=0.30")
)

# Add built frontend
for candidate in ("dist/web", "dist"):
    if Path(candidate).is_dir():
        image = image.add_local_dir(candidate, "/app/static", copy=True)
        break

image = image.env({"GO_BACKEND_URL": _go_backend_url})


@app.function(image=image, timeout=600, memory=512, min_containers=0)
@modal.concurrent(max_inputs=100)
@modal.asgi_app()
def web():
    """SPA + reverse proxy to Go backend."""
    import httpx
    from starlette.applications import Starlette
    from starlette.responses import FileResponse, Response
    from starlette.routing import Mount, Route
    from starlette.staticfiles import StaticFiles

    backend = os.environ["GO_BACKEND_URL"].rstrip("/")
    static_dir = Path("/app/static")
    client = httpx.AsyncClient(base_url=backend, timeout=30.0)

    # Modal injects internal headers that must not be forwarded
    _STRIP_REQ = {"host", "modal-function-call-id", "modal-retry-count"}
    _STRIP_RESP = {"modal-function-call-id", "modal-retry-count",
                   "transfer-encoding", "content-encoding", "content-length"}

    async def proxy(request):
        path = request.url.path
        qs = str(request.url.query)
        url = f"{path}?{qs}" if qs else path

        fwd = {k: v for k, v in request.headers.items()
               if k.lower() not in _STRIP_REQ}

        resp = await client.request(
            method=request.method,
            url=url,
            headers=fwd,
            content=await request.body(),
        )
        resp_headers = {k: v for k, v in resp.headers.items()
                        if k.lower() not in _STRIP_RESP}
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=resp_headers,
        )

    async def spa_fallback(request):
        """Serve index.html for any path not matched by static or API."""
        index = static_dir / "index.html"
        if index.exists():
            return FileResponse(index, media_type="text/html")
        return Response("Not Found", status_code=404)

    # /auth/login and /auth/signup are SPA pages; other /auth/* go to backend
    _SPA_AUTH_PREFIXES = ("/auth/login", "/auth/signup", "/auth/settings")

    async def auth_proxy(request):
        path = request.url.path.rstrip("/")
        if any(path == p or path.startswith(p + "/") for p in _SPA_AUTH_PREFIXES):
            return await spa_fallback(request)
        return await proxy(request)

    routes = [
        Route("/api/{path:path}", proxy, methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]),
        Route("/auth/{path:path}", auth_proxy, methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]),
        Route("/ws/{path:path}", proxy, methods=["GET"]),
        Mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets") if (static_dir / "assets").exists() else Route("/assets/{path:path}", spa_fallback),
        Route("/{path:path}", spa_fallback),
    ]

    return Starlette(routes=routes)
