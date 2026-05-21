from __future__ import annotations

import pytest
from uuid import UUID

# Import stubs — wrapped in try/except to survive before implementation exists
try:
    from app.main import app as _app
except ImportError:
    _app = None  # type: ignore[assignment]

try:
    from app.db.session import AsyncSessionLocal as _AsyncSessionLocal
except ImportError:
    _AsyncSessionLocal = None  # type: ignore[assignment]

try:
    from app.core.tenancy import set_tenant_id as _set_tenant_id
except ImportError:
    _set_tenant_id = None  # type: ignore[assignment]


# Test tenant constant — Sofa Belle pilot tenant
TEST_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture
async def async_client():
    """Async HTTP client for FastAPI app testing.

    Yields an httpx.AsyncClient pointed at the FastAPI app.
    Yields None if the app is not yet implemented (pre-implementation stubs pass).
    """
    if _app is None:
        yield None
        return

    from httpx import AsyncClient, ASGITransport

    async with AsyncClient(
        transport=ASGITransport(app=_app),
        base_url="http://test",
    ) as client:
        yield client


@pytest.fixture
async def db_session():
    """Async SQLAlchemy session with tenant context set.

    Sets the tenant context var to TEST_TENANT_ID before yielding.
    Rolls back on teardown to keep tests isolated.
    Yields None if the session factory is not yet implemented.
    """
    if _AsyncSessionLocal is None or _set_tenant_id is None:
        yield None
        return

    _set_tenant_id(TEST_TENANT_ID)

    async with _AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.rollback()


@pytest.fixture
def test_tenant() -> dict:
    """Returns a dict representing the Sofa Belle test tenant.

    Does not require a database connection — used by unit tests.
    """
    return {
        "id": TEST_TENANT_ID,
        "name": "Sofa Belle",
    }
