"""
INFRA-01 and SC#1 integration tests.

Verifies that GET /healthz returns HTTP 200 with JSON body {"status": "ok"}.

This is the primary health check endpoint used by Docker Compose `service_healthy`
condition and external monitoring.

References:
  - INFRA-01: Docker Compose dev stack; /healthz returns 200 within 30s
  - SC#1: Phase 1 success criteria #1
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

# Import stub — survives before implementation exists
try:
    from app.main import app
except ImportError:
    app = None  # type: ignore[assignment]

pytestmark = pytest.mark.integration


async def test_healthz_returns_200() -> None:
    """INFRA-01, SC#1: GET /healthz returns 200 with JSON {status: ok}.

    Uses httpx.AsyncClient with ASGITransport to test the FastAPI app
    in-process without needing a running server.

    This test verifies:
    - The /healthz endpoint exists and is routed correctly
    - The response status code is 200 (not 404, 500, etc.)
    - The JSON body is {"status": "ok"}
    """
    if app is None:
        pytest.skip("app.main.app not importable — implementation pending")

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/healthz")

    assert response.status_code == 200, (
        f"GET /healthz must return 200, got {response.status_code}. "
        f"Body: {response.text}"
    )

    body = response.json()
    assert body == {"status": "ok"}, (
        f"GET /healthz body must be {{\"status\": \"ok\"}}, got: {body}"
    )


async def test_healthz_response_structure() -> None:
    """SC#1: healthz response must be {"status": "ok"} JSON — not just a 200 status.

    Verifies the exact JSON structure. Docker/monitoring systems that parse
    the healthcheck response need a consistent schema.
    """
    if app is None:
        pytest.skip("app.main.app not importable — implementation pending")

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/healthz")

    # Verify it is valid JSON
    assert response.headers.get("content-type", "").startswith("application/json"), (
        f"GET /healthz must return application/json, "
        f"got Content-Type: {response.headers.get('content-type')}"
    )

    body = response.json()

    # Verify "status" key exists and has value "ok"
    assert "status" in body, (
        f"GET /healthz response must have 'status' key. Got: {body}"
    )
    assert body["status"] == "ok", (
        f"GET /healthz 'status' must be 'ok', got '{body['status']}'"
    )
