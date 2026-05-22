from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import httpx
import redis.asyncio as aioredis
import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)

_LOCK_TTL = 36000  # 10 hours — covers worst-case full backfill runtime


def get_cf(fields: object, field_id: int) -> object:
    """Extract a custom field value by form-cf-ID from MEFI custom_fields.

    None-safe: returns None if fields is None, empty, or the field is absent.
    Handles both Pydantic MefiCustomField objects (from API response) and
    plain dicts (from stored custom_fields_raw JSON).
    """
    if not fields:
        return None
    for f in fields:  # type: ignore[union-attr]
        if hasattr(f, "field_id"):
            # Pydantic MefiCustomField object — use attribute access
            if f.field_id == field_id:
                return f.value
        else:
            # Plain dict (from custom_fields_raw or test data)
            if f.get("field_id") == field_id or f.get("id") == field_id:
                return f.get("value")
    return None


@celery_app.task(
    bind=True,
    autoretry_for=(httpx.TimeoutException, httpx.NetworkError),
    max_retries=3,
    default_retry_delay=60,
    name="tasks.etl.sync_mefi_leads",
)
def sync_mefi_leads(self, tenant_id: str) -> dict:  # type: ignore[no-untyped-def]
    """Nightly MEFI CRM lead sync task.

    Fetches all leads modified since the last successful sync, writes them to
    raw_mefi_leads via bulk UPSERT, records status-change history, and triggers
    a backfill if this is the first sync for the tenant.

    Args:
        tenant_id: UUID string for the tenant to sync (PIPE-02: UUID validation
            at entry point prevents spoofing via malformed input — T-02-11).

    Returns:
        Dict with status, records_synced, and duration_ms.
    """
    try:
        return asyncio.run(_sync_async(UUID(tenant_id)))
    except Exception as exc:
        from app.services.integrations.mefi import RateLimitError  # noqa

        if isinstance(exc, RateLimitError):
            raise self.retry(countdown=exc.retry_after) from exc
        raise


async def _sync_async(tenant_id: UUID) -> dict:
    """Core sync coroutine — all I/O imports are deferred to this body (Pitfall 8).

    All app.db.session and app.models imports are inside this function to
    prevent module-level DB connection pool creation before Celery's prefork
    pool forks worker processes (INFRA-05 / fork-safety).
    """
    # Deferred imports — must stay inside this function body (Pitfall 8 / INFRA-05)
    from app.core.config import settings
    from app.core.tenancy import set_tenant_id
    from app.db.session import AsyncSessionLocal
    from app.models.pipeline import SyncRun
    from app.services.integrations.mefi import MefiClient
    from app.services.repositories.mefi_repository import MefiRepository

    set_tenant_id(tenant_id)
    sync_start_at = datetime.now(UTC)

    log = logger.bind(tenant_id=str(tenant_id), task="sync_mefi_leads")

    # ── Step 1: Acquire Redis lock (T-02-09) ─────────────────────────────────
    lock_key = f"sync:mefi:{tenant_id}"
    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        acquired = await redis.set(lock_key, "1", nx=True, ex=_LOCK_TTL)
    except Exception:
        await redis.aclose()
        raise

    if not acquired:
        log.info("sync.lock_held", lock_key=lock_key)
        await redis.aclose()
        return {"status": "noop", "reason": "lock_held"}

    try:
        async with AsyncSessionLocal() as session:
            repo = MefiRepository(session, tenant_id)

            # ── Step 2: Write SyncRun at start ───────────────────────────────
            sync_run = SyncRun(
                tenant_id=tenant_id,
                source="mefi",
                status="running",
                started_at=sync_start_at,
            )
            session.add(sync_run)
            await session.commit()
            await session.refresh(sync_run)

            async with MefiClient(api_key=settings.mefi_api_key) as client:
                # ── Step 3: Liveness probe ───────────────────────────────────
                alive = await client.health_check()
                if not alive:
                    log.warning("mefi.liveness_failed")
                    sync_run.status = "failed"
                    sync_run.error_msg = "MEFI liveness check returned total=0"
                    sync_run.completed_at = datetime.now(UTC)
                    await session.commit()
                    return {"status": "failed", "reason": "liveness_failed"}

                # ── Step 4: First-ever sync? Trigger backfill ────────────────
                lead_count = await repo.get_lead_count_for_tenant()
                if lead_count == 0:
                    from app.tasks.etl.backfill_mefi_leads import backfill_mefi_leads  # noqa

                    backfill_mefi_leads.apply_async(
                        args=[str(tenant_id)], queue="backfill"
                    )
                    log.info("sync.backfill_enqueued", tenant_id=str(tenant_id))

                # ── Step 5: Compute date window ──────────────────────────────
                last_sync_at = await repo.get_last_sync_at()
                if last_sync_at:
                    date_from = (last_sync_at.date() - timedelta(days=1)).isoformat()
                else:
                    date_from = date(2025, 1, 1).isoformat()

                date_to = sync_start_at.date().isoformat()

                # ── Step 6: Paginate MEFI API ────────────────────────────────
                page = 1
                per_page = 100
                total_synced = 0

                while True:
                    response = await client.search_leads(
                        filters={
                            "lifecycle": ["active", "lost", "junk"],
                            "date_from": date_from,
                            "date_to": date_to,
                            "date_field": "status_changed_at",
                        },
                        page=page,
                        per_page=per_page,
                        sort="status_changed_at",
                        order="asc",
                    )

                    if not response.data:
                        break

                    # ── Step 7: Transform batch ──────────────────────────────
                    rows = []
                    salesperson_pairs: list[tuple[int, str]] = []
                    now = datetime.now(UTC)

                    for lead in response.data:
                        cf = lead.custom_fields if lead.custom_fields else []
                        offer_raw = get_cf(cf, 20)
                        offer_flag: bool | None = None
                        if offer_raw == "✅DA":
                            offer_flag = True
                        elif offer_raw == "❌NU":
                            offer_flag = False

                        row: dict = {
                            "tenant_id": tenant_id,
                            "external_id": str(lead.id),
                            "status_id": lead.status.id if lead.status else None,
                            "status_name": lead.status.name if lead.status else None,
                            "source_id": lead.source.id if lead.source else None,
                            "source_name": lead.source.name if lead.source else None,
                            "lifecycle": lead.lifecycle or "active",
                            "assigned_to_id": lead.assigned_to.id if lead.assigned_to else None,
                            "assigned_to_name": lead.assigned_to.name if lead.assigned_to else None,
                            "estimated_value": lead.estimated_value,
                            "priority": lead.priority.get("name") if isinstance(lead.priority, dict) else lead.priority,
                            "is_duplicate": lead.is_duplicate or False,
                            "created_at_source": lead.created_at,
                            "last_contact_at": lead.last_contact_at,
                            "status_changed_at": lead.status_changed_at,
                            "showroom": get_cf(cf, 14),
                            "offer_sent_flag": offer_flag,
                            "utm_source": get_cf(cf, 38),
                            "utm_campaign": get_cf(cf, 39),
                            "utm_content": get_cf(cf, 40),
                            "utm_medium": get_cf(cf, 41),
                            "custom_fields_raw": [f.model_dump() for f in cf] if cf else None,
                            "raw_payload": lead.model_dump(),
                            "synced_at": now,
                        }
                        rows.append(row)

                        if lead.assigned_to and lead.assigned_to.id:
                            salesperson_pairs.append(
                                (lead.assigned_to.id, lead.assigned_to.name or "")
                            )

                    # ── Step 8: Detect history, upsert, record ───────────────
                    history_rows = await repo.detect_and_record_history(rows)
                    await repo.bulk_upsert_leads(rows)
                    await repo.insert_history_rows(history_rows)
                    await repo.upsert_salespeople(salesperson_pairs)

                    total_synced += len(rows)
                    log.info(
                        "sync.page_done",
                        page=page,
                        batch_size=len(rows),
                        total_synced=total_synced,
                    )

                    if len(response.data) < per_page:
                        break
                    page += 1

            # ── Step 9: PIPE-03 — warn if no data today ──────────────────────
            if total_synced == 0 and date_from == date_to:
                log.warning("sync.no_data_today", date=date_to)
                raise RuntimeError("No data for today — halting pipeline chain")

            # ── Step 10: Update SyncRun to success ───────────────────────────
            elapsed_ms = int((datetime.now(UTC) - sync_start_at).total_seconds() * 1000)
            sync_run.status = "success"
            sync_run.records_synced = total_synced
            sync_run.duration_ms = elapsed_ms
            sync_run.completed_at = datetime.now(UTC)
            await session.commit()

            log.info(
                "sync.complete",
                records_synced=total_synced,
                duration_ms=elapsed_ms,
            )

            return {
                "status": "success",
                "records_synced": total_synced,
                "duration_ms": elapsed_ms,
            }

    except Exception as exc:
        # ── Error path: update SyncRun to failed, release lock ───────────────
        try:
            async with AsyncSessionLocal() as err_session:
                from app.core.tenancy import set_tenant_id as _set  # noqa
                _set(tenant_id)
                from sqlalchemy import select as _select  # noqa
                from app.models.pipeline import SyncRun as _SR  # noqa
                result = await err_session.execute(
                    _select(_SR).where(
                        _SR.tenant_id == tenant_id,
                        _SR.source == "mefi",
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
            log.warning("sync.error_handler_failed", error=str(err_exc))
        raise
    finally:
        await redis.delete(lock_key)
        await redis.aclose()


def daily_pipeline(tenant_id: str) -> object:
    """Build the daily analytics pipeline chain for a tenant.

    Phase 2: chain only contains sync_mefi_leads.
    Phase 3 will extend this chain with calculate_metrics.si() etc.

    Defined here so Phase 3 modifies this function without touching celery_app.py.
    """
    from celery import chain

    return chain(sync_mefi_leads.si(tenant_id))
