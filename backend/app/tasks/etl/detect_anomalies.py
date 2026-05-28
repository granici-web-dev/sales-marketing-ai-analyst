from __future__ import annotations

"""Anomaly detection Celery task — third link in the PIPE-01 chain (D-15).

Wires AnomalyService.run_all_rules() and AnomalyRepository.upsert_detected_problem()
into a single idempotent Celery task that:

  1. Resolves the target date (default = yesterday in Europe/Bucharest)
  2. Creates a NullPool engine per invocation (Pitfall 2 / INFRA-05)
  3. Writes SyncRun(source="anomaly") for audit (PIPE-04)
  4. Runs all 5 anomaly detection rules via AnomalyService.run_all_rules()
  5. Upserts all results via AnomalyRepository.upsert_detected_problem()
     (single commit after all upserts — WR-04)
  6. Updates SyncRun to "success" or "failed"

Chain position: sync_mefi_leads → calculate_daily_kpis → detect_anomalies → (Phase 5: generate_daily_insights)

NullPool + deferred imports pattern (INFRA-05 / Pitfall 2) — copy from calculate_daily_kpis.py

Security:
  T-04-04-01: UUID(tenant_id) at task entry — malformed strings raise ValueError
  T-04-04-02: task_serializer="json", accept_content=["json"] — pickle disabled (set in celery_app.py)
  T-04-04-03: Every detect_anomalies run writes SyncRun(source="anomaly") with audit trail
  T-04-04-04: str(exc)[:500] captures errors without leaking PII — exception messages contain only counts/dates
  T-04-04-05: NullPool + finally:dispose() — no connection leaks on retry
  T-04-04-06: detect_anomalies.si() is immutable — cannot inject args or modify preceding task results

Phase 4 Plan 04 — final wave of the Anomaly Detection phase.
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
    name="tasks.etl.detect_anomalies",
)
def detect_anomalies(self, tenant_id: str) -> dict:
    """Run anomaly detection rules for the given tenant.

    Third link in the PIPE-01 daily pipeline chain (D-15).
    Runs after calculate_daily_kpis completes successfully.

    Args:
        tenant_id: UUID string for the tenant (T-04-04-01 — validated as UUID at entry).

    Returns:
        Dict with status, kpi_date, problems_found, duration_ms.
    """
    # CR-05 pattern: no manual try/except self.retry() — autoretry_for handles it.
    # Manual retry was removed from calculate_daily_kpis.py for the same reason (WR-05).
    return asyncio.run(_detect_async(UUID(tenant_id)))


async def _detect_async(tenant_id: UUID) -> dict:
    """Core detection coroutine — all DB/model imports deferred (INFRA-05, Pitfall 2).

    NullPool prevents cross-loop Future references when asyncio.run() creates
    a fresh event loop on each Celery task call (Pitfall 2 documented in RESEARCH.md).
    All app.models.*, app.db.session, app.services.* imports live inside this
    function body to prevent module-level DB pool creation before Celery's
    prefork pool forks worker processes (INFRA-05).

    Args:
        tenant_id: Validated UUID from the sync entry point.

    Returns:
        Dict with status, kpi_date, problems_found, duration_ms.
    """
    # ---------------------------------------------------------------------------
    # Deferred imports — must stay inside this function body (INFRA-05, Pitfall 2)
    # ---------------------------------------------------------------------------
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.core.config import settings
    from app.core.tenancy import set_tenant_id
    from app.models.pipeline import SyncRun
    from app.services.anomaly.anomaly_service import AnomalyService
    from app.services.repositories.anomaly_repository import AnomalyRepository
    from zoneinfo import ZoneInfo
    from datetime import date as date_type, timedelta

    # ── Security: set tenant context ────────────────────────────────────────────
    set_tenant_id(tenant_id)
    detect_start_at = datetime.now(UTC)
    log = logger.bind(tenant_id=str(tenant_id), task="detect_anomalies")

    # ── NullPool engine per invocation (Pitfall 2 / T-04-04-04 / T-04-04-05) ───
    task_engine = create_async_engine(settings.database_url, poolclass=NullPool)
    TaskSession = async_sessionmaker(task_engine, expire_on_commit=False, class_=AsyncSession)

    # ── Resolve kpi_date (detect anomalies for yesterday — mirrors D-10 default) ─
    BUCHAREST = ZoneInfo("Europe/Bucharest")
    kpi_date = datetime.now(BUCHAREST).date() - timedelta(days=1)
    log.info("anomaly.detect_start", kpi_date=str(kpi_date))

    try:
        async with TaskSession() as session:
            # ── Step 1: Write SyncRun at start (PIPE-04 / T-04-04-03) ──────────
            # WR-06: Mark any stale running SyncRun as failed before creating a new one.
            # Without this, each retry creates a new SyncRun(status="running") row;
            # the error handler only updates the latest one (LIMIT 1 ORDER BY started_at DESC),
            # leaving older ones permanently stuck at status="running" in audit queries.
            from sqlalchemy import update as _update  # deferred — fork-safe

            await session.execute(
                _update(SyncRun)
                .where(
                    SyncRun.tenant_id == tenant_id,
                    SyncRun.source == "anomaly",
                    SyncRun.status == "running",
                )
                .values(status="failed", completed_at=datetime.now(UTC))
            )
            await session.flush()

            sync_run = SyncRun(
                tenant_id=tenant_id,
                source="anomaly",  # "anomaly" distinguishes from "mefi" / "metrics"
                status="running",
                started_at=detect_start_at,
            )
            session.add(sync_run)
            await session.commit()
            await session.refresh(sync_run)

            # ── Step 2: Instantiate services ─────────────────────────────────
            svc = AnomalyService(session, tenant_id)
            repo = AnomalyRepository(session, tenant_id)

            # ── Step 3: Run all anomaly detection rules ───────────────────────
            problems = await svc.run_all_rules(kpi_date)
            log.info("anomaly.rules_done", kpi_date=str(kpi_date), problems_found=len(problems))

            # ── Step 4: Upsert problem rows — NO commit per row (WR-04) ───────
            # Single commit after all upserts — idempotent (D-01 / Pitfall 5)
            for problem in problems:
                await repo.upsert_detected_problem(problem)
            await session.commit()

            # ── Step 5: Update SyncRun to success ────────────────────────────
            elapsed_ms = int((datetime.now(UTC) - detect_start_at).total_seconds() * 1000)
            sync_run.status = "success"
            sync_run.records_synced = len(problems)
            sync_run.duration_ms = elapsed_ms
            sync_run.completed_at = datetime.now(UTC)
            await session.commit()

            log.info(
                "anomaly.complete",
                kpi_date=str(kpi_date),
                problems_written=len(problems),
                duration_ms=elapsed_ms,
            )

            return {
                "status": "success",
                "kpi_date": kpi_date.isoformat(),
                "problems_found": len(problems),
                "duration_ms": elapsed_ms,
            }

    except Exception as exc:
        # ── Error path: update SyncRun to failed (T-04-04-03 / PIPE-04) ────────
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
                        _SR.source == "anomaly",
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
            log.warning("anomaly.error_handler_failed", error=str(err_exc))
        raise
    finally:
        # ── Always dispose engine (T-04-04-05 — no connection leaks) ──────────
        await task_engine.dispose()
