"""Backfill daily KPI computation for a date range — tasks.etl.backfill_daily_kpis.

Computes and UPSERTs daily_kpi, salesperson_daily_kpi, and source_daily_kpi for
every calendar date in [date_from, date_to] inclusive.

One SyncRun(source="metrics_backfill") is written for the entire range.
Per-date progress is committed by the repository methods — if the task is killed
mid-run, already-processed dates remain committed and a re-run picks them up
idempotently (UPSERT conflict keys: (tenant_id, date) for each table).

Routes to the "backfill" queue so it does not starve the default daily queue.

Security:
  UUID(tenant_id)          — rejects malformed strings at task entry (T-03-04-01 pattern)
  date.fromisoformat()     — parses dates as Python date; raw strings never reach SQL
  set_tenant_id(tenant_id) — scopes the tenancy context for all downstream queries
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import structlog
from celery import Task

from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(
    bind=True,
    max_retries=0,
    name="tasks.etl.backfill_daily_kpis",
)
def backfill_daily_kpis(
    self: Task,
    tenant_id: str,
    date_from: str,
    date_to: str,
) -> dict:
    """Compute daily KPIs for every date in [date_from, date_to] inclusive.

    No autoretry — this is a long-running task; per-date commits mean partial
    progress survives a restart and a manual re-run is safe (all upserts are
    idempotent on (tenant_id, date)).

    Args:
        tenant_id: UUID string for the tenant.
        date_from: ISO date string YYYY-MM-DD (inclusive start).
        date_to:   ISO date string YYYY-MM-DD (inclusive end).

    Returns:
        Dict with status, date_from, date_to, dates_processed, records_written,
        duration_ms.
    """
    return asyncio.run(_backfill_async(UUID(tenant_id), date_from, date_to))


async def _backfill_async(tenant_id: UUID, date_from_str: str, date_to_str: str) -> dict:
    """Core backfill coroutine — all DB/model imports deferred (INFRA-05, Pitfall 2)."""
    from sqlalchemy import update as _update
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.core.config import settings
    from app.core.tenancy import set_tenant_id
    from app.models.pipeline import SyncRun
    from app.services.metrics.daily_kpi_service import DailyKpiService
    from app.services.metrics.salesperson_kpi_service import SalespersonKpiService
    from app.services.metrics.source_kpi_service import SourceKpiService
    from app.services.repositories.metrics_repository import MetricsRepository

    set_tenant_id(tenant_id)
    start_at = datetime.now(UTC)
    log = logger.bind(tenant_id=str(tenant_id), task="backfill_daily_kpis")

    date_from = date.fromisoformat(date_from_str)
    date_to = date.fromisoformat(date_to_str)

    if date_from > date_to:
        raise ValueError(f"date_from ({date_from}) must be <= date_to ({date_to})")

    total_days = (date_to - date_from).days + 1
    task_engine = create_async_engine(settings.database_url, poolclass=NullPool)
    TaskSession = async_sessionmaker(task_engine, expire_on_commit=False, class_=AsyncSession)

    total_records = 0
    dates_processed = 0

    try:
        async with TaskSession() as session:
            # WR-06 pattern: mark any stale running backfill as failed before starting
            await session.execute(
                _update(SyncRun)
                .where(
                    SyncRun.tenant_id == tenant_id,
                    SyncRun.source == "metrics_backfill",
                    SyncRun.status == "running",
                )
                .values(status="failed", completed_at=datetime.now(UTC))
            )
            await session.flush()

            sync_run = SyncRun(
                tenant_id=tenant_id,
                source="metrics_backfill",
                status="running",
                started_at=start_at,
            )
            session.add(sync_run)
            await session.commit()
            await session.refresh(sync_run)

            log.info(
                "kpi_backfill.start",
                date_from=date_from_str,
                date_to=date_to_str,
                total_days=total_days,
            )

            daily_svc = DailyKpiService(session, tenant_id)
            sp_svc = SalespersonKpiService(session, tenant_id)
            src_svc = SourceKpiService(session, tenant_id)
            repo = MetricsRepository(session, tenant_id)

            current = date_from
            while current <= date_to:
                daily_row = await daily_svc.compute_for_date(current)
                sp_rows = await sp_svc.compute_for_date(current)
                src_rows = await src_svc.compute_for_date(current)

                await repo.upsert_daily_kpi(daily_row)
                await repo.upsert_salesperson_kpis(sp_rows)
                await repo.upsert_source_kpis(src_rows)

                day_records = 1 + len(sp_rows) + len(src_rows)
                total_records += day_records
                dates_processed += 1

                log.info(
                    "kpi_backfill.date_done",
                    kpi_date=str(current),
                    records=day_records,
                    dates_done=dates_processed,
                    dates_total=total_days,
                )
                current += timedelta(days=1)

            elapsed_ms = int((datetime.now(UTC) - start_at).total_seconds() * 1000)
            sync_run.status = "success"
            sync_run.records_synced = total_records
            sync_run.duration_ms = elapsed_ms
            sync_run.completed_at = datetime.now(UTC)
            await session.commit()

            log.info(
                "kpi_backfill.complete",
                date_from=date_from_str,
                date_to=date_to_str,
                dates_processed=dates_processed,
                records_written=total_records,
                duration_ms=elapsed_ms,
            )

            return {
                "status": "success",
                "date_from": date_from_str,
                "date_to": date_to_str,
                "dates_processed": dates_processed,
                "records_written": total_records,
                "duration_ms": elapsed_ms,
            }

    except Exception as exc:
        try:
            from sqlalchemy import select as _select

            set_tenant_id(tenant_id)
            async with TaskSession() as err_session:
                result = await err_session.execute(
                    _select(SyncRun)
                    .where(
                        SyncRun.tenant_id == tenant_id,
                        SyncRun.source == "metrics_backfill",
                        SyncRun.status == "running",
                    )
                    .order_by(SyncRun.started_at.desc())
                    .limit(1)
                )
                run = result.scalar_one_or_none()
                if run:
                    run.status = "failed"
                    run.error_msg = str(exc)[:500]
                    run.completed_at = datetime.now(UTC)
                    await err_session.commit()
        except Exception as err_exc:  # noqa: BLE001
            log.warning("kpi_backfill.error_handler_failed", error=str(err_exc))
        raise
    finally:
        await task_engine.dispose()
