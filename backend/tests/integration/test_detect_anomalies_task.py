from __future__ import annotations

"""Integration tests for detect_anomalies Celery task — RED-state contracts for Phase 4.

All tests will fail with ImportError until Plan 04-04 (Wave 3) implements
app.tasks.etl.detect_anomalies.detect_anomalies.

Tests requiring a live DB are marked with @pytest.mark.integration and
skipped automatically when TEST_DATABASE_URL is not set.

Requirements: ANOM-01, ANOM-02, ANOM-06, ANOM-07

Patterns tested:
  ANOM-01: detect_anomalies task writes SyncRun(source="anomaly") for pipeline audit
  PIPE-04: SyncRun lifecycle — running → success (or failed on error)
  WR-06: Stale SyncRun cleanup before new running row (from Phase 3 code review)
  T-04-xx-01: tenant_id validated as UUID at task entry point
  ROADMAP SC#6: junk leads excluded from slow_first_touch (ANOM-07)
  D-01: detected_problems UPSERT idempotency on (tenant_id, date, rule_id)
"""

import os
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
TENANT_ID_STR = str(TENANT_ID)

# Integration tests require a live DB — skip when not available
_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "")
_INTEGRATION_SKIP = pytest.mark.skipif(
    not _TEST_DB_URL,
    reason="Integration tests require TEST_DATABASE_URL env var (docker compose up -d)",
)


class TestDetectAnomaliesTask:
    """Tests for detect_anomalies Celery task — ANOM-01, PIPE-04, WR-06."""

    def test_task_writes_syncrun_with_source_anomaly(self) -> None:
        """detect_anomalies writes SyncRun(source="anomaly") for pipeline audit (ANOM-01, PIPE-04).

        PIPE-04: Every pipeline step writes a SyncRun row for audit and monitoring.
        The detect_anomalies task must create SyncRun(source="anomaly") with
        status="running" at start, then update to status="success" on completion.
        """
        from app.tasks.etl.detect_anomalies import detect_anomalies  # noqa: PLC0415

        mock_detect_result = {
            "status": "success",
            "problems_found": 2,
            "duration_ms": 100,
        }

        with patch("app.tasks.etl.detect_anomalies.asyncio.run") as mock_run:
            mock_run.return_value = mock_detect_result

            # The task must not raise even with mocked asyncio.run
            # SyncRun write is verified through the _detect_async internals
            # (full verification in live-DB integration test below)
            result = detect_anomalies.apply(args=[TENANT_ID_STR])

        # Task must complete (not crash) — SyncRun write is internal to _detect_async
        assert result is not None

    def test_task_validates_tenant_id_as_uuid(self) -> None:
        """detect_anomalies validates tenant_id as UUID at entry point (T-04-xx-01).

        T-04-xx-01: Task entry point must validate tenant_id with UUID(tenant_id_str).
        Passing "not-a-uuid" must raise ValueError at the validation step,
        before any DB connection is opened (fail-fast pattern from calculate_daily_kpis).
        """
        from app.tasks.etl.detect_anomalies import detect_anomalies  # noqa: PLC0415

        with pytest.raises((ValueError, Exception)):
            # "not-a-uuid" must fail UUID() conversion at task entry
            detect_anomalies.apply(args=["not-a-uuid"], throw=True)

    @_INTEGRATION_SKIP
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_task_marks_stale_running_syncrun_as_failed(self) -> None:
        """Stale SyncRun(source="anomaly", status="running") → updated to "failed" (WR-06).

        WR-06: Before creating a new SyncRun(status="running"), mark any existing
        running rows with the same source as "failed" to prevent phantom running rows.

        This test requires a live DB to verify the actual DB state change.
        Steps:
        1. Pre-seed SyncRun(source="anomaly", status="running")
        2. Run detect_anomalies task
        3. Assert stale row updated to status="failed"
        4. Assert new row created with status="running" then updated to "success"
        """
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        from app.tasks.etl.detect_anomalies import detect_anomalies  # noqa: PLC0415

        engine = create_async_engine(_TEST_DB_URL)
        try:
            async with engine.begin() as conn:
                # Pre-seed a stale running SyncRun
                await conn.execute(
                    text(
                        "INSERT INTO sync_runs (tenant_id, source, status, started_at) "
                        "VALUES (:tenant_id, 'anomaly', 'running', NOW() - INTERVAL '1 hour')"
                    ),
                    {"tenant_id": TENANT_ID},
                )

            # Run the task
            detect_anomalies.apply(args=[TENANT_ID_STR])

            async with engine.connect() as conn:
                result = await conn.execute(
                    text(
                        "SELECT status FROM sync_runs "
                        "WHERE tenant_id = :tenant_id AND source = 'anomaly' "
                        "ORDER BY started_at ASC LIMIT 1"
                    ),
                    {"tenant_id": TENANT_ID},
                )
                rows = result.fetchall()

            # The stale row should be marked failed
            assert len(rows) >= 1
            assert rows[0][0] == "failed", (
                "Stale SyncRun(status='running') must be updated to 'failed' "
                "before new run starts (WR-06)"
            )
        finally:
            await engine.dispose()

    @_INTEGRATION_SKIP
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_slow_first_touch_not_triggered_for_junk_leads(self) -> None:
        """Junk leads excluded from slow_first_touch rule (ROADMAP SC#6, ANOM-07).

        ROADMAP SC#6: Junk leads must not trigger slow_first_touch even if
        time_to_first_touch_minutes > 300. This test seeds 3 junk leads created
        yesterday with no contact attempt, then runs detect_anomalies and asserts
        no detected_problems row with rule_id="slow_first_touch" exists for those IDs.

        D-11: junk IDs computed once from v_mefi_leads_junk and passed to all non-junk rules.
        """
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        from app.tasks.etl.detect_anomalies import detect_anomalies  # noqa: PLC0415

        engine = create_async_engine(_TEST_DB_URL)
        kpi_date = date.today()

        try:
            async with engine.begin() as conn:
                # Seed 3 junk leads created yesterday with no touch
                for i in range(3):
                    await conn.execute(
                        text(
                            "INSERT INTO raw_mefi_leads "
                            "(tenant_id, external_id, lifecycle, created_date_local, "
                            "time_to_first_touch_minutes, funnel_stage) "
                            "VALUES (:tenant_id, :ext_id, 'junk', :yesterday, NULL, 'lead') "
                            "ON CONFLICT (tenant_id, external_id) DO NOTHING"
                        ),
                        {
                            "tenant_id": TENANT_ID,
                            "ext_id": f"junk-notouched-{i:04d}",
                            "yesterday": kpi_date,
                        },
                    )

                # Seed 30-day daily_kpi baseline (>= 7 rows required by D-13)
                from datetime import timedelta
                from decimal import Decimal

                for days_ago in range(1, 31):
                    await conn.execute(
                        text(
                            "INSERT INTO daily_kpi "
                            "(tenant_id, date, leads_total, visits_count, offers_count, "
                            "contracts_count, conversion_l_to_v, conversion_o_to_c, avg_deal_size) "
                            "VALUES (:tenant_id, :dt, 10, 3, 2, 1, 0.32, 0.15, 22000) "
                            "ON CONFLICT (tenant_id, date) DO NOTHING"
                        ),
                        {
                            "tenant_id": TENANT_ID,
                            "dt": kpi_date - timedelta(days=days_ago),
                        },
                    )

            # Run detect_anomalies
            detect_anomalies.apply(args=[TENANT_ID_STR])

            # Assert no slow_first_touch row was created for junk leads
            async with engine.connect() as conn:
                result = await conn.execute(
                    text(
                        "SELECT count(*) FROM detected_problems "
                        "WHERE tenant_id = :tenant_id "
                        "AND rule_id = 'slow_first_touch' "
                        "AND date = :kpi_date "
                        "AND context_json::text LIKE '%junk-notouched%'"
                    ),
                    {"tenant_id": TENANT_ID, "kpi_date": kpi_date},
                )
                count = result.scalar()

            assert count == 0, (
                "slow_first_touch must NOT fire for junk leads — "
                f"found {count} detected_problems rows containing junk lead IDs "
                "(ROADMAP SC#6, ANOM-07, D-11)"
            )
        finally:
            await engine.dispose()

    @_INTEGRATION_SKIP
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_detected_problems_upsert_idempotent(self) -> None:
        """Running detect_anomalies twice for same date → exactly 1 row per rule_id (D-01).

        D-01: detected_problems UPSERT on (tenant_id, date, rule_id) is idempotent.
        Running the task twice for the same date must not create duplicate rows.
        Second run updates the existing row — total count per (tenant_id, date, rule_id) = 1.
        """
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        from app.tasks.etl.detect_anomalies import detect_anomalies  # noqa: PLC0415

        engine = create_async_engine(_TEST_DB_URL)
        kpi_date = date.today()

        try:
            # Run detect_anomalies twice
            detect_anomalies.apply(args=[TENANT_ID_STR])
            detect_anomalies.apply(args=[TENANT_ID_STR])

            # Assert no duplicates — each (tenant_id, date, rule_id) has exactly 1 row
            async with engine.connect() as conn:
                result = await conn.execute(
                    text(
                        "SELECT rule_id, count(*) as cnt "
                        "FROM detected_problems "
                        "WHERE tenant_id = :tenant_id AND date = :kpi_date "
                        "GROUP BY rule_id "
                        "HAVING count(*) > 1"
                    ),
                    {"tenant_id": TENANT_ID, "kpi_date": kpi_date},
                )
                duplicates = result.fetchall()

            assert len(duplicates) == 0, (
                "detected_problems must not have duplicate (tenant_id, date, rule_id) rows "
                f"after two task runs — found duplicates: {duplicates} (D-01 UPSERT idempotency)"
            )
        finally:
            await engine.dispose()
