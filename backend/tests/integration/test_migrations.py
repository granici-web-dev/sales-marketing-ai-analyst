"""
PIPE-04 and SC#2 integration tests.

Verifies that `alembic upgrade head` creates all required base tables with
correct schema (columns, types, constraints).

Required tables (SPEC.md §7, Phase 1):
  - tenants
  - users
  - sync_runs
  - pipeline_runs

These tests connect directly to a disposable test database via asyncpg.
They gate on TEST_DATABASE_URL, like every other integration test here.
DATABASE_URL is the application's own variable: finding it set says the app
is configured, not that a database safe to inspect is running.
"""

from __future__ import annotations

import os

import pytest

try:
    import asyncpg
except ImportError:
    asyncpg = None  # type: ignore[assignment]

pytestmark = pytest.mark.integration


async def test_tables_exist() -> None:
    """PIPE-04, SC#2: alembic upgrade head must create all base tables.

    Connects to the PostgreSQL database and queries information_schema.tables
    to verify all four Phase 1 tables exist in the 'public' schema.

    Required tables: tenants, users, sync_runs, pipeline_runs
    """
    if asyncpg is None:
        pytest.skip("asyncpg not installed — install with: uv pip install asyncpg")

    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL not set — integration test requires a live DB")

    # asyncpg uses postgresql:// not postgresql+asyncpg://
    conn_str = database_url.replace("postgresql+asyncpg://", "postgresql://")

    conn = await asyncpg.connect(conn_str)
    try:
        rows = await conn.fetch(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE'
            """
        )
        existing_tables = {row["table_name"] for row in rows}

        required_tables = {"tenants", "users", "sync_runs", "pipeline_runs"}
        missing = required_tables - existing_tables

        assert not missing, (
            f"Missing tables after alembic upgrade head: {missing}. "
            f"Existing tables: {existing_tables}. "
            "Run: alembic upgrade head"
        )
    finally:
        await conn.close()


async def test_tenant_id_not_null_constraint() -> None:
    """PIPE-04: users.tenant_id must be NOT NULL in the database schema.

    Queries information_schema.columns to verify the column-level constraint.
    """
    if asyncpg is None:
        pytest.skip("asyncpg not installed")

    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL not set")

    conn_str = database_url.replace("postgresql+asyncpg://", "postgresql://")

    conn = await asyncpg.connect(conn_str)
    try:
        row = await conn.fetchrow(
            """
            SELECT is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'users'
              AND column_name = 'tenant_id'
            """
        )

        assert row is not None, (
            "users.tenant_id column not found in information_schema — did alembic upgrade head run?"
        )
        assert row["is_nullable"] == "NO", (
            f"users.tenant_id must be NOT NULL. "
            f"information_schema shows is_nullable='{row['is_nullable']}'"
        )
    finally:
        await conn.close()


async def test_timestamps_are_timestamptz() -> None:
    """INFRA-02, SC#2: users.created_at must use TIMESTAMPTZ in PostgreSQL.

    TIMESTAMPTZ stores timezone-aware timestamps (UTC internally).
    Plain TIMESTAMP (without time zone) is ambiguous and not acceptable.
    """
    if asyncpg is None:
        pytest.skip("asyncpg not installed")

    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL not set")

    conn_str = database_url.replace("postgresql+asyncpg://", "postgresql://")

    conn = await asyncpg.connect(conn_str)
    try:
        row = await conn.fetchrow(
            """
            SELECT data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'users'
              AND column_name = 'created_at'
            """
        )

        assert row is not None, (
            "users.created_at column not found in information_schema — "
            "did alembic upgrade head run?"
        )
        assert row["data_type"] == "timestamp with time zone", (
            f"users.created_at must be TIMESTAMPTZ ('timestamp with time zone'). "
            f"Got: '{row['data_type']}'. "
            "Check alembic migration — use TIMESTAMPTZ, not TIMESTAMP."
        )
    finally:
        await conn.close()
