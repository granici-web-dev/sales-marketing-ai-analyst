"""Unit tests for InsightRepository — RED-state contracts for Phase 5.

All tests will fail with ImportError until Plan 05-02 (Wave 2) implements
app.services.repositories.insight_repository.InsightRepository.

Tests mock AsyncSession — no live DB required.

Requirements: D-16, Pitfall 6 (tenant isolation on Core INSERT), WR-04

Patterns tested:
  D-16: UPSERT to daily_insights on (tenant_id, date) unique constraint
  Pitfall 6: tenant_id validated before INSERT (with_loader_criteria bypassed by Core INSERT)
  WR-04: upsert_daily_insight does NOT commit (caller commits atomically)
  Cross-tenant write guard: repo tenant_id must match row tenant_id
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from tests.factories.insight_factory import make_insight_row

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
TODAY = date(2026, 5, 28)


def _make_repo(mock_session=None, tenant_id=None):
    """Build InsightRepository with mocked AsyncSession.

    Import deferred — file parses (RED) before Plan 05-02 implements InsightRepository.
    Returns (repo, session) tuple.
    """
    from app.services.repositories.insight_repository import (
        InsightRepository,  # deferred (INFRA-05)
    )

    session = mock_session or AsyncMock()
    tid = tenant_id or TENANT_ID
    return InsightRepository(session, tid), session


class TestUpsertDailyInsight:
    """Tests for InsightRepository.upsert_daily_insight() — D-16, Pitfall 6, WR-04."""

    @pytest.mark.asyncio
    async def test_upsert_calls_session_execute(self) -> None:
        """upsert_daily_insight() must call session.execute() once (D-16 UPSERT).

        D-16: ON CONFLICT (tenant_id, date) DO UPDATE — one row per tenant per day.
        Execution is delegated to session.execute() with SQLAlchemy Core INSERT statement.
        """
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        session.execute = AsyncMock(return_value=mock_result)

        repo, _ = _make_repo(session)
        row = make_insight_row()
        await repo.upsert_daily_insight(row)

        (
            session.execute.assert_called_once(),
            ("upsert_daily_insight() must call session.execute() exactly once (D-16)"),
        )

    @pytest.mark.asyncio
    async def test_upsert_raises_on_missing_tenant_id(self) -> None:
        """upsert_daily_insight() raises ValueError if row is missing tenant_id (Pitfall 6).

        Pitfall 6: with_loader_criteria only fires on ORM SELECT — Core INSERT bypasses it.
        InsightRepository must validate tenant_id explicitly before executing INSERT.
        Pattern mirrors MetricsRepository and AnomalyRepository from Phase 3/4.
        """
        repo, _ = _make_repo()

        # Row without tenant_id key
        row_without_tenant = {
            "date": TODAY,
            "status": "success",
            "payload_json": {},
            "input_tokens": 3000,
            "output_tokens": 2000,
        }

        with pytest.raises(ValueError, match="missing tenant_id"):
            await repo.upsert_daily_insight(row_without_tenant)

    @pytest.mark.asyncio
    async def test_upsert_raises_on_cross_tenant_write(self) -> None:
        """upsert_daily_insight() raises ValueError if row.tenant_id != repo.tenant_id (Pitfall 6).

        Security guard: repo initialized with tenant_id=A must reject rows with tenant_id=B.
        Prevents cross-tenant data corruption (multi-tenancy correctness requirement).
        """
        TENANT_A = UUID("00000000-0000-0000-0000-000000000001")
        TENANT_B = UUID("00000000-0000-0000-0000-000000000002")

        repo, _ = _make_repo(tenant_id=TENANT_A)
        row_with_wrong_tenant = make_insight_row(tenant_id=TENANT_B)

        # Without `match` this passes on any ValueError — including one raised
        # for an unrelated reason — and the cross-tenant guard goes unproven.
        with pytest.raises(ValueError, match="cross-tenant write blocked"):
            await repo.upsert_daily_insight(row_with_wrong_tenant)

    @pytest.mark.asyncio
    async def test_upsert_does_not_commit(self) -> None:
        """upsert_daily_insight() must NOT call session.commit() (WR-04).

        WR-04: Repository methods do not commit — the Celery task caller
        is responsible for committing atomically after all writes complete.
        Early commit in the repo would break atomicity on partial failure.
        """
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        session.execute = AsyncMock(return_value=mock_result)

        repo, _ = _make_repo(session)
        row = make_insight_row()
        await repo.upsert_daily_insight(row)

        (
            session.commit.assert_not_called(),
            (
                "upsert_daily_insight() must NOT call session.commit() — "
                "caller (generate_daily_insights task) commits atomically (WR-04)"
            ),
        )
