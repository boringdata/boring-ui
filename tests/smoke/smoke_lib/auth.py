"""Supabase auth flows: signup, email confirmation, signin + token exchange."""
from __future__ import annotations

import random
import string
import time

import httpx

from .client import SmokeClient
from .resend import (
    callback_path_from_confirmation_url,
    extract_confirmation_url,
    get_email,
    wait_for_email,
)


def random_password() -> str:
    alphabet = string.ascii_letters + string.digits
    tail = "".join(random.choice(alphabet) for _ in range(14))
    return f"Aa1!{tail}"


def supabase_signup(
    *,
    supabase_url: str,
    supabase_anon_key: str,
    email: str,
    password: str,
    redirect_base: str = "http://127.0.0.1:8000",
    max_attempts: int = 3,
) -> httpx.Response:
    last_resp: httpx.Response | None = None
    for attempt in range(1, max_attempts + 1):
        resp = httpx.post(
            f"{supabase_url}/auth/v1/signup",
            headers={
                "apikey": supabase_anon_key,
                "Authorization": f"Bearer {supabase_anon_key}",
                "Content-Type": "application/json",
            },
            json={
                "email": email,
                "password": password,
                "options": {
                    "email_redirect_to": f"{redirect_base}/auth/callback?redirect_uri=%2F",
                },
            },
            timeout=30.0,
        )
        if resp.status_code in {200, 201}:
            return resp
        last_resp = resp
        if resp.status_code != 429:
            break
        retry_after = resp.headers.get("retry-after", "").strip()
        delay = int(retry_after) if retry_after.isdigit() else min(5 * attempt, 45)
        time.sleep(min(max(delay, 1), 60))
    if last_resp is None:
        raise RuntimeError("Signup failed before receiving any response")
    return last_resp


def supabase_signin(
    *,
    supabase_url: str,
    supabase_anon_key: str,
    email: str,
    password: str,
) -> dict:
    resp = httpx.post(
        f"{supabase_url}/auth/v1/token?grant_type=password",
        headers={
            "apikey": supabase_anon_key,
            "Authorization": f"Bearer {supabase_anon_key}",
            "Content-Type": "application/json",
        },
        json={"email": email, "password": password},
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()


def signup_flow(
    client: SmokeClient,
    *,
    supabase_url: str,
    supabase_anon_key: str,
    resend_api_key: str,
    email: str,
    password: str,
    timeout_seconds: int = 180,
) -> str:
    """Full signup: Supabase signup -> wait for email -> confirm via callback.

    Returns the callback path used.
    """
    client.set_phase("signup")
    sent_after = time.time()

    print(f"[smoke] Signing up {email}...")
    resp = supabase_signup(
        supabase_url=supabase_url,
        supabase_anon_key=supabase_anon_key,
        email=email,
        password=password,
        redirect_base=client.base_url,
    )
    if resp.status_code not in {200, 201}:
        raise RuntimeError(f"Signup failed: {resp.status_code} {resp.text[:300]}")

    print(f"[smoke] Waiting for confirmation email...")
    email_summary = wait_for_email(
        resend_api_key,
        recipient=email,
        sent_after_epoch=sent_after,
        timeout_seconds=timeout_seconds,
    )
    email_id = str(email_summary.get("id") or "").strip()
    if not email_id:
        raise RuntimeError("Resend list did not include email id")
    email_details = get_email(resend_api_key, email_id=email_id)

    confirmation_url = extract_confirmation_url(email_details)
    callback_path = callback_path_from_confirmation_url(confirmation_url)

    print(f"[smoke] Confirming email via callback...")
    client.set_phase("confirm")
    resp = client.get(callback_path, expect_status=(302,))
    if resp.status_code != 302:
        raise RuntimeError(f"Callback did not redirect: {resp.status_code} {resp.text[:300]}")
    location = resp.headers.get("location", "")
    if not location.startswith("/"):
        raise RuntimeError(f"Unexpected callback redirect: {location}")

    return callback_path


def signin_flow(
    client: SmokeClient,
    *,
    supabase_url: str,
    supabase_anon_key: str,
    email: str,
    password: str,
) -> dict:
    """Sign in via Supabase password grant + boring-ui token-exchange.

    Returns the session payload from /auth/session.
    """
    client.set_phase("signin")
    print(f"[smoke] Signing in {email}...")
    token_data = supabase_signin(
        supabase_url=supabase_url,
        supabase_anon_key=supabase_anon_key,
        email=email,
        password=password,
    )
    access_token = token_data.get("access_token")
    if not access_token:
        raise RuntimeError("Supabase signin did not return access_token")

    resp = client.post(
        "/auth/token-exchange",
        json={"access_token": access_token, "redirect_uri": "/"},
        expect_status=(200,),
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Token exchange failed: {resp.status_code} {resp.text[:300]}")
    payload = resp.json()
    if not payload.get("ok"):
        raise RuntimeError(f"Token exchange not ok: {payload}")

    client.set_phase("session-check")
    session_resp = client.get("/auth/session", expect_status=(200,))
    if session_resp.status_code != 200:
        raise RuntimeError(f"Session check failed: {session_resp.status_code}")
    session = session_resp.json()
    user_email = (session.get("user") or {}).get("email", "")
    if str(user_email).strip().lower() != email.lower():
        raise RuntimeError(f"Session email mismatch: expected {email}, got {user_email}")
    print(f"[smoke] Session verified for {email}")
    return session
