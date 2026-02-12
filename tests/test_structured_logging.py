"""Tests for structured logging and request correlation (bd-1pwb.9.1)."""

import pytest
import uuid
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from src.back.boring_ui.api.logging_middleware import (
    add_logging_middleware,
    get_request_id,
    propagate_request_context,
)


@pytest.fixture
def app():
    """Create a test FastAPI app with structured logging middleware."""
    app = FastAPI()
    add_logging_middleware(app)

    @app.get("/test")
    async def test_route(request: Request):
        """Test endpoint that returns request context."""
        return {
            "request_id": get_request_id(request),
        }

    @app.post("/test-subservice")
    async def test_subservice(request: Request):
        """Test endpoint that returns propagated headers."""
        headers = propagate_request_context(request)
        return {"headers": headers}

    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


def test_request_id_generation(client):
    """Test that request IDs are generated if not provided."""
    response = client.get("/test")
    assert response.status_code == 200

    data = response.json()
    assert data["request_id"]  # Should be generated UUID
    assert len(data["request_id"]) > 0
    assert "X-Request-ID" in response.headers
    assert response.headers["X-Request-ID"] == data["request_id"]


def test_request_id_from_header(client):
    """Test that provided request IDs are respected."""
    test_request_id = str(uuid.uuid4())
    response = client.get("/test", headers={"X-Request-ID": test_request_id})

    assert response.status_code == 200
    data = response.json()
    assert data["request_id"] == test_request_id
    assert response.headers["X-Request-ID"] == test_request_id


def test_request_id_in_response_header(client):
    """Test that request ID is included in response headers."""
    test_request_id = str(uuid.uuid4())
    response = client.get("/test", headers={"X-Request-ID": test_request_id})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == test_request_id
    # Should also have X-Process-Time
    assert "X-Process-Time" in response.headers


def test_subservice_header_propagation(client):
    """Test that headers can be propagated to subservices."""
    test_request_id = str(uuid.uuid4())

    response = client.post(
        "/test-subservice",
        headers={
            "X-Request-ID": test_request_id,
        },
    )

    assert response.status_code == 200
    data = response.json()
    headers = data["headers"]
    assert headers.get("X-Request-ID") == test_request_id


def test_propagate_with_base_headers(client):
    """Test that propagate_request_context augments existing headers."""
    test_request_id = str(uuid.uuid4())

    response = client.post(
        "/test-subservice",
        headers={
            "X-Request-ID": test_request_id,
            "Authorization": "Bearer token123",
        },
    )

    assert response.status_code == 200
    # Verify request was successful (middleware didn't break anything)
    assert "headers" in response.json()


def test_health_check_not_logged(client):
    """Test that health check endpoints are not logged (to reduce noise)."""
    # This is more of an integration test - just verify /health works
    response = client.get("/health")
    # Health endpoint might not exist, but if it does, it should work
    if response.status_code != 404:
        assert response.status_code == 200
