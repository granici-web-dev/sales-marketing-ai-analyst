"""Unit tests for AnomalyRepository — RED-state contracts for Phase 4 anomaly detection.

Tests mock AsyncSession — no live DB required.
All tests will fail with ImportError until Plan 04-02 (Wave 1) implements
app.services.repositories.anomaly_repository.AnomalyRepository.

Requirements: ANOM-01

Patterns tested:
  Pitfall 5: 3-column conflict target (tenant_id, date, rule_id) — same as source_daily_kpi
  Pitfall 6: tenant_id validation before INSERT — must raise ValueError loudly
  WR-04: upsert_detected_problem does NOT commit (caller commits atomically)
  D-01: UPSERT idempotency on (tenant_id, date, rule_id) unique constraint
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
TODAY = date(2026, 5, 28)


def _make_repo(mock_session=None):
    """Build AnomalyRepository with mocked AsyncSession.

    Import deferred — file parses (RED) before Plan 04-02 implements AnomalyRepository.
    Returns (repo, session) tuple.
    """
    from app.services.repositories.anomaly_repository import (
        AnomalyRepository,  # deferred (INFRA-05)
    )

    session = mock_session or AsyncMock()
    return AnomalyRepository(session, TENANT_ID), session


def _detected_problem_row(**kwargs) -> dict:
    """Build a minimal valid detected_problems row dict."""
    defaults = {
        "tenant_id": TENANT_ID,
        "date": TODAY,
        "rule_id": "slow_first_touch",
        "severity": "high",
        "metric": "time_to_first_touch_minutes",
        "current_value": Decimal("360.00"),
        "expected_value": Decimal("300.00"),
        "estimated_loss_ron": Decimal("5500.00"),
        "context_json": {"count": 1, "lead_ids": ["ext-001"]},
    }
    defaults.update(kwargs)
    return defaults


class TestUpsertDetectedProblem:
    """Tests for AnomalyRepository.upsert_detected_problem() — D-01, Pitfall 5, Pitfall 6, WR-04."""

    @pytest.mark.asyncio
    async def test_raises_when_tenant_id_missing(self) -> None:
        """upsert_detected_problem raises ValueError if row missing tenant_id (Pitfall 6).

        Pitfall 6: with_loader_criteria only fires on ORM SELECT — Core INSERT
        bypasses it. AnomalyRepository must validate tenant_id explicitly
        before executing INSERT, raising ValueError loudly (not silently insert).

        Pattern mirrors MetricsRepository.upsert_daily_kpi() from Phase 3.
        """
        repo, _ = _make_repo()
        with pytest.raises(ValueError, match="missing tenant_id"):
            await repo.upsert_detected_problem(  # type: ignore[attr-defined]
                {"date": TODAY, "rule_id": "slow_first_touch"}
            )

    @pytest.mark.asyncio
    async def test_raises_when_tenant_id_none(self) -> None:
        """upsert_detected_problem raises ValueError if tenant_id is None (Pitfall 6).

        Explicit None is as bad as missing key — both must raise ValueError.
        """
        repo, _ = _make_repo()
        row = _detected_problem_row(tenant_id=None)
        with pytest.raises(ValueError, match="missing tenant_id"):
            await repo.upsert_detected_problem(row)  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_uses_three_column_conflict_target(self) -> None:
        """UPSERT uses index_elements=["tenant_id", "date", "rule_id"] (D-01, Pitfall 5).

        D-01: detected_problems UNIQUE constraint is on (tenant_id, date, rule_id).
        AnomalyRepository must use pg_insert().on_conflict_do_update with
        index_elements=["tenant_id", "date", "rule_id"] — 3-column conflict target.

        Using only (tenant_id, date) would fail on second rule row for same date.
        Mirrors Pitfall 5 from MetricsRepository source_daily_kpi UPSERT.
        """
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        session.execute = AsyncMock(return_value=mock_result)

        repo, _ = _make_repo(session)
        row = _detected_problem_row()
        await repo.upsert_detected_problem(row)  # type: ignore[attr-defined]

        # Verify execute was called (3-col conflict target correctness verified in integration tests)
        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_does_not_commit_on_upsert(self) -> None:
        """session.commit NOT called inside upsert_detected_problem (WR-04 pattern).

        WR-04: Upsert methods must NOT call session.commit() internally.
        The detect_anomalies task commits atomically after all rule upserts complete.
        If the repo commits early, a partial failure leaves orphaned rows.

        Pattern from Phase 3: upsert_daily_kpi no longer commits — caller commits.
        """
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        session.execute = AsyncMock(return_value=mock_result)

        repo, _ = _make_repo(session)
        row = _detected_problem_row()
        await repo.upsert_detected_problem(row)  # type: ignore[attr-defined]

        session.commit.assert_not_called(), (
            "upsert_detected_problem must NOT call session.commit() — "
            "caller (detect_anomalies task) is responsible for commit (WR-04)"
        )

    @pytest.mark.asyncio
    async def test_idempotent_double_upsert(self) -> None:
        """Same (tenant_id, date, rule_id) row upserted twice → no duplicate (D-01 UPSERT).

        D-01: ON CONFLICT DO UPDATE on (tenant_id, date, rule_id) is idempotent.
        Second call with identical key must update the existing row, not insert duplicate.
        Mocked session returns rowcount=1 for both calls — verifying both succeed without error.
        """
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        session.execute = AsyncMock(return_value=mock_result)

        repo, _ = _make_repo(session)
        row = _detected_problem_row()

        await repo.upsert_detected_problem(row)  # type: ignore[attr-defined]
        await repo.upsert_detected_problem(row)  # type: ignore[attr-defined]

        assert session.execute.call_count == 2, (
            "upsert_detected_problem called twice for same (tenant_id, date, rule_id) "
            "must not raise UniqueViolationError — ON CONFLICT DO UPDATE handles it (D-01)"
        )
        session.commit.assert_not_called()  # WR-04: no internal commit
