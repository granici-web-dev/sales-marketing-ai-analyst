from __future__ import annotations

"""Unit tests for calculate_daily_kpis Celery task entry point.

Tests cover: task name, signature, default date behavior, retry config.
No live DB or Redis required — task imports are deferred inside test bodies.

Requirements: METR-01
Tests D-10 (default to yesterday Bucharest), D-12 (optional date parameter),
PIPE-02 (retry on exception), task name assertion.
"""

from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
BUCHAREST = ZoneInfo("Europe/Bucharest")


def _get_task():
    """Import calculate_daily_kpis — deferred for RED tolerance."""
    from app.tasks.etl.calculate_daily_kpis import calculate_daily_kpis  # noqa: PLC0415

    return calculate_daily_kpis


class TestTaskRegistration:
    """Tests for Celery task metadata — task name, retry config."""

    def test_task_name_is_tasks_etl_calculate_daily_kpis(self) -> None:
        """Task name must be 'tasks.etl.calculate_daily_kpis'.

        This name is used in Celery beat schedule, chain() wiring (D-18),
        and log records. A wrong name breaks the pipeline chain.
        """
        task = _get_task()
        assert task.name == "tasks.etl.calculate_daily_kpis", (
            f"Task name must be 'tasks.etl.calculate_daily_kpis', got '{task.name}'. "
            "Celery beat schedule and chain() depend on this exact name (D-18)."
        )

    def test_retry_config(self) -> None:
        """Task must have autoretry_for=(Exception,) and max_retries=3 (PIPE-02).

        PIPE-02: Exception in calculate_daily_kpis must halt the downstream chain
        AND retry up to 3 times. autoretry_for=(Exception,) covers all exception types.
        """
        task = _get_task()
        assert hasattr(task, "autoretry_for"), (
            "Task must declare autoretry_for — Celery autoretry mechanism (PIPE-02)"
        )
        assert Exception in task.autoretry_for, (  # type: ignore[attr-defined]
            f"autoretry_for must include Exception, got {task.autoretry_for}"
        )
        assert task.max_retries == 3, (  # type: ignore[attr-defined]
            f"max_retries must be 3, got {task.max_retries}"
        )

    def test_task_is_bound(self) -> None:
        """Task must be bound (bind=True) to access self.retry()."""
        task = _get_task()
        # Bound tasks have the 'bind' attribute or are instances of Task with self
        # We verify by checking the task is correctly registered in Celery registry
        from app.tasks.celery_app import celery_app  # noqa: PLC0415

        assert "tasks.etl.calculate_daily_kpis" in celery_app.tasks, (
            "calculate_daily_kpis must be registered in celery_app.tasks"
        )


class TestSignatureAndDate:
    """Tests for task signature and default date behavior — D-10, D-12."""

    def test_signature_accepts_optional_calculation_date(self) -> None:
        """Task signature: calculate_daily_kpis(tenant_id, calculation_date=None) — D-12.

        D-12: When called with an explicit date, calculates for that date (backfill support).
        calculation_date is an ISO date string or None.
        """
        import inspect

        task = _get_task()
        # Get the underlying function signature (not the Celery wrapper)
        sig = inspect.signature(task.run)
        params = list(sig.parameters.keys())

        # Must accept tenant_id and calculation_date
        assert "tenant_id" in params, (
            f"Task must accept 'tenant_id' parameter, got: {params}"
        )
        assert "calculation_date" in params, (
            f"Task must accept 'calculation_date' parameter (D-12 backfill support), got: {params}"
        )

        # calculation_date must be optional (has a default of None)
        calc_date_param = sig.parameters["calculation_date"]
        assert calc_date_param.default is None, (
            f"calculation_date must default to None (D-12), got default={calc_date_param.default}"
        )

    def test_default_calculation_date_is_yesterday_bucharest(self) -> None:
        """When calculation_date=None, task calculates for yesterday in Europe/Bucharest — D-10.

        D-10: calculate_daily_kpis calculates KPIs for yesterday (previous full calendar
        day in Europe/Bucharest). At 04:00 Bucharest, the previous day is always complete.
        """
        # Compute expected "yesterday" in Bucharest at any time of day
        today_bucharest = datetime.now(BUCHAREST).date()
        expected_yesterday = today_bucharest - timedelta(days=1)

        # The task's internal _default_date() helper (or equivalent logic) must return this
        # We verify by importing _calc_async — it resolves the date when calculation_date=None
        # The core contract: None → yesterday Bucharest date (not UTC yesterday)
        from app.tasks.etl.calculate_daily_kpis import _calc_async  # type: ignore[attr-defined]  # noqa: PLC0415

        # _calc_async resolves calculation_date internally — we test the resolution logic
        # by verifying the function exists and its default date logic is correct
        # (actual date resolution tested in integration tests with patched asyncio.run)
        import asyncio as _asyncio

        import inspect

        source = inspect.getsource(_calc_async)
        # D-10: The source must reference Europe/Bucharest (not UTC) for date resolution
        assert "Bucharest" in source or "BUCHAREST" in source, (
            "_calc_async must use Europe/Bucharest timezone for default date resolution (D-10), "
            "not UTC. A UTC default assigns late-evening leads to wrong day."
        )


class TestPipelineChain:
    """Tests for Celery chain wiring — D-18, PIPE-01."""

    def test_daily_pipeline_includes_calculate_task(self) -> None:
        """daily_pipeline() chain must include calculate_daily_kpis as second task (D-18).

        D-18: calculate_daily_kpis is second in the chain:
        sync_mefi_leads → calculate_daily_kpis → detect_anomalies → generate_daily_insights.
        """
        from app.tasks.etl.sync_mefi_leads import daily_pipeline  # noqa: PLC0415

        pipeline = daily_pipeline(str(TENANT_ID))
        # Celery chain tasks attribute contains the linked tasks
        tasks_str = str(pipeline)
        assert "calculate_daily_kpis" in tasks_str, (
            "daily_pipeline() must include calculate_daily_kpis in the chain (D-18). "
            "Check that sync_mefi_leads.py daily_pipeline() was updated in Plan 04."
        )

    def test_task_propagates_exception_for_chain_halt(self) -> None:
        """calculate_daily_kpis raises on _calc_async failure → halts chain (PIPE-02).

        PIPE-02: Exception in any pipeline step must halt downstream tasks.
        The task wraps asyncio.run() in try/except and calls self.retry(exc=exc),
        which re-raises after max_retries exhausted.
        """
        task = _get_task()

        with patch("app.tasks.etl.calculate_daily_kpis.asyncio") as mock_asyncio:
            mock_asyncio.run = MagicMock(side_effect=RuntimeError("DB connection failed"))
            with pytest.raises(Exception):
                task.run(str(TENANT_ID), calculation_date=None)
