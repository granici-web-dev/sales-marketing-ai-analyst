from __future__ import annotations

"""Daily KPI calculation Celery task — second link in the PIPE-01 chain (D-18).

Wires DailyKpiService, SalespersonKpiService, SourceKpiService, and
MetricsRepository into a single idempotent Celery task that:

  1. Resolves the target date (default = yesterday in Europe/Bucharest, D-10)
  2. Creates a NullPool engine per invocation (Pitfall 2 / INFRA-05)
  3. Writes SyncRun(source="metrics") for audit (PIPE-04 / T-03-04-06)
  4. Computes and UPSERTs daily_kpi (1 row), salesperson_daily_kpi (N rows),
     source_daily_kpi (7 rows) — all idempotent (METR-01 SC#1, D-12)
  5. Updates SyncRun to "success" or "failed"

Chain position: sync_mefi_leads → calculate_daily_kpis → (Phase 4: detect_anomalies)

Security:
  T-03-04-01: UUID(tenant_id) at sync entry — malformed strings raise ValueError
  T-03-04-02: date.fromisoformat(calculation_date) parses as Python date before queries
  T-03-04-03: structlog binds tenant_id + kpi_date only — no PII (INFRA-06)
  T-03-04-04: NullPool + finally:dispose() — connections always closed (Pitfall 2)
  T-03-04-05: NullPool prevents cross-loop asyncpg Future reuse (Pitfall 2)
  T-03-04-06: Failed runs write SyncRun(status="failed", error_msg) for audit (PIPE-04)

Phase 3 Plan 04 — final wave of the Metrics Engine phase.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=60,
    name="tasks.etl.calculate_daily_kpis",
)
def calculate_daily_kpis(
    self,
    tenant_id: str,
    calculation_date: str | None = None,
) -> dict:
    """Calculate daily KPIs for the given tenant and optional date.

    Second link in the PIPE-01 daily pipeline chain (D-18).
    Runs after sync_mefi_leads completes successfully.

    Args:
        tenant_id: UUID string for the tenant (T-03-04-01 — validated as UUID at entry).
        calculation_date: ISO date string YYYY-MM-DD or None → yesterday in
            Europe/Bucharest (D-10 / D-12 backfill support).

    Returns:
        Dict with status, kpi_date, records_written, duration_ms.
    """
    # CR-05 FIX: removed manual try/except + self.retry(). The task already declares
    # autoretry_for=(Exception,), so the manual retry was redundant and caused a
    # double-retry hazard: when max_retries was exhausted, self.retry() re-raised
    # the original exception which autoretry_for then caught again, allowing up to
    # 2× the intended retry budget and leaving stale SyncRun("running") rows.
    return asyncio.run(_calc_async(UUID(tenant_id), calculation_date))


async def _calc_async(tenant_id: UUID, calculation_date: str | None) -> dict:
    """Core calculation coroutine — all DB/model imports deferred (INFRA-05, Pitfall 2).

    NullPool prevents cross-loop Future references when asyncio.run() creates
    a fresh event loop on each Celery task call (Pitfall 2 documented in RESEARCH.md).
    All app.models.*, app.db.session, app.services.* imports live inside this
    function body to prevent module-level DB pool creation before Celery's
    prefork pool forks worker processes (INFRA-05).

    Args:
        tenant_id: Validated UUID from the sync entry point.
        calculation_date: ISO date string or None.

    Returns:
        Dict with status, kpi_date, records_written, duration_ms.
    """
    # ---------------------------------------------------------------------------
    # Deferred imports — must stay inside this function body (INFRA-05, Pitfall 2)
    # ---------------------------------------------------------------------------
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.core.config import settings
    from app.core.tenancy import set_tenant_id
    from app.models.pipeline import SyncRun
    from app.services.metrics.daily_kpi_service import DailyKpiService
    from app.services.metrics.salesperson_kpi_service import SalespersonKpiService
    from app.services.metrics.source_kpi_service import SourceKpiService
    from app.services.repositories.metrics_repository import MetricsRepository
    from zoneinfo import ZoneInfo
    from datetime import date as date_type

    # ── Security: set tenant context ────────────────────────────────────────────
    set_tenant_id(tenant_id)
    calc_start_at = datetime.now(UTC)
    log = logger.bind(tenant_id=str(tenant_id), task="calculate_daily_kpis")

    # ── NullPool engine per invocation (Pitfall 2 / T-03-04-04 / T-03-04-05) ───
    task_engine = create_async_engine(settings.database_url, poolclass=NullPool)
    TaskSession = async_sessionmaker(task_engine, expire_on_commit=False, class_=AsyncSession)

    # ── Resolve calculation date (D-10, T-03-04-02) ────────────────────────────
    # date.fromisoformat() parses input as Python date — raw strings NEVER reach SQL
    # (T-03-04-02 SQL injection mitigation). ValueError on malformed date propagates
    # to autoretry exception handler (correct — invalid date should not silently
    # default to yesterday).
    BUCHAREST = ZoneInfo("Europe/Bucharest")
    if calculation_date is not None:
        kpi_date = date_type.fromisoformat(calculation_date)
    else:
        kpi_date = datetime.now(BUCHAREST).date() - timedelta(days=1)

    log.info("kpi.compute_start", kpi_date=str(kpi_date))

    try:
        async with TaskSession() as session:
            # ── Step 1: Write SyncRun at start (PIPE-04 / T-03-04-06) ──────────
            # WR-06 FIX: Mark any stale running SyncRun as failed before creating a new one.
            # Without this, each retry creates a new SyncRun(status="running") row;
            # the error handler only updates the latest one (LIMIT 1 ORDER BY started_at DESC),
            # leaving older ones permanently stuck at status="running" in audit queries.
            from sqlalchemy import update as _update  # deferred — fork-safe

            await session.execute(
                _update(SyncRun)
                .where(
                    SyncRun.tenant_id == tenant_id,
                    SyncRun.source == "metrics",
                    SyncRun.status == "running",
                )
                .values(status="failed", completed_at=datetime.now(UTC))
            )
            await session.flush()

            sync_run = SyncRun(
                tenant_id=tenant_id,
                source="metrics",  # "metrics" distinguishes from "mefi" / "backfill"
                status="running",
                started_at=calc_start_at,
            )
            session.add(sync_run)
            await session.commit()
            await session.refresh(sync_run)

            # ── Step 2: Instantiate services + repository ────────────────────
            daily_svc = DailyKpiService(session, tenant_id)
            sp_svc = SalespersonKpiService(session, tenant_id)
            src_svc = SourceKpiService(session, tenant_id)
            repo = MetricsRepository(session, tenant_id)

            # ── Step 3: Compute metrics sequentially (shared read locks) ──────
            # Sequential — not concurrent — services may share DB read locks
            daily_row = await daily_svc.compute_for_date(kpi_date)
            log.info("kpi.daily_done", kpi_date=str(kpi_date))

            sp_rows = await sp_svc.compute_for_date(kpi_date)
            log.info("kpi.salespeople_done", kpi_date=str(kpi_date), records=len(sp_rows))

            src_rows = await src_svc.compute_for_date(kpi_date)
            log.info("kpi.sources_done", kpi_date=str(kpi_date), records=len(src_rows))

            # ── Step 4: UPSERT metric rows (idempotent — METR-01 SC#1) ────────
            await repo.upsert_daily_kpi(daily_row)
            await repo.upsert_salesperson_kpis(sp_rows)
            await repo.upsert_source_kpis(src_rows)

            total_records = 1 + len(sp_rows) + len(src_rows)

            # ── Step 5: Update SyncRun to success ────────────────────────────
            elapsed_ms = int((datetime.now(UTC) - calc_start_at).total_seconds() * 1000)
            sync_run.status = "success"
            sync_run.records_synced = total_records
            sync_run.duration_ms = elapsed_ms
            sync_run.completed_at = datetime.now(UTC)
            await session.commit()

            log.info(
                "kpi.complete",
                kpi_date=str(kpi_date),
                records_written=total_records,
                duration_ms=elapsed_ms,
            )

            return {
                "status": "success",
                "kpi_date": kpi_date.isoformat(),
                "records_written": total_records,
                "duration_ms": elapsed_ms,
            }

    except Exception as exc:
        # ── Error path: update SyncRun to failed (T-03-04-06 / PIPE-04) ────────
        # Open a NEW session — the original session may have rolled back
        try:
            from sqlalchemy import select as _select  # noqa: PLC0415
            from app.models.pipeline import SyncRun as _SR  # noqa: PLC0415
            from app.core.tenancy import set_tenant_id as _set  # noqa: PLC0415

            _set(tenant_id)
            async with TaskSession() as err_session:
                result = await err_session.execute(
                    _select(_SR).where(
                        _SR.tenant_id == tenant_id,
                        _SR.source == "metrics",
                        _SR.status == "running",
                    ).order_by(_SR.started_at.desc()).limit(1)
                )
                run = result.scalar_one_or_none()
                if run:
                    run.status = "failed"
                    run.error_msg = str(exc)[:500]
                    run.completed_at = datetime.now(UTC)
                    await err_session.commit()
        except Exception as err_exc:  # noqa: BLE001
            log.warning("kpi.error_handler_failed", error=str(err_exc))
        raise
    finally:
        # ── Always dispose engine (T-03-04-04 — no connection leaks) ──────────
        await task_engine.dispose()
