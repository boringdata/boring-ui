"""SmokeClient: httpx wrapper with cookie jar, base_url switching, and reporting."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class StepResult:
    phase: str
    method: str
    path: str
    status: int
    ok: bool
    elapsed_ms: float
    detail: str = ""


class SmokeClient:
    """httpx.Client wrapper with cookie persistence, base_url switching, result collection."""

    def __init__(self, base_url: str, *, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.cookies = httpx.Cookies()
        self.results: list[StepResult] = []
        self._phase = "init"

    def set_phase(self, phase: str) -> None:
        self._phase = phase

    def _client(self) -> httpx.Client:
        # Use a plain dict for cookies so they are sent regardless of domain
        # (httpx.Cookies is domain-scoped and won't forward across base_url switches).
        cookie_dict = dict(self.cookies)
        return httpx.Client(
            base_url=self.base_url,
            cookies=cookie_dict,
            timeout=self.timeout,
            follow_redirects=False,
        )

    def _record(self, method: str, path: str, resp: httpx.Response, ok: bool, elapsed_ms: float, detail: str = "") -> None:
        self.results.append(StepResult(
            phase=self._phase,
            method=method,
            path=path,
            status=resp.status_code,
            ok=ok,
            elapsed_ms=elapsed_ms,
            detail=detail,
        ))

    def request(self, method: str, path: str, *, expect_status: int | tuple[int, ...] | None = None, **kw) -> httpx.Response:
        with self._client() as client:
            t0 = time.monotonic()
            resp = client.request(method, path, **kw)
            elapsed = (time.monotonic() - t0) * 1000
            # Persist any cookies set by the response
            self.cookies.update(resp.cookies)
            if expect_status is not None:
                if isinstance(expect_status, int):
                    expect_status = (expect_status,)
                ok = resp.status_code in expect_status
            else:
                ok = 200 <= resp.status_code < 400
            self._record(method, path, resp, ok, elapsed)
            return resp

    def get(self, path: str, **kw) -> httpx.Response:
        return self.request("GET", path, **kw)

    def post(self, path: str, **kw) -> httpx.Response:
        return self.request("POST", path, **kw)

    def put(self, path: str, **kw) -> httpx.Response:
        return self.request("PUT", path, **kw)

    def delete(self, path: str, **kw) -> httpx.Response:
        return self.request("DELETE", path, **kw)

    def switch_base(self, new_base_url: str) -> None:
        self.base_url = new_base_url.rstrip("/")

    def report(self) -> dict[str, Any]:
        passed = sum(1 for r in self.results if r.ok)
        failed = sum(1 for r in self.results if not r.ok)
        return {
            "ok": failed == 0,
            "passed": passed,
            "failed": failed,
            "total": len(self.results),
            "steps": [
                {
                    "phase": r.phase,
                    "method": r.method,
                    "path": r.path,
                    "status": r.status,
                    "ok": r.ok,
                    "elapsed_ms": round(r.elapsed_ms, 1),
                    "detail": r.detail,
                }
                for r in self.results
            ],
        }

    def assert_all_passed(self) -> None:
        failures = [r for r in self.results if not r.ok]
        if failures:
            lines = [f"  {r.phase}: {r.method} {r.path} -> {r.status} ({r.detail})" for r in failures]
            raise AssertionError(f"{len(failures)} smoke test step(s) failed:\n" + "\n".join(lines))
