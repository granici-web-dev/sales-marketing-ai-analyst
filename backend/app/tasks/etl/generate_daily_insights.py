from __future__ import annotations

"""AI Insights generation Celery task — fourth and final link in the PIPE-01 chain (D-17).

Wires InsightService.run() and InsightRepository.upsert_daily_insight() into a single
idempotent Celery task that:

  1. Resolves the target date (default = yesterday in Europe/Bucharest)
  2. Creates a NullPool engine per invocation (INFRA-05)
  3. Writes SyncRun(source='insights') for audit (PIPE-04)
  4. Writes DailyInsight(status='running') at start
  5. Calls InsightService.run() to generate DailyInsightResponse via Claude Sonnet 4.5
  6. Upserts result to daily_insights via InsightRepository
  7. Updates DailyInsight status to 'success'/'fallback'/'failed' and SyncRun to
     'success'/'failed'.

Chain position: sync_mefi_leads → calculate_daily_kpis → detect_anomalies → generate_daily_insights

Security:
  T-05-04-01: UUID(tenant_id) at task entry — malformed strings raise ValueError
  T-05-04-02: task_serializer='json', accept_content=['json'] — pickle disabled (celery_app.py)
  T-05-04-03: SyncRun(source='insights') audit trail (PIPE-04)
  T-05-04-04: str(exc)[:500] in error handler — no PII in error logs
  T-05-04-05: NullPool + finally:dispose() — no connection leaks
  T-05-04-06: generate_daily_insights.si() is immutable — no arg injection
"""

import asyncio
from datetime import UTC, datetime
from uuid import UUID

import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=60,
    name="tasks.etl.generate_daily_insights",
    soft_time_limit=120,
    time_limit=180,
)
def generate_daily_insights(self, tenant_id: str) -> dict:
    """Generate AI insights for the given tenant.

    Fourth and final link in the PIPE-01 daily pipeline chain (D-17).
    Runs after detect_anomalies completes successfully.

    Args:
        tenant_id: UUID string for the tenant (T-05-04-01 — validated as UUID at entry).

    Returns:
        Dict with status, kpi_date, duration_ms.
    """
    # CR-05 pattern: no manual try/except self.retry() — autoretry_for handles it.
    return asyncio.run(_generate_async(UUID(tenant_id)))


async def _generate_async(
    tenant_id: str | UUID,
    kpi_date: object = None,
) -> dict:
    """Core generation coroutine — all DB/model imports deferred (INFRA-05, Pitfall 2).

    NullPool prevents cross-loop Future references when asyncio.run() creates
    a fresh event loop on each Celery task call (Pitfall 2 documented in RESEARCH.md).
    All app.models.*, app.db.session, app.services.* imports live inside this
    function body to prevent module-level DB pool creation before Celery's
    prefork pool forks worker processes (INFRA-05).

    Args:
        tenant_id: UUID or UUID string from the sync entry point.
        kpi_date: Optional target date (default = yesterday in Europe/Bucharest).

    Returns:
        Dict with status, kpi_date, duration_ms.
    """
    # ---------------------------------------------------------------------------
    # Deferred imports — must stay inside this function body (INFRA-05, Pitfall 2)
    # ---------------------------------------------------------------------------
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.core.config import settings
    from app.core.tenancy import set_tenant_id
    from app.models.insights.daily_insight import DailyInsight
    from app.models.pipeline import SyncRun
    from app.services.insights.insight_service import InsightService
    from app.services.repositories.insight_repository import InsightRepository
    from zoneinfo import ZoneInfo
    from datetime import date as date_type, timedelta
    from sqlalchemy import select as _select, update as _update

    # Convert string tenant_id to UUID (supports both Celery task and direct test calls)
    if isinstance(tenant_id, str):
        tenant_id = UUID(tenant_id)

    # WR-04: minimum staleness threshold — only clean rows older than 30 minutes
    _STALE_SYNCRUN_THRESHOLD_MINUTES = 30

    # ── Security: set tenant context ────────────────────────────────────────────
    set_tenant_id(tenant_id)
    task_start_at = datetime.now(UTC)
    log = logger.bind(tenant_id=str(tenant_id), task="generate_daily_insights")

    # ── NullPool engine per invocation (Pitfall 2 / T-05-04-05) ─────────────────
    task_engine = create_async_engine(settings.database_url, poolclass=NullPool)
    TaskSession = async_sessionmaker(task_engine, expire_on_commit=False, class_=AsyncSession)

    # ── Resolve kpi_date (generate insights for yesterday — D-10 default) ────────
    BUCHAREST = ZoneInfo("Europe/Bucharest")
    if kpi_date is None:
        kpi_date = datetime.now(BUCHAREST).date() - timedelta(days=1)
    log.info("insight.generate_start", kpi_date=str(kpi_date))

    try:
        async with TaskSession() as session:
            # ── WR-06: Mark stale SyncRuns as failed ─────────────────────────────
            # Without this, each retry creates a new SyncRun(status="running") row;
            # the error handler only updates the latest one (LIMIT 1 ORDER BY started_at DESC),
            # leaving older ones permanently stuck at status="running" in audit queries.
            await session.execute(
                _update(SyncRun)
                .where(
                    SyncRun.tenant_id == tenant_id,
                    SyncRun.source == "insights",
                    SyncRun.status == "running",
                    SyncRun.started_at
                    < datetime.now(UTC) - timedelta(minutes=_STALE_SYNCRUN_THRESHOLD_MINUTES),
                )
                .values(status="failed", completed_at=datetime.now(UTC))
            )
            await session.flush()

            # ── Step 1: Write SyncRun at start (PIPE-04 / T-05-04-03) ───────────
            sync_run = SyncRun(
                tenant_id=tenant_id,
                source="insights",  # "insights" distinguishes from "mefi"/"metrics"/"anomaly"
                status="running",
                started_at=task_start_at,
            )
            session.add(sync_run)
            await session.commit()
            await session.refresh(sync_run)

            # ── Step 2: Write DailyInsight(status='running') — D-16 state machine ─
            # UPSERT: if insight exists for this date (manual re-run), update status to 'running'
            from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: PLC0415

            running_row = {
                "tenant_id": tenant_id,
                "date": kpi_date,
                "status": "running",
            }
            stmt = pg_insert(DailyInsight).values([running_row])
            stmt = stmt.on_conflict_do_update(
                index_elements=["tenant_id", "date"],
                set_={
                    "status": stmt.excluded.status,
                    "updated_at": datetime.now(UTC),
                },
            )
            await session.execute(stmt)
            await session.commit()

            # ── Step 3: Run InsightService (Claude API call + validation + fallback) ─
            svc = InsightService(session, tenant_id)
            result_dict, status = await svc.run(kpi_date)

            # ── Step 4: Upsert final daily_insights row via InsightRepository ────
            repo = InsightRepository(session, tenant_id)
            final_row = {
                "tenant_id": tenant_id,
                "date": kpi_date,
                "status": status,
                "payload_json": result_dict["payload"],
                "generated_at": datetime.now(UTC),
                "input_tokens": result_dict["input_tokens"],
                "output_tokens": result_dict["output_tokens"],
                "cost_usd": result_dict["cost_usd"],
                "raw_response": result_dict.get("raw_response", ""),
            }
            await repo.upsert_daily_insight(final_row)

            # ── Step 5: Update SyncRun — propagate insight status (WR-01 fix) ─────
            # status is "success" | "fallback" — both are non-error terminal states.
            # Previously always "success", which hid fallback events from monitoring.
            elapsed_ms = int((datetime.now(UTC) - task_start_at).total_seconds() * 1000)
            sync_run.status = status  # "success" | "fallback" — both non-error terminals
            sync_run.records_synced = 1
            sync_run.duration_ms = elapsed_ms
            sync_run.completed_at = datetime.now(UTC)
            await session.commit()

            log.info(
                "insight.complete",
                kpi_date=str(kpi_date),
                status=status,
                input_tokens=result_dict["input_tokens"],
                cost_usd=str(result_dict["cost_usd"]),
                duration_ms=elapsed_ms,
            )

            return {
                "status": status,
                "kpi_date": kpi_date.isoformat(),
                "duration_ms": elapsed_ms,
            }

    except Exception as exc:
        # ── Error path: update SyncRun to failed (T-05-04-03 / PIPE-04) ─────────
        # Open a NEW session — the original session may have rolled back
        try:
            from app.core.tenancy import set_tenant_id as _set  # noqa: PLC0415

            _set(tenant_id)
            async with TaskSession() as err_session:
                result = await err_session.execute(
                    _select(SyncRun)
                    .where(
                        SyncRun.tenant_id == tenant_id,
                        SyncRun.source == "insights",
                        SyncRun.status == "running",
                    )
                    .order_by(SyncRun.started_at.desc())
                    .limit(1)
                )
                run = result.scalar_one_or_none()
                if run:
                    run.status = "failed"
                    run.error_msg = str(exc)[:500]  # T-05-04-04: no PII in error logs
                    run.completed_at = datetime.now(UTC)
                    await err_session.commit()
            # Also try to update DailyInsight to 'failed'
            async with TaskSession() as err_session2:
                from app.models.insights.daily_insight import DailyInsight as _DI  # noqa: PLC0415

                result2 = await err_session2.execute(
                    _select(_DI).where(
                        _DI.tenant_id == tenant_id,
                        _DI.date == kpi_date,
                    )
                )
                insight = result2.scalar_one_or_none()
                if insight:
                    insight.status = "failed"
                    await err_session2.commit()
        except Exception as err_exc:  # noqa: BLE001
            log.warning("insight.error_handler_failed", error=str(err_exc))
        raise
    finally:
        # ── Always dispose engine (T-05-04-05 — no connection leaks) ────────────
        await task_engine.dispose()
