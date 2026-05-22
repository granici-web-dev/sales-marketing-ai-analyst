from __future__ import annotations

"""Unit tests for sync_mefi_leads Celery task.

Tests mock Redis, MefiClient, and AsyncSession. No live DB or Redis required.

Requirements: MEFI-08, MEFI-11, MEFI-12, PIPE-01, PIPE-02
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tasks.etl.sync_mefi_leads import get_cf


class TestGetCf:
    """Tests for get_cf() custom field extractor helper."""

    def test_none_fields_returns_none(self) -> None:
        assert get_cf(None, 14) is None

    def test_empty_list_returns_none(self) -> None:
        assert get_cf([], 14) is None

    def test_field_found_by_field_id(self) -> None:
        fields = [{"field_id": 14, "value": "Brașov"}]
        assert get_cf(fields, 14) == "Brașov"

    def test_field_found_by_id(self) -> None:
        fields = [{"id": 14, "value": "Cluj"}]
        assert get_cf(fields, 14) == "Cluj"

    def test_field_not_found_returns_none(self) -> None:
        fields = [{"field_id": 99, "value": "Other"}]
        assert get_cf(fields, 14) is None

    def test_offer_flag_true_mapping(self) -> None:
        """'✅DA' is the MEFI value for offer_sent=True (DATA-02)."""
        fields = [{"field_id": 20, "value": "✅DA"}]
        assert get_cf(fields, 20) == "✅DA"

    def test_offer_flag_false_mapping(self) -> None:
        """'❌NU' is the MEFI value for offer_sent=False."""
        fields = [{"field_id": 20, "value": "❌NU"}]
        assert get_cf(fields, 20) == "❌NU"


class TestRedisLock:
    """Tests for Redis advisory lock in sync_mefi_leads (MEFI-11)."""

    @pytest.mark.asyncio
    async def test_lock_held_returns_noop(self) -> None:
        """When Redis lock is already held, _sync_async returns noop (MEFI-11).

        set_tenant_id is a deferred import inside _sync_async — patch at source.
        aioredis is a module-level import — patch on the task module.
        """
        from app.tasks.etl.sync_mefi_leads import _sync_async
        import uuid

        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=None)  # None = lock already held
        mock_redis.delete = AsyncMock()
        mock_redis.aclose = AsyncMock()

        with patch("app.tasks.etl.sync_mefi_leads.aioredis") as mock_aioredis, \
             patch("app.core.tenancy.set_tenant_id"), \
             patch("app.core.config.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_settings.mefi_api_key = "lrd_test"
            mock_settings.sofa_belle_tenant_id = str(tenant_id)
            mock_aioredis.from_url = MagicMock(return_value=mock_redis)

            result = await _sync_async(tenant_id)

        assert result["status"] == "noop"
        assert result["reason"] == "lock_held"
        mock_redis.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_lock_released_after_noop(self) -> None:
        """When lock is held, delete is NOT called (we never acquired it)."""
        from app.tasks.etl.sync_mefi_leads import _sync_async
        import uuid

        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=None)
        mock_redis.aclose = AsyncMock()

        with patch("app.tasks.etl.sync_mefi_leads.aioredis") as mock_aioredis, \
             patch("app.core.tenancy.set_tenant_id"), \
             patch("app.core.config.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost"
            mock_settings.mefi_api_key = "lrd_test"
            mock_aioredis.from_url = MagicMock(return_value=mock_redis)

            await _sync_async(tenant_id)

        mock_redis.delete.assert_not_called()


class TestBeatSchedule:
    """Tests for Celery beat schedule configuration (PIPE-01)."""

    def test_task_routes_has_backfill_queue(self) -> None:
        """celery_app.conf.task_routes routes backfill to 'backfill' queue (PIPE-01)."""
        from app.tasks.celery_app import celery_app

        routes = celery_app.conf.task_routes
        assert "tasks.etl.backfill_mefi_leads" in routes
        assert routes["tasks.etl.backfill_mefi_leads"]["queue"] == "backfill"

    def test_etl_include_in_celery_app(self) -> None:
        """celery_app includes 'app.tasks.etl' module for task discovery (PIPE-01)."""
        from app.tasks.celery_app import celery_app

        assert "app.tasks.etl" in celery_app.conf.include

    def test_sync_mefi_leads_task_name(self) -> None:
        """sync_mefi_leads task name matches the beat schedule key."""
        from app.tasks.etl.sync_mefi_leads import sync_mefi_leads

        assert sync_mefi_leads.name == "tasks.etl.sync_mefi_leads"

    def test_celery_timezone_bucharest(self) -> None:
        """Celery timezone is Europe/Bucharest (INFRA-04, PIPE-01)."""
        from app.tasks.celery_app import celery_app

        assert celery_app.conf.timezone == "Europe/Bucharest"


class TestBackfillMonthWindows:
    """Tests for 12-month window calculation — MEFI-12."""

    def test_12_windows_returned(self) -> None:
        from app.tasks.etl.backfill_mefi_leads import get_12_month_windows

        windows = get_12_month_windows(date(2026, 5, 21))
        assert len(windows) == 12

    def test_first_window_is_12_months_ago(self) -> None:
        from app.tasks.etl.backfill_mefi_leads import get_12_month_windows

        windows = get_12_month_windows(date(2026, 5, 21))
        assert windows[0][0] == date(2025, 5, 1)
        assert windows[0][1] == date(2025, 5, 31)

    def test_last_window_is_previous_month(self) -> None:
        from app.tasks.etl.backfill_mefi_leads import get_12_month_windows

        windows = get_12_month_windows(date(2026, 5, 21))
        assert windows[-1][0] == date(2026, 4, 1)
        assert windows[-1][1] == date(2026, 4, 30)

    def test_current_month_excluded(self) -> None:
        """The current partial month must not appear (D-04)."""
        from app.tasks.etl.backfill_mefi_leads import get_12_month_windows

        windows = get_12_month_windows(date(2026, 5, 21))
        window_starts = [w[0] for w in windows]
        assert date(2026, 5, 1) not in window_starts


class TestTaskChainHalt:
    """Tests for PIPE-02 — exception in sync halts downstream pipeline."""

    def test_sync_leads_propagates_exceptions(self) -> None:
        """If _sync_async raises, sync_mefi_leads propagates (PIPE-02)."""
        from app.tasks.etl.sync_mefi_leads import sync_mefi_leads

        with patch("app.tasks.etl.sync_mefi_leads.asyncio") as mock_asyncio:
            mock_asyncio.run = MagicMock(side_effect=RuntimeError("No data for today"))
            with pytest.raises(RuntimeError, match="No data for today"):
                sync_mefi_leads.run("00000000-0000-0000-0000-000000000001")

    def test_uuid_validation_at_entry(self) -> None:
        """sync_mefi_leads raises ValueError on malformed tenant_id (T-02-11)."""
        from app.tasks.etl.sync_mefi_leads import sync_mefi_leads

        with patch("app.tasks.etl.sync_mefi_leads.asyncio") as mock_asyncio:
            mock_asyncio.run = MagicMock()
            with pytest.raises((ValueError, AttributeError)):
                sync_mefi_leads.run("not-a-valid-uuid")
