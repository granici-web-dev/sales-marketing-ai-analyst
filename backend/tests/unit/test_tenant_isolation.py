from __future__ import annotations

"""
D-06 required failing test — proves the SQLAlchemy with_loader_criteria
enforcement seam is required and will be tested before implementation is written.

SC#6: DB layer rejects queries when no tenant context is set.
"""

import pytest
from uuid import UUID
from sqlalchemy import select

# These imports will fail until implementation is complete — that is expected.
# The test suite is written first (Wave 0 gate) per CONTEXT.md D-06.
try:
    from app.db.session import AsyncSessionLocal
except ImportError:
    AsyncSessionLocal = None  # type: ignore[assignment]

try:
    from app.models.user import User
except ImportError:
    User = None  # type: ignore[assignment]

try:
    from app.core.exceptions import TenantIsolationError
except ImportError:
    TenantIsolationError = None  # type: ignore[assignment]

try:
    from app.core.tenancy import _tenant_id_var
except ImportError:
    _tenant_id_var = None  # type: ignore[assignment]


async def test_query_without_tenant_context_raises() -> None:
    """SC#6: DB layer rejects queries when no tenant context is set (D-06 required deliverable).

    This test MUST NOT be skipped — it is the required proof that the
    with_loader_criteria enforcement seam exists and is wired correctly.
    When enforcement code is absent, this test fails with ImportError or
    AssertionError — that failing state is expected and intentional.
    """
    if AsyncSessionLocal is None:
        pytest.fail(
            "app.db.session.AsyncSessionLocal not importable — "
            "implementation is missing (this is expected in Wave 0, "
            "but the test stub must exist). D-06 required."
        )
    if User is None:
        pytest.fail(
            "app.models.user.User not importable — "
            "implementation is missing (this is expected in Wave 0). D-06 required."
        )
    if TenantIsolationError is None:
        pytest.fail(
            "app.core.exceptions.TenantIsolationError not importable — "
            "implementation is missing (this is expected in Wave 0). D-06 required."
        )
    if _tenant_id_var is None:
        pytest.fail(
            "app.core.tenancy._tenant_id_var not importable — "
            "implementation is missing (this is expected in Wave 0). D-06 required."
        )

    # Ensure no tenant context is set
    _tenant_id_var.set(None)

    async with AsyncSessionLocal() as session:
        with pytest.raises(TenantIsolationError):
            await session.execute(select(User))


@pytest.mark.skip(reason="Requires live DB — run in integration suite")
async def test_query_with_tenant_context_succeeds() -> None:
    """SC#6: DB layer allows queries when tenant context is set.

    Skipped in unit suite — requires a running PostgreSQL instance.
    This test is covered by the integration suite via test_auth.py
    and test_migrations.py which set up a live DB.
    """
    if AsyncSessionLocal is None or User is None or _tenant_id_var is None:
        pytest.skip("Implementation not yet available")

    _tenant_id_var.set(UUID("00000000-0000-0000-0000-000000000001"))

    async with AsyncSessionLocal() as session:
        # Should NOT raise TenantIsolationError when tenant context is set
        result = await session.execute(select(User))
        assert result is not None
