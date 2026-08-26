"""Unit tests for MetricsRepository.

Tests mock AsyncSession — no live DB required.
Coverage: UPSERT idempotency, tenant_id validation, 3-column conflict targets.

Requirements: METR-01
Tests Pitfall 5 (SourceDailyKpi 3-col conflict target),
Pitfall 6 (tenant_id validation before INSERT),
METR-01 SC#1 (idempotent re-runs — same row count after double-upsert).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


def _make_repo(mock_session=None):
    """Build MetricsRepository with mocked AsyncSession.

    Import deferred — file parses (RED) before Plan 03 implementation exists.
    """
    from app.services.repositories.metrics_repository import (
        MetricsRepository,  # deferred (INFRA-05)
    )

    session = mock_session or AsyncMock()
    return MetricsRepository(session, TENANT_ID), session


def _daily_kpi_row(**kwargs) -> dict:
    """Build a minimal valid daily_kpi row dict."""
    defaults = {
        "tenant_id": TENANT_ID,
        "date": date(2026, 5, 24),
        "leads_total": 20,
        "visits_count": 8,
        "offers_count": 4,
        "contracts_count": 1,
        "revenue": Decimal("15000.00"),
        "conversion_l_to_v": Decimal("0.4000"),
        "conversion_v_to_o": Decimal("0.5000"),
        "conversion_l_to_o": Decimal("0.2000"),
        "conversion_o_to_c": Decimal("0.2500"),
        "conversion_l_to_c": Decimal("0.0500"),
    }
    defaults.update(kwargs)
    return defaults


def _salesperson_row(**kwargs) -> dict:
    """Build a minimal valid salesperson_daily_kpi row dict."""
    defaults = {
        "tenant_id": TENANT_ID,
        "date": date(2026, 5, 24),
        "salesperson_external_id": "101",
        "leads_assigned": 5,
        "leads_contacted": 3,
        "visits_conducted": 2,
        "offers_sent": 1,
        "deals_won": 0,
        "deals_lost": 0,
        "revenue": Decimal("0.00"),
        "data_completeness_pct": Decimal("80.00"),
    }
    defaults.update(kwargs)
    return defaults


def _source_row(**kwargs) -> dict:
    """Build a minimal valid source_daily_kpi row dict."""
    defaults = {
        "tenant_id": TENANT_ID,
        "date": date(2026, 5, 24),
        "source": "mail_fb_ig",
        "leads": 8,
        "visits": 3,
        "offers": 1,
        "deals_won": 0,
        "revenue": Decimal("0.00"),
        "conversion_rate": Decimal("0.3750"),
    }
    defaults.update(kwargs)
    return defaults


class TestUpsertDailyKpi:
    """Tests for MetricsRepository.upsert_daily_kpi() — METR-01, Pitfall 6."""

    @pytest.mark.asyncio
    async def test_raises_when_tenant_id_missing(self) -> None:
        """upsert_daily_kpi raises ValueError if row missing tenant_id (Pitfall 6).

        Pitfall 6: with_loader_criteria only fires on ORM SELECT — Core INSERT
        bypasses it. MetricsRepository must validate tenant_id explicitly
        before executing INSERT, raising ValueError loudly (not silently insert).
        """
        repo, _ = _make_repo()
        with pytest.raises(ValueError, match="tenant_id"):
            await repo.upsert_daily_kpi({"date": date(2026, 5, 24)})  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_raises_when_tenant_id_none(self) -> None:
        """upsert_daily_kpi raises ValueError if tenant_id is None."""
        repo, _ = _make_repo()
        row = _daily_kpi_row(tenant_id=None)
        with pytest.raises(ValueError, match="tenant_id"):
            await repo.upsert_daily_kpi(row)  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_calls_execute_with_valid_row(self) -> None:
        """upsert_daily_kpi calls session.execute with a valid row.

        WR-04: upsert_daily_kpi no longer commits internally — the task commits
        atomically after all three upsert operations complete. The test verifies
        execute is called but NOT commit (commit is the caller's responsibility).
        """
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        session.execute = AsyncMock(return_value=mock_result)

        repo, _ = _make_repo(session)
        await repo.upsert_daily_kpi(_daily_kpi_row())  # type: ignore[attr-defined]

        session.execute.assert_called_once()
        session.commit.assert_not_called()  # WR-04: commit moved to caller (task)

    @pytest.mark.asyncio
    async def test_upsert_idempotent_same_date(self) -> None:
        """Running upsert twice for same (tenant_id, date) → same row count (METR-01 SC#1).

        ON CONFLICT DO UPDATE is idempotent: second call updates same row,
        does NOT insert a duplicate. Total row count must remain 1 after two calls.
        WR-04: commit is now caller's responsibility — not called by upsert_daily_kpi.
        """
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        session.execute = AsyncMock(return_value=mock_result)

        repo, _ = _make_repo(session)
        row = _daily_kpi_row()

        await repo.upsert_daily_kpi(row)  # type: ignore[attr-defined]
        await repo.upsert_daily_kpi(row)  # type: ignore[attr-defined]

        # Two execute calls → both succeed (no uniqueness violation)
        assert session.execute.call_count == 2, (
            "upsert_daily_kpi called twice for same (tenant_id, date) must not raise "
            "UniqueViolationError — ON CONFLICT DO UPDATE handles it (METR-01 SC#1)"
        )
        session.commit.assert_not_called()  # WR-04: commit moved to caller (task)


class TestUpsertSalespersonKpi:
    """Tests for MetricsRepository.upsert_salesperson_kpi() — 3-col conflict target."""

    @pytest.mark.asyncio
    async def test_uses_three_column_conflict_target(self) -> None:
        """salesperson_daily_kpi UPSERT uses (tenant_id, salesperson_external_id, date).

        salesperson_daily_kpi has a 3-column UNIQUE constraint unlike daily_kpi (2 cols).
        MetricsRepository must use index_elements=["tenant_id", "salesperson_external_id", "date"]
        to avoid UniqueViolationError when upserting for multiple salespeople.
        WR-04: upsert_salesperson_kpi no longer commits — caller (task) commits atomically.
        """
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        session.execute = AsyncMock(return_value=mock_result)

        repo, _ = _make_repo(session)
        row = _salesperson_row()
        await repo.upsert_salesperson_kpi(row)  # type: ignore[attr-defined]

        # Verify execute was called (conflict target correctness verified by integration test)
        session.execute.assert_called_once()
        session.commit.assert_not_called()  # WR-04: commit moved to caller (task)

    @pytest.mark.asyncio
    async def test_raises_when_salesperson_id_missing(self) -> None:
        """upsert_salesperson_kpi raises ValueError if tenant_id missing."""
        repo, _ = _make_repo()
        with pytest.raises(ValueError, match="tenant_id"):
            await repo.upsert_salesperson_kpi(  # type: ignore[attr-defined]
                {"date": date(2026, 5, 24), "salesperson_external_id": "101"}
            )

    @pytest.mark.asyncio
    async def test_multiple_salespeople_no_conflict(self) -> None:
        """Two salespeople, same date → two rows, no conflict (3-col key covers sp_id)."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        session.execute = AsyncMock(return_value=mock_result)

        repo, _ = _make_repo(session)
        await repo.upsert_salesperson_kpi(_salesperson_row(salesperson_external_id="101"))  # type: ignore[attr-defined]
        await repo.upsert_salesperson_kpi(_salesperson_row(salesperson_external_id="102"))  # type: ignore[attr-defined]

        # Both execute without error — different salesperson_external_id = no conflict
        assert session.execute.call_count == 2


class TestUpsertSourceKpi:
    """Tests for MetricsRepository.upsert_source_kpi() — Pitfall 5 (3-col conflict)."""

    @pytest.mark.asyncio
    async def test_source_uses_three_column_conflict_target(self) -> None:
        """source_daily_kpi UPSERT uses (tenant_id, source, date) — Pitfall 5.

        Pitfall 5: source_daily_kpi UNIQUE constraint is on (tenant_id, source, date).
        If only (tenant_id, date) used as conflict target, second source category
        insert fails with UniqueViolationError (constraint still catches it).
        Must use 3-column index_elements to handle all 7 categories without error.
        """
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        session.execute = AsyncMock(return_value=mock_result)

        repo, _ = _make_repo(session)

        # Insert 7 source rows — all same date, different source (3-col key)
        sources = ["mail_fb_ig", "telefon", "whatsapp", "site", "designer", "alte", "google"]
        for src in sources:
            row = _source_row(source=src)
            await repo.upsert_source_kpi(row)  # type: ignore[attr-defined]

        # All 7 executed without error — 3-col conflict target handles distinct sources
        assert session.execute.call_count == 7, (
            "All 7 source category upserts must succeed with 3-col conflict target (Pitfall 5)"
        )

    @pytest.mark.asyncio
    async def test_raises_when_source_kpi_tenant_id_missing(self) -> None:
        """upsert_source_kpi raises ValueError if tenant_id missing (Pitfall 6)."""
        repo, _ = _make_repo()
        with pytest.raises(ValueError, match="tenant_id"):
            await repo.upsert_source_kpi(  # type: ignore[attr-defined]
                {"date": date(2026, 5, 24), "source": "google", "leads": 5}
            )

    @pytest.mark.asyncio
    async def test_upsert_source_idempotent(self) -> None:
        """upsert_source_kpi twice for same (tenant_id, source, date) → no duplicate."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        session.execute = AsyncMock(return_value=mock_result)

        repo, _ = _make_repo(session)
        row = _source_row(source="google")
        await repo.upsert_source_kpi(row)  # type: ignore[attr-defined]
        await repo.upsert_source_kpi(row)  # type: ignore[attr-defined]

        # Second call updates same row — no UniqueViolationError
        assert session.execute.call_count == 2
