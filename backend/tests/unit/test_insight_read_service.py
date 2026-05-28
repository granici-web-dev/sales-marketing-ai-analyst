from __future__ import annotations

"""Unit tests for InsightReadService — Phase 6 Plan 02.

Tests mock AsyncSession — no live DB required.
Requirements: INSI-01, INSI-02, INSI-04, INSI-05, INSI-06

All tests will fail with ImportError until Plan 06-02 creates
app.services.insights.insight_read_service.InsightReadService.
"""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


def _make_service(mock_session=None):
    """Build InsightReadService with mocked AsyncSession."""
    from app.services.insights.insight_read_service import InsightReadService  # noqa: PLC0415

    session = mock_session or AsyncMock()
    return InsightReadService(session, TENANT_ID), session


def _mock_insight_row(
    status: str = "success",
    date_val: date | None = None,
    payload_json: dict | None = None,
    generated_at: datetime | None = None,
) -> MagicMock:
    """Build a mock DailyInsight row."""
    row = MagicMock()
    row.date = date_val or date(2026, 5, 27)
    row.status = status
    row.payload_json = payload_json or {"summary": "Test insight"}
    row.generated_at = generated_at or datetime(2026, 5, 28, 6, 7, 23, tzinfo=timezone.utc)
    return row


def _mock_execute_result(scalar=None):
    """Build a mock result returning scalar_one_or_none."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar
    return result


class TestInsightReadServiceGetToday:
    """Tests for InsightReadService.get_today() — INSI-01, INSI-05, INSI-06."""

    @pytest.mark.asyncio
    async def test_get_today_returns_yesterday_insight(self) -> None:
        """get_today returns dict with generation_failed=False when status='success' — INSI-01.

        Mock session returns DailyInsight with status='success'.
        """
        session = AsyncMock()
        yesterday = date(2026, 5, 27)
        row = _mock_insight_row(status="success", date_val=yesterday)

        session.execute = AsyncMock(return_value=_mock_execute_result(scalar=row))

        svc, _ = _make_service(session)

        # Patch Bucharest timezone today to make yesterday deterministic
        fixed_now = datetime(2026, 5, 28, 9, 0, 0)
        with patch(
            "app.services.insights.insight_read_service.datetime"
        ) as mock_dt:
            mock_dt.now.return_value = fixed_now
            result = await svc.get_today()

        assert result is not None
        assert result["generation_failed"] is False
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_get_today_returns_none_when_no_row(self) -> None:
        """get_today returns None when no insight row for yesterday — INSI-01.

        Router will respond with 404 when service returns None.
        """
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_mock_execute_result(scalar=None))

        svc, _ = _make_service(session)

        fixed_now = datetime(2026, 5, 28, 9, 0, 0)
        with patch("app.services.insights.insight_read_service.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_now
            result = await svc.get_today()

        assert result is None

    @pytest.mark.asyncio
    async def test_get_today_failed_status_sets_generation_failed(self) -> None:
        """DailyInsight.status='failed' → generation_failed=True — INSI-05."""
        session = AsyncMock()
        row = _mock_insight_row(status="failed")
        session.execute = AsyncMock(return_value=_mock_execute_result(scalar=row))

        svc, _ = _make_service(session)

        fixed_now = datetime(2026, 5, 28, 9, 0, 0)
        with patch("app.services.insights.insight_read_service.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_now
            result = await svc.get_today()

        assert result is not None
        assert result["generation_failed"] is True

    @pytest.mark.asyncio
    async def test_get_today_fallback_status_sets_generation_failed(self) -> None:
        """DailyInsight.status='fallback' → generation_failed=True — INSI-05."""
        session = AsyncMock()
        row = _mock_insight_row(status="fallback")
        session.execute = AsyncMock(return_value=_mock_execute_result(scalar=row))

        svc, _ = _make_service(session)

        fixed_now = datetime(2026, 5, 28, 9, 0, 0)
        with patch("app.services.insights.insight_read_service.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_now
            result = await svc.get_today()

        assert result is not None
        assert result["generation_failed"] is True


class TestInsightReadServiceGetByDate:
    """Tests for InsightReadService.get_by_date() — INSI-02."""

    @pytest.mark.asyncio
    async def test_get_by_date_returns_none_for_missing(self) -> None:
        """get_by_date returns None for date with no insight row — INSI-02.

        Router will return 404 when service returns None.
        """
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_mock_execute_result(scalar=None))

        svc, _ = _make_service(session)
        result = await svc.get_by_date(date(2026, 5, 15))

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_date_returns_insight_dict(self) -> None:
        """get_by_date returns dict with correct date when row exists — INSI-02."""
        session = AsyncMock()
        query_date = date(2026, 5, 20)
        row = _mock_insight_row(status="success", date_val=query_date)
        session.execute = AsyncMock(return_value=_mock_execute_result(scalar=row))

        svc, _ = _make_service(session)
        result = await svc.get_by_date(query_date)

        assert result is not None
        assert result["date"] == query_date
        assert result["status"] == "success"
        assert "payload" in result
        assert "generated_at" in result
