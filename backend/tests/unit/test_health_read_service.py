"""Unit tests for HealthReadService — Phase 6 Plan 02.

Tests mock AsyncSession — no live DB required.
Requirements: UI-06, PIPE-04

All tests will fail with ImportError until Plan 06-02 creates
app.services.dashboards.health_read_service.HealthReadService.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


def _make_service(mock_session=None):
    """Build HealthReadService with mocked AsyncSession."""
    from app.services.dashboards.health_read_service import HealthReadService  # deferred (INFRA-05)

    session = mock_session or AsyncMock()
    return HealthReadService(session, TENANT_ID), session


def _mock_execute_multi(sync_row=None, pipeline_row=None):
    """Return a session mock with side_effect for two sequential execute calls."""
    session = AsyncMock()

    sync_result = MagicMock()
    sync_result.first.return_value = sync_row

    pipeline_result = MagicMock()
    pipeline_result.first.return_value = pipeline_row

    session.execute = AsyncMock(side_effect=[sync_result, pipeline_result])
    return session


class TestHealthReadService:
    """Tests for HealthReadService.get_health() — UI-06, PIPE-04."""

    @pytest.mark.asyncio
    async def test_health_stale_when_last_sync_over_26h(self) -> None:
        """stale=True when last_sync_at is 27h ago — UI-06."""
        now_utc = datetime.now(UTC)
        last_sync_at = now_utc - timedelta(hours=27)

        sync_row = MagicMock()
        sync_row.completed_at = last_sync_at
        sync_row.status = "success"

        pipeline_row = MagicMock()
        pipeline_row.status = "success"

        session = _mock_execute_multi(sync_row=sync_row, pipeline_row=pipeline_row)
        svc, _ = _make_service(session)

        result = await svc.get_health()

        assert result["stale"] is True

    @pytest.mark.asyncio
    async def test_health_not_stale_when_recent(self) -> None:
        """stale=False when last_sync_at is 1h ago — UI-06."""
        now_utc = datetime.now(UTC)
        last_sync_at = now_utc - timedelta(hours=1)

        sync_row = MagicMock()
        sync_row.completed_at = last_sync_at
        sync_row.status = "success"

        pipeline_row = MagicMock()
        pipeline_row.status = "success"

        session = _mock_execute_multi(sync_row=sync_row, pipeline_row=pipeline_row)
        svc, _ = _make_service(session)

        result = await svc.get_health()

        assert result["stale"] is False

    @pytest.mark.asyncio
    async def test_health_stale_when_no_sync_run(self) -> None:
        """stale=True when no SyncRun row found — UI-06."""
        session = _mock_execute_multi(sync_row=None, pipeline_row=None)
        svc, _ = _make_service(session)

        result = await svc.get_health()

        assert result["stale"] is True
        assert result["last_sync_at"] is None

    @pytest.mark.asyncio
    async def test_health_last_pipeline_status(self) -> None:
        """last_pipeline_status = PipelineRun.status of most recent run — PIPE-04."""
        now_utc = datetime.now(UTC)

        sync_row = MagicMock()
        sync_row.completed_at = now_utc - timedelta(hours=1)
        sync_row.status = "success"

        pipeline_row = MagicMock()
        pipeline_row.status = "success"

        session = _mock_execute_multi(sync_row=sync_row, pipeline_row=pipeline_row)
        svc, _ = _make_service(session)

        result = await svc.get_health()

        assert result["last_pipeline_status"] == "success"

    @pytest.mark.asyncio
    async def test_health_last_pipeline_status_none_when_no_pipeline_run(self) -> None:
        """last_pipeline_status = None when no PipelineRun row — PIPE-04."""
        now_utc = datetime.now(UTC)

        sync_row = MagicMock()
        sync_row.completed_at = now_utc - timedelta(hours=2)
        sync_row.status = "success"

        session = _mock_execute_multi(sync_row=sync_row, pipeline_row=None)
        svc, _ = _make_service(session)

        result = await svc.get_health()

        assert result["last_pipeline_status"] is None

    @pytest.mark.asyncio
    async def test_health_returns_last_sync_at(self) -> None:
        """last_sync_at = SyncRun.completed_at of most recent mefi sync."""
        now_utc = datetime.now(UTC)
        completed = now_utc - timedelta(hours=2)

        sync_row = MagicMock()
        sync_row.completed_at = completed
        sync_row.status = "success"

        pipeline_row = MagicMock()
        pipeline_row.status = "success"

        session = _mock_execute_multi(sync_row=sync_row, pipeline_row=pipeline_row)
        svc, _ = _make_service(session)

        result = await svc.get_health()

        assert result["last_sync_at"] == completed
