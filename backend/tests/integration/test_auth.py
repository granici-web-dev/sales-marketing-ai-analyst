from __future__ import annotations

"""
AUTH-01 and AUTH-02 integration tests.

AUTH-01: POST /api/v1/auth/login with valid credentials returns:
  - HTTP 200
  - JSON body with access_token and token_type="bearer"
  - Set-Cookie header with refresh_token as HttpOnly cookie

AUTH-02: POST /api/v1/auth/refresh with valid refresh cookie returns:
  - HTTP 200
  - New access_token in JSON body
  - Rotated refresh_token in Set-Cookie header

These tests require the FastAPI app + database with seeded Sofa Belle admin user.
They will fail with ImportError or skip until implementation is complete.
"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


async def test_login_success(async_client: AsyncClient) -> None:
    """AUTH-01: Login with valid credentials returns 200 + access_token JSON + HttpOnly refresh cookie.

    Asserts:
    - HTTP 200 status
    - JSON body contains "access_token" key
    - JSON body has "token_type": "bearer"
    - Set-Cookie response header contains "refresh_token" and "HttpOnly"
    """
    if async_client is None:
        pytest.skip("FastAPI app not available — implementation pending")

    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@sofabelle.ro", "password": "Admin1234!"},
    )

    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}. Body: {response.text}"
    )

    body = response.json()
    assert "access_token" in body, (
        f"Response body must have 'access_token' key. Got: {body}"
    )
    assert body.get("token_type") == "bearer", (
        f"Response body must have 'token_type': 'bearer'. Got: {body}"
    )

    # Verify HttpOnly refresh cookie is set
    set_cookie_header = response.headers.get("set-cookie", "")
    assert "refresh_token" in set_cookie_header, (
        f"Set-Cookie header must contain 'refresh_token'. Got: '{set_cookie_header}'"
    )
    assert "HttpOnly" in set_cookie_header, (
        f"Set-Cookie header must contain 'HttpOnly' flag. Got: '{set_cookie_header}'"
    )


async def test_login_invalid_credentials(async_client: AsyncClient) -> None:
    """AUTH-01: Login with wrong password returns 401 Unauthorized."""
    if async_client is None:
        pytest.skip("FastAPI app not available — implementation pending")

    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@sofabelle.ro", "password": "wrong_password_123"},
    )

    assert response.status_code == 401, (
        f"Expected 401 for invalid credentials, got {response.status_code}"
    )


async def test_refresh_rotates(async_client: AsyncClient) -> None:
    """AUTH-02: Refresh token endpoint rotates cookie and returns new access token.

    Flow:
    1. POST /api/v1/auth/login to get initial refresh_token cookie
    2. POST /api/v1/auth/refresh with that cookie
    3. Assert: new access_token in body, new refresh_token in Set-Cookie

    The refresh cookie is rotated on every call — the old one is invalidated
    and a new one is issued (prevents cookie theft replay attacks).
    """
    if async_client is None:
        pytest.skip("FastAPI app not available — implementation pending")

    # Step 1: Login to get refresh cookie
    login_response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@sofabelle.ro", "password": "Admin1234!"},
    )
    assert login_response.status_code == 200, (
        f"Login prerequisite failed with {login_response.status_code}"
    )

    # Step 2: Refresh using the cookie (httpx follows cookies automatically)
    refresh_response = await async_client.post("/api/v1/auth/refresh")

    assert refresh_response.status_code == 200, (
        f"Expected 200 from /auth/refresh, got {refresh_response.status_code}. "
        f"Body: {refresh_response.text}"
    )

    body = refresh_response.json()
    assert "access_token" in body, (
        f"/auth/refresh must return new 'access_token'. Got: {body}"
    )

    # Verify rotated refresh cookie is set
    set_cookie_header = refresh_response.headers.get("set-cookie", "")
    assert "refresh_token" in set_cookie_header, (
        f"Set-Cookie from /auth/refresh must contain 'refresh_token'. Got: '{set_cookie_header}'"
    )


async def test_protected_route_without_token(async_client: AsyncClient) -> None:
    """AUTH-01/AUTH-03: GET a protected route without auth returns 401 or 307 redirect to /login.

    The FastAPI backend returns 401 for unauthenticated API calls.
    The Next.js proxy.ts redirects browser requests to /login (AUTH-03 — tested via Playwright).
    """
    if async_client is None:
        pytest.skip("FastAPI app not available — implementation pending")

    # Attempt to access a protected endpoint without providing any auth token
    response = await async_client.get("/api/v1/me")  # or another protected endpoint

    # Backend should return 401 (API client)
    # proxy.ts would return 307 for browser requests — not testable here
    assert response.status_code in (401, 307, 403), (
        f"Expected 401/307/403 for unauthenticated request, got {response.status_code}"
    )
