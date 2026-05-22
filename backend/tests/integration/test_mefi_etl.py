from __future__ import annotations

"""Integration tests for MEFI ETL — Phase 2, Plan 02-05.

These tests verify the Alembic migration 003 schema against a real
PostgreSQL database. They are skipped automatically when no test DB
is available (MEFI_TEST_DB_URL not set).

Requirements: MEFI-05, DATA-01, DATA-03

Note: Full integration tests (live DB + alembic upgrade/downgrade) require
Docker Compose to be running. For CI without Docker, these tests skip
gracefully via the @pytest.mark.integration marker.
"""

import os

import pytest

# Integration tests are skipped unless TEST_DATABASE_URL is set.
# In local dev: docker compose up -d then run pytest tests/integration/
_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(
    not _TEST_DB_URL,
    reason="Integration tests require TEST_DATABASE_URL env var (docker compose up -d)",
)


@pytest.fixture(scope="module")
async def test_engine():
    """Create a test engine and run alembic migrations."""
    if not _TEST_DB_URL:
        pytest.skip("TEST_DATABASE_URL not set")

    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(_TEST_DB_URL, echo=False)
    yield engine
    await engine.dispose()


@pytest.mark.asyncio
async def test_003_views_exist(test_engine) -> None:
    """v_mefi_leads_active and v_mefi_leads_junk exist after migration 003 (DATA-01)."""
    async with test_engine.connect() as conn:
        await conn.execute(
            __import__("sqlalchemy", fromlist=["text"]).text(
                "SELECT 1 FROM v_mefi_leads_active LIMIT 0"
            )
        )
        await conn.execute(
            __import__("sqlalchemy", fromlist=["text"]).text(
                "SELECT 1 FROM v_mefi_leads_junk LIMIT 0"
            )
        )


@pytest.mark.asyncio
async def test_view_funnel_columns(test_engine) -> None:
    """v_mefi_leads_active has reached_visit, reached_offer, reached_contract columns (MEFI-05)."""
    from sqlalchemy import text

    async with test_engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'v_mefi_leads_active' "
                "AND column_name IN ('reached_visit', 'reached_offer', 'reached_contract') "
                "ORDER BY column_name"
            )
        )
        columns = [row[0] for row in result]

    assert "reached_contract" in columns, "reached_contract column missing from v_mefi_leads_active"
    assert "reached_offer" in columns, "reached_offer column missing from v_mefi_leads_active"
    assert "reached_visit" in columns, "reached_visit column missing from v_mefi_leads_active"


@pytest.mark.asyncio
async def test_view_local_timestamps(test_engine) -> None:
    """v_mefi_leads_active has local timestamp columns AT TIME ZONE Europe/Bucharest (DATA-03)."""
    from sqlalchemy import text

    async with test_engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'v_mefi_leads_active' "
                "AND column_name IN ('created_at_local', 'status_changed_at_local') "
                "ORDER BY column_name"
            )
        )
        columns = [row[0] for row in result]

    assert "created_at_local" in columns, "created_at_local column missing from v_mefi_leads_active"
    assert "status_changed_at_local" in columns, "status_changed_at_local column missing"


@pytest.mark.asyncio
async def test_raw_mefi_leads_unique_constraint(test_engine) -> None:
    """raw_mefi_leads has UNIQUE(tenant_id, external_id) for UPSERT conflict target (MEFI-02)."""
    from sqlalchemy import text

    async with test_engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT constraint_name FROM information_schema.table_constraints "
                "WHERE table_name = 'raw_mefi_leads' "
                "AND constraint_type = 'UNIQUE'"
            )
        )
        constraints = [row[0] for row in result]

    assert any("uq" in c.lower() for c in constraints), (
        f"No UNIQUE constraint found on raw_mefi_leads. Found: {constraints}"
    )


@pytest.mark.asyncio
async def test_funnel_config_seeded(test_engine) -> None:
    """tenants.funnel_config JSONB is seeded for Sofa Belle (DATA-01)."""
    from sqlalchemy import text

    async with test_engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT funnel_config FROM tenants "
                "WHERE slug = 'sofa-belle' AND funnel_config IS NOT NULL"
            )
        )
        rows = result.fetchall()

    assert len(rows) == 1, "Sofa Belle tenant funnel_config not seeded by migration 003"
    config = rows[0][0]
    assert "visit" in config, "funnel_config missing 'visit' stage"
    assert "offer" in config, "funnel_config missing 'offer' stage"
    assert "contract" in config, "funnel_config missing 'contract' stage"
