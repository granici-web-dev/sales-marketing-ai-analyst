"""Unit tests for calculate_daily_kpis Celery task entry point.

Tests cover: task name, signature, default date behavior, retry config.
No live DB or Redis required — task imports are deferred inside test bodies.

Requirements: METR-01
Tests D-10 (default to yesterday Bucharest), D-12 (optional date parameter),
PIPE-02 (retry on exception), task name assertion.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
BUCHAREST = ZoneInfo("Europe/Bucharest")


def _get_task():
    """Import calculate_daily_kpis — deferred for RED tolerance."""
    from app.tasks.etl.calculate_daily_kpis import calculate_daily_kpis  # deferred (INFRA-05)

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
        """Task must be bound (bind=True) — `self.retry()` needs it to exist.

        Registration alone does not prove boundness, and this test used to check
        only registration while its name promised more.
        """
        from app.tasks.celery_app import celery_app  # deferred (INFRA-05)

        assert "tasks.etl.calculate_daily_kpis" in celery_app.tasks, (
            "calculate_daily_kpis must be registered in celery_app.tasks"
        )
        import functools  # deferred (INFRA-05)

        # Celery binds `self` by storing the header as a partial over a sentinel;
        # with bind=False the header is the plain function. `__bound__` is not the
        # tell — it means bound-to-an-app and is True either way.
        header = celery_app.tasks["tasks.etl.calculate_daily_kpis"].__header__
        assert isinstance(header, functools.partial), (
            "calculate_daily_kpis must be declared with bind=True — without it "
            "the task body has no `self` and the retry path cannot run"
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
        assert "tenant_id" in params, f"Task must accept 'tenant_id' parameter, got: {params}"
        assert "calculation_date" in params, (
            f"Task must accept 'calculation_date' parameter (D-12 backfill support), got: {params}"
        )

        # calculation_date must be optional (has a default of None)
        calc_date_param = sig.parameters["calculation_date"]
        assert calc_date_param.default is None, (
            f"calculation_date must default to None (D-12), got default={calc_date_param.default}"
        )

    def test_default_calculation_date_is_yesterday_bucharest(self) -> None:
        """calculation_date=None resolves to yesterday in Europe/Bucharest — D-10.

        At 04:00 Bucharest the previous local day is always complete. Resolving
        against UTC instead would, between local midnight and 02:00, file the
        previous evening's leads under the wrong day.
        """
        from app.tasks.etl.calculate_daily_kpis import resolve_kpi_date  # deferred (INFRA-05)

        expected = datetime.now(BUCHAREST).date() - timedelta(days=1)
        assert resolve_kpi_date(None) == expected

    def test_utc_would_disagree_at_local_midnight(self) -> None:
        """The Bucharest rule is not the UTC rule — D-10.

        01:00 on 1 July in Bucharest is 22:00 on 30 June in UTC. Yesterday is
        30 June locally and 29 June in UTC; this asserts the resolver picks the
        local answer, and fails against a UTC implementation.
        """
        import app.tasks.etl.calculate_daily_kpis as mod  # deferred (INFRA-05)

        local_1am = datetime(2026, 7, 1, 1, 0, tzinfo=BUCHAREST)
        assert local_1am.astimezone(UTC).date() == date(2026, 6, 30)

        class _FrozenDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return local_1am.astimezone(tz)

        original = mod.datetime
        mod.datetime = _FrozenDatetime
        try:
            assert mod.resolve_kpi_date(None) == date(2026, 6, 30)
        finally:
            mod.datetime = original

    def test_supplied_date_is_parsed_not_interpolated(self) -> None:
        """An explicit date is parsed into a `date`; a malformed one raises — T-03-04-02."""
        from app.tasks.etl.calculate_daily_kpis import resolve_kpi_date  # deferred (INFRA-05)

        assert resolve_kpi_date("2026-03-14") == date(2026, 3, 14)
        with pytest.raises(ValueError, match="Invalid isoformat|day is out of range"):
            resolve_kpi_date("2026-02-30'; DROP TABLE daily_kpi; --")


class TestPipelineChain:
    """Tests for Celery chain wiring — D-18, PIPE-01."""

    def test_daily_pipeline_includes_calculate_task(self) -> None:
        """daily_pipeline() chain must include calculate_daily_kpis as second task (D-18).

        D-18: calculate_daily_kpis is second in the chain:
        sync_mefi_leads → calculate_daily_kpis → detect_anomalies → generate_daily_insights.
        """
        from app.tasks.etl.sync_mefi_leads import daily_pipeline  # deferred (INFRA-05)

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

        # _calc_async is patched alongside asyncio: patching only asyncio still
        # evaluates the inner `_calc_async(...)` call to build the argument, so a
        # coroutine is created and never awaited. Python reports that whenever
        # the collector next runs, which lands the warning on some unrelated
        # test — it was showing up under test_celery_app.
        with (
            patch("app.tasks.etl.calculate_daily_kpis.asyncio") as mock_asyncio,
            patch("app.tasks.etl.calculate_daily_kpis._calc_async", MagicMock()),
        ):
            mock_asyncio.run = MagicMock(side_effect=RuntimeError("DB connection failed"))
            with pytest.raises(RuntimeError, match="DB connection failed"):
                task.run(str(TENANT_ID), calculation_date=None)
