"""Unit tests for service-to-service auth middleware (bd-1pwb.10.1).

Tests:
- add_service_auth_middleware behavior
- Token extraction from X-Service-Token header
- Prefix-based route filtering
- Missing/invalid token semantics
- Service name filtering
- Middleware disabled when validator is None
"""

import pytest
from unittest.mock import MagicMock
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from boring_ui.api.service_auth import (
    add_service_auth_middleware,
    ServiceTokenValidator,
    ServiceTokenSigner,
)

# RSA key pair for tests
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization


@pytest.fixture(scope="module")
def rsa_keys():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_pem, public_pem


def _make_app(validator, prefix="/internal/v1", accepted_services=None):
    app = FastAPI()
    add_service_auth_middleware(app, validator, prefix, accepted_services)

    @app.get("/internal/v1/files/list")
    async def internal_route(request: Request):
        claims = getattr(request.state, "service_auth_claims", None)
        return {"claims": claims is not None}

    @app.get("/api/health")
    async def public_route():
        return {"status": "ok"}

    return app


class TestServiceAuthMiddleware:
    """add_service_auth_middleware behavior."""

    def test_missing_token_returns_401(self, rsa_keys):
        _, public_pem = rsa_keys
        validator = ServiceTokenValidator({1: public_pem})
        app = _make_app(validator)
        tc = TestClient(app)

        resp = tc.get("/internal/v1/files/list")
        assert resp.status_code == 401
        assert resp.json()["code"] == "SERVICE_AUTH_MISSING"

    def test_invalid_token_returns_401(self, rsa_keys):
        _, public_pem = rsa_keys
        validator = ServiceTokenValidator({1: public_pem})
        app = _make_app(validator)
        tc = TestClient(app)

        resp = tc.get(
            "/internal/v1/files/list",
            headers={"X-Service-Token": "invalid-jwt"},
        )
        assert resp.status_code == 401
        assert resp.json()["code"] == "SERVICE_AUTH_INVALID"

    def test_valid_token_succeeds(self, rsa_keys):
        private_pem, public_pem = rsa_keys
        signer = ServiceTokenSigner(private_pem)
        validator = ServiceTokenValidator({1: public_pem})
        app = _make_app(validator)
        tc = TestClient(app)

        token = signer.sign_request(ttl_seconds=60)
        resp = tc.get(
            "/internal/v1/files/list",
            headers={"X-Service-Token": token},
        )
        assert resp.status_code == 200
        assert resp.json()["claims"] is True

    def test_public_route_skips_auth(self, rsa_keys):
        _, public_pem = rsa_keys
        validator = ServiceTokenValidator({1: public_pem})
        app = _make_app(validator)
        tc = TestClient(app)

        resp = tc.get("/api/health")
        assert resp.status_code == 200

    def test_custom_prefix(self, rsa_keys):
        _, public_pem = rsa_keys
        validator = ServiceTokenValidator({1: public_pem})
        app = FastAPI()
        add_service_auth_middleware(app, validator, required_prefix="/custom")

        @app.get("/custom/endpoint")
        async def custom_route(request: Request):
            return {"ok": True}

        @app.get("/other/endpoint")
        async def other_route():
            return {"ok": True}

        tc = TestClient(app)
        # Custom prefix requires auth
        assert tc.get("/custom/endpoint").status_code == 401
        # Other prefix is unprotected
        assert tc.get("/other/endpoint").status_code == 200

    def test_disabled_when_validator_none(self):
        app = FastAPI()
        add_service_auth_middleware(app, None)

        @app.get("/internal/v1/test")
        async def route():
            return {"ok": True}

        tc = TestClient(app)
        resp = tc.get("/internal/v1/test")
        assert resp.status_code == 200

    def test_service_name_filtering(self, rsa_keys):
        private_pem, public_pem = rsa_keys
        signer = ServiceTokenSigner(private_pem, service_name="hosted-api")
        validator = ServiceTokenValidator({1: public_pem})
        app = _make_app(validator, accepted_services=["hosted-api"])
        tc = TestClient(app)

        token = signer.sign_request()
        resp = tc.get(
            "/internal/v1/files/list",
            headers={"X-Service-Token": token},
        )
        assert resp.status_code == 200

    def test_service_name_rejected_when_not_in_list(self, rsa_keys):
        private_pem, public_pem = rsa_keys
        signer = ServiceTokenSigner(private_pem, service_name="rogue-service")
        validator = ServiceTokenValidator({1: public_pem})
        app = _make_app(validator, accepted_services=["hosted-api"])
        tc = TestClient(app)

        token = signer.sign_request()
        resp = tc.get(
            "/internal/v1/files/list",
            headers={"X-Service-Token": token},
        )
        assert resp.status_code == 401

    def test_claims_injected_into_request_state(self, rsa_keys):
        private_pem, public_pem = rsa_keys
        signer = ServiceTokenSigner(private_pem)
        validator = ServiceTokenValidator({1: public_pem})

        app = FastAPI()
        add_service_auth_middleware(app, validator)

        @app.get("/internal/v1/check")
        async def check(request: Request):
            claims = request.state.service_auth_claims
            return {"sub": claims.get("sub"), "key_version": claims.get("key_version")}

        tc = TestClient(app)
        token = signer.sign_request()
        resp = tc.get("/internal/v1/check", headers={"X-Service-Token": token})
        assert resp.status_code == 200
        data = resp.json()
        assert data["sub"] == "hosted-api"
        assert data["key_version"] == 1
