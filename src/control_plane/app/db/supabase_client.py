"""Async PostgREST client wrapper for Supabase.

Bead: bd-1joj.3 (DB0)

This is the single point of Supabase HTTP interaction for control-plane repos.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

import httpx

from .errors import (
    SupabaseAuthError,
    SupabaseConflictError,
    SupabaseError,
    SupabaseNotFoundError,
)

# Module-level shared client for connection pooling in app runtimes/tests.
_shared_async_client: httpx.AsyncClient | None = None


def _get_shared_async_client() -> httpx.AsyncClient:
    global _shared_async_client
    if _shared_async_client is None:
        _shared_async_client = httpx.AsyncClient()
    return _shared_async_client


def _reset_shared_async_client_for_tests() -> None:
    """Test helper: clear shared client cache (does not close the instance)."""
    global _shared_async_client
    _shared_async_client = None


@dataclass(frozen=True, slots=True)
class PostgrestFilter:
    column: str
    op: str
    value: Any


def _split_schema_table(table: str, default_schema: str) -> tuple[str, str]:
    # Accept "cloud.workspaces" as well as "workspaces". Supabase accesses non-public
    # schemas via Accept-Profile/Content-Profile headers.
    if "." in table:
        schema, name = table.split(".", 1)
        return schema.strip(), name.strip()
    return default_schema, table.strip()


def _encode_filter_value(op: str, value: Any) -> str:
    if op == "is":
        if value is None:
            return "null"
        if value is True:
            return "true"
        if value is False:
            return "false"
        return str(value)

    if op == "in":
        if not isinstance(value, (list, tuple, set, frozenset)):
            raise ValueError("in operator requires an iterable of values")
        items = []
        for v in value:
            if isinstance(v, str):
                # PostgREST expects quoted strings inside `in.(...)`. Keep it simple and
                # JSON-escape quotes/backslashes.
                items.append(json.dumps(v))
            elif v is None:
                items.append("null")
            else:
                items.append(str(v))
        return f"({','.join(items)})"

    if value is None:
        # Prefer explicit `is.null` rather than `eq.null` (PostgREST semantics).
        if op in ("eq", "neq", "gt", "lt", "like"):
            raise ValueError(f"{op} does not support None; use op='is' with value=None")

    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _filters_to_params(
    filters: Sequence[PostgrestFilter] | Mapping[str, tuple[str, Any] | Any] | None,
) -> dict[str, str]:
    if not filters:
        return {}

    params: dict[str, str] = {}

    if isinstance(filters, Mapping):
        items: Iterable[tuple[str, tuple[str, Any] | Any]] = filters.items()
        for col, spec in items:
            if isinstance(spec, tuple) and len(spec) == 2:
                op, val = spec
            else:
                op, val = "eq", spec
            op_str = str(op)
            params[str(col)] = f"{op_str}.{_encode_filter_value(op_str, val)}"
        return params

    for f in filters:
        params[f.column] = f"{f.op}.{_encode_filter_value(f.op, f.value)}"
    return params


class SupabaseClient:
    """Minimal async PostgREST client (service role) with typed results."""

    def __init__(
        self,
        *,
        supabase_url: str,
        service_role_key: str,
        default_schema: str = "public",
        http_client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        if not supabase_url:
            raise ValueError("supabase_url is required")
        if not service_role_key:
            raise ValueError("service_role_key is required")

        self._supabase_url = supabase_url.rstrip("/")
        self._service_role_key = service_role_key
        self._default_schema = default_schema or "public"
        self._timeout_seconds = float(timeout_seconds)
        self._client = http_client or _get_shared_async_client()

    @property
    def base_rest_url(self) -> str:
        return f"{self._supabase_url}/rest/v1"

    def _auth_headers(self) -> dict[str, str]:
        # Never log these headers.
        return {
            "apikey": self._service_role_key,
            "Authorization": f"Bearer {self._service_role_key}",
        }

    def _schema_headers(self, schema: str, method: str) -> dict[str, str]:
        headers: dict[str, str] = {}
        if schema:
            headers["Accept-Profile"] = schema
            if method.upper() in ("POST", "PATCH", "PUT", "DELETE"):
                headers["Content-Profile"] = schema
        return headers

    def _raise_for_error(self, resp: httpx.Response) -> None:
        if resp.status_code < 400:
            return

        message = resp.text
        code = details = hint = None

        try:
            payload = resp.json()
            if isinstance(payload, dict):
                message = payload.get("message") or message
                code = payload.get("code")
                details = payload.get("details")
                hint = payload.get("hint")
        except ValueError:
            pass

        err_cls: type[SupabaseError]
        if resp.status_code in (401, 403):
            err_cls = SupabaseAuthError
        elif resp.status_code == 404:
            err_cls = SupabaseNotFoundError
        elif resp.status_code == 409:
            err_cls = SupabaseConflictError
        else:
            err_cls = SupabaseError

        # Avoid including secrets in the exception string.
        raise err_cls(
            status_code=resp.status_code,
            message=message,
            code=code,
            details=details,
            hint=hint,
        )

    async def select(
        self,
        table: str,
        filters: Sequence[PostgrestFilter] | Mapping[str, tuple[str, Any] | Any] | None = None,
        *,
        columns: str = "*",
        limit: int | None = None,
        order: str | None = None,
    ) -> list[dict[str, Any]]:
        schema, table_name = _split_schema_table(table, self._default_schema)
        url = f"{self.base_rest_url}/{table_name}"
        params = _filters_to_params(filters)
        params["select"] = columns
        if limit is not None:
            params["limit"] = str(int(limit))
        if order:
            params["order"] = order

        headers = {
            **self._auth_headers(),
            **self._schema_headers(schema, "GET"),
        }

        resp = await self._client.request(
            "GET",
            url,
            params=params,
            headers=headers,
            timeout=self._timeout_seconds,
        )
        self._raise_for_error(resp)
        payload = resp.json()
        if not isinstance(payload, list):
            raise SupabaseError(status_code=500, message="expected list response from select")
        return payload

    async def insert(
        self,
        table: str,
        data: Mapping[str, Any] | Sequence[Mapping[str, Any]],
        *,
        upsert: bool = False,
    ) -> list[dict[str, Any]]:
        schema, table_name = _split_schema_table(table, self._default_schema)
        url = f"{self.base_rest_url}/{table_name}"
        headers = {
            **self._auth_headers(),
            **self._schema_headers(schema, "POST"),
            "Prefer": "return=representation",
        }
        if upsert:
            headers["Prefer"] = f"{headers['Prefer']},resolution=merge-duplicates"

        resp = await self._client.request(
            "POST",
            url,
            json=data,
            headers=headers,
            timeout=self._timeout_seconds,
        )
        self._raise_for_error(resp)
        payload = resp.json()
        if not isinstance(payload, list):
            raise SupabaseError(status_code=500, message="expected list response from insert")
        return payload

    async def update(
        self,
        table: str,
        filters: Sequence[PostgrestFilter] | Mapping[str, tuple[str, Any] | Any] | None,
        data: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        schema, table_name = _split_schema_table(table, self._default_schema)
        url = f"{self.base_rest_url}/{table_name}"
        params = _filters_to_params(filters)
        headers = {
            **self._auth_headers(),
            **self._schema_headers(schema, "PATCH"),
            "Prefer": "return=representation",
        }

        resp = await self._client.request(
            "PATCH",
            url,
            params=params,
            json=data,
            headers=headers,
            timeout=self._timeout_seconds,
        )
        self._raise_for_error(resp)
        payload = resp.json()
        if not isinstance(payload, list):
            raise SupabaseError(status_code=500, message="expected list response from update")
        return payload

    async def delete(
        self,
        table: str,
        filters: Sequence[PostgrestFilter] | Mapping[str, tuple[str, Any] | Any] | None,
    ) -> list[dict[str, Any]]:
        schema, table_name = _split_schema_table(table, self._default_schema)
        url = f"{self.base_rest_url}/{table_name}"
        params = _filters_to_params(filters)
        headers = {
            **self._auth_headers(),
            **self._schema_headers(schema, "DELETE"),
            "Prefer": "return=representation",
        }

        resp = await self._client.request(
            "DELETE",
            url,
            params=params,
            headers=headers,
            timeout=self._timeout_seconds,
        )
        self._raise_for_error(resp)
        payload = resp.json()
        if not isinstance(payload, list):
            raise SupabaseError(status_code=500, message="expected list response from delete")
        return payload

    async def rpc(
        self,
        function_name: str,
        params: Mapping[str, Any] | None = None,
        *,
        schema: str | None = None,
    ) -> Any:
        schema_name = schema or self._default_schema
        url = f"{self.base_rest_url}/rpc/{function_name}"
        headers = {
            **self._auth_headers(),
            **self._schema_headers(schema_name, "POST"),
        }
        resp = await self._client.request(
            "POST",
            url,
            json=params or {},
            headers=headers,
            timeout=self._timeout_seconds,
        )
        self._raise_for_error(resp)
        return resp.json()

