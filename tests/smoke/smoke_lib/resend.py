"""Resend email polling and confirmation URL extraction."""
from __future__ import annotations

import html
import re
import time
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import httpx

RESEND_API_BASE = "https://api.resend.com"
CONFIRMATION_CODE_RE = re.compile(r"\b(\d{6})\b")


def _iso_to_epoch(value: str | None) -> float | None:
    if not value:
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = f"{raw[:-1]}+00:00"
    try:
        return datetime.fromisoformat(raw).timestamp()
    except ValueError:
        return None


def _normalize_recipients(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        out: list[str] = []
        for item in raw:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                email = item.get("email")
                if isinstance(email, str) and email.strip():
                    out.append(email.strip())
        return out
    return []


def list_emails(api_key: str, *, limit: int = 25) -> list[dict[str, Any]]:
    for attempt in range(1, 8):
        resp = httpx.get(
            f"{RESEND_API_BASE}/emails",
            headers={"Authorization": f"Bearer {api_key}"},
            params={"limit": limit},
            timeout=20.0,
        )
        if resp.status_code == 429:
            time.sleep(min(0.5 * attempt, 3.0))
            continue
        resp.raise_for_status()
        payload = resp.json()
        if isinstance(payload, dict):
            data = payload.get("data")
            return data if isinstance(data, list) else []
        return payload if isinstance(payload, list) else []
    raise RuntimeError("Resend list endpoint kept returning rate limits")


def get_email(api_key: str, *, email_id: str) -> dict[str, Any]:
    last_payload: dict[str, Any] | None = None
    for attempt in range(1, 8):
        resp = httpx.get(
            f"{RESEND_API_BASE}/emails/{email_id}",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=20.0,
        )
        if resp.status_code in {404, 429}:
            time.sleep(min(0.5 * attempt, 4.0))
            continue
        resp.raise_for_status()
        payload = resp.json()
        if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
            last_payload = payload["data"]
            if _rendered_email_content(last_payload):
                return last_payload
            time.sleep(min(0.5 * attempt, 4.0))
            continue
        if isinstance(payload, dict):
            last_payload = payload
            if _rendered_email_content(last_payload):
                return last_payload
            time.sleep(min(0.5 * attempt, 4.0))
            continue
        raise RuntimeError("Unexpected Resend email detail payload")
    if last_payload is not None:
        return last_payload
    raise RuntimeError("Resend detail endpoint kept returning rate limits")


def _rendered_email_content(payload: dict[str, Any]) -> bool:
    for key in ("html", "text"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return True
    return False


def _message_bodies(payload: dict[str, Any]) -> list[str]:
    bodies: list[str] = []
    for key in ("html", "text"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            bodies.append(value)
    return bodies


def wait_for_email(
    api_key: str,
    *,
    recipient: str,
    sent_after_epoch: float,
    timeout_seconds: int = 180,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    recipient_lower = recipient.lower()
    while time.monotonic() < deadline:
        for email in list_emails(api_key):
            if not isinstance(email, dict):
                continue
            recipients = _normalize_recipients(email.get("to"))
            if recipient_lower not in {item.lower() for item in recipients}:
                continue
            created_epoch = _iso_to_epoch(email.get("created_at"))
            if created_epoch is not None and created_epoch + 5 < sent_after_epoch:
                continue
            return email
        time.sleep(3)
    raise RuntimeError(f"Timed out ({timeout_seconds}s) waiting for signup email to {recipient}")


def extract_confirmation_url(payload: dict[str, Any]) -> str:
    candidates: list[str] = []
    for value in _message_bodies(payload):
        candidates.extend(re.findall(r"https?://[^\s\"'<>]+", value))

    for raw_url in candidates:
        url = html.unescape(raw_url.strip()).rstrip("]")
        for _ in range(3):
            parsed = urlparse(url)
            query = parse_qs(parsed.query)
            if ("token_hash" in query or "token" in query) and "type" in query:
                return url
            decoded = unquote(url)
            if decoded == url:
                break
            url = decoded

    if candidates:
        return html.unescape(candidates[0].strip()).rstrip("]")
    raise RuntimeError("No URL found in Resend payload")


def extract_confirmation_code(payload: dict[str, Any]) -> str:
    candidates = _message_bodies(payload)
    for value in list(candidates):
        if "<" in value and ">" in value:
            candidates.append(re.sub(r"<[^>]+>", " ", value))

    for value in candidates:
        match = CONFIRMATION_CODE_RE.search(value)
        if match:
            return match.group(1)
    raise RuntimeError("No confirmation code found in Resend payload")


def confirmation_callback_url(url: str) -> str | None:
    """Extract callbackURL from a verification link's query params.

    Returns None when the verification link does not embed a callbackURL
    (e.g. Neon Auth ``/verify-email?token=<jwt>`` where the callback is
    stored server-side).
    """
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    raw = (
        (params.get("callbackURL") or [""])[0].strip()
        or (params.get("callbackUrl") or [""])[0].strip()
    )
    if not raw:
        return None
    value = html.unescape(raw)
    for _ in range(3):
        decoded = unquote(value)
        if decoded == value:
            break
        value = decoded
    return value


def assert_confirmation_callback_url(
    url: str,
    *,
    expected_app_base_url: str,
    expected_redirect_uri: str,
    require_pending_login: bool = False,
) -> str | None:
    callback_url = confirmation_callback_url(url)
    if callback_url is None:
        # Neon Auth verify-email links don't embed callbackURL in the URL —
        # the callback is stored server-side. Skip assertion; the actual
        # redirect is validated when the link is followed.
        return None
    actual = urlparse(callback_url)
    expected = urlparse(f"{expected_app_base_url.rstrip('/')}/auth/callback")
    actual_origin_path = f"{actual.scheme}://{actual.netloc}{actual.path}"
    expected_origin_path = f"{expected.scheme}://{expected.netloc}{expected.path}"
    if actual_origin_path != expected_origin_path:
        raise RuntimeError(
            f"Unexpected verification callback target: expected {expected_origin_path}, got {actual_origin_path}"
        )
    params = parse_qs(actual.query)
    if params.get("redirect_uri") != [expected_redirect_uri]:
        raise RuntimeError(
            f"Unexpected verification redirect_uri: expected {expected_redirect_uri!r}, got {params.get('redirect_uri')!r}"
        )
    if require_pending_login and not ((params.get("pending_login") or [""])[0].strip()):
        raise RuntimeError("Verification callback URL missing pending_login")
    return callback_url


def callback_path_from_confirmation_url(url: str) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    verify_type = (params.get("type") or [""])[0].strip()
    token_hash = (params.get("token_hash") or [""])[0].strip()
    token = (params.get("token") or [""])[0].strip()
    if not verify_type:
        raise RuntimeError("Confirmation URL missing type")
    if token_hash:
        return f"/auth/callback?token_hash={token_hash}&type={verify_type}"
    if token:
        return f"/auth/callback?token={token}&type={verify_type}"
    raise RuntimeError("Confirmation URL missing token/token_hash")
