"""Auth boundary integration tests for Phase 6 endpoints.

Verifies that protected endpoints reject requests without a valid JWT (401)
and that the public /health/data endpoint does NOT require auth.

These tests use dependency_overrides to avoid real DB/Redis connections.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.asyncio


MOCK_USER_ID = UUID("00000000-0000-0000-0000-000000000002")


@pytest.fixture
def app_with_overrides():
    """FastAPI app with DB session mock — avoids real DB connections."""
    from app.db.deps import get_session
    from app.main import app

    mock_session = AsyncMock()

    async def _mock_get_session():
        yield mock_session

    app.dependency_overrides[get_session] = _mock_get_session
    yield app
    app.dependency_overrides.pop(get_session, None)


async def test_sales_dashboard_requires_auth(app_with_overrides) -> None:
    """GET /dashboards/sales without Authorization → 401/403."""
    async with AsyncClient(
        transport=ASGITransport(app=app_with_overrides),
        base_url="http://test",
    ) as client:
        r = await client.get("/api/v1/dashboards/sales?from=2026-05-01&to=2026-05-19")
    assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}"


async def test_salespeople_dashboard_requires_auth(app_with_overrides) -> None:
    """GET /dashboards/salespeople without Authorization → 401/403."""
    async with AsyncClient(
        transport=ASGITransport(app=app_with_overrides),
        base_url="http://test",
    ) as client:
        r = await client.get("/api/v1/dashboards/salespeople?from=2026-05-01&to=2026-05-19")
    assert r.status_code in (401, 403)


async def test_marketing_dashboard_requires_auth(app_with_overrides) -> None:
    """GET /dashboards/marketing without Authorization → 401/403."""
    async with AsyncClient(
        transport=ASGITransport(app=app_with_overrides),
        base_url="http://test",
    ) as client:
        r = await client.get("/api/v1/dashboards/marketing?from=2026-05-01&to=2026-05-19")
    assert r.status_code in (401, 403)


async def test_insights_today_requires_auth(app_with_overrides) -> None:
    """GET /insights/today without Authorization → 401/403."""
    async with AsyncClient(
        transport=ASGITransport(app=app_with_overrides),
        base_url="http://test",
    ) as client:
        r = await client.get("/api/v1/insights/today")
    assert r.status_code in (401, 403)


async def test_insights_by_date_requires_auth(app_with_overrides) -> None:
    """GET /insights?date=... without Authorization → 401/403."""
    async with AsyncClient(
        transport=ASGITransport(app=app_with_overrides),
        base_url="http://test",
    ) as client:
        r = await client.get("/api/v1/insights?date=2026-05-01")
    assert r.status_code in (401, 403)


async def test_insights_refresh_requires_auth(app_with_overrides) -> None:
    """POST /insights/refresh without Authorization → 401/403."""
    async with AsyncClient(
        transport=ASGITransport(app=app_with_overrides),
        base_url="http://test",
    ) as client:
        r = await client.post("/api/v1/insights/refresh")
    assert r.status_code in (401, 403)


async def test_health_data_requires_auth(app_with_overrides) -> None:
    """Свежесть данных — данные арендатора, и без спроса не отдаются.

    Прежде эндпоинт был единственным без проверки, и держалось это на том, что
    арендатор приходил из настройки: любой запрос получал состояние Sofa Belle.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app_with_overrides),
        base_url="http://test",
    ) as client:
        r = await client.get("/api/v1/health/data")

    assert r.status_code in (401, 403), f"ожидался отказ, получено {r.status_code}"
