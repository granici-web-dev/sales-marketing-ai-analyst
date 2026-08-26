from __future__ import annotations

from datetime import UTC, datetime

import structlog
from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.core.redis import redis_client
from app.core.tenancy import require_tenant_id
from app.schemas.auth import UserOut

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/sync", tags=["sync"])

# Protect MEFI's burst rate limit — one on-demand sync per tenant per minute.
RATE_LIMIT_TTL = 60


class SyncTriggerResponse(BaseModel):
    task_id: str
    enqueued_at: str


class SyncStatusResponse(BaseModel):
    task_id: str
    state: str  # PENDING | STARTED | RETRY | SUCCESS | FAILURE
    done: bool
    error: str | None = None


@router.post("/trigger", status_code=202, response_model=SyncTriggerResponse)
async def trigger_sync(
    current_user: UserOut = Depends(get_current_user),
) -> SyncTriggerResponse:
    """On-demand sync — pull fresh MEFI leads and recompute today's KPIs.

    Chain: sync_mefi_leads → calculate_daily_kpis. Anomaly detection and AI
    insights are intentionally NOT in this chain — they're expensive and
    user-controlled separately (Insights page "Generează insight" button).
    """
    tenant_id_str = str(require_tenant_id())
    rate_key = f"rate_limit:sync_trigger:{tenant_id_str}"

    async with redis_client() as r:
        was_set = await r.set(rate_key, "1", nx=True, ex=RATE_LIMIT_TTL)
        if not was_set:
            ttl = await r.ttl(rate_key)
            retry_after = max(ttl, 0)
            raise HTTPException(
                status_code=429,
                detail=f"Sync already triggered. Try again in {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)},
            )

    from celery import chain

    from app.tasks.etl.calculate_daily_kpis import calculate_daily_kpis
    from app.tasks.etl.sync_mefi_leads import sync_mefi_leads

    pipeline = chain(
        sync_mefi_leads.si(tenant_id_str),
        calculate_daily_kpis.si(tenant_id_str),
    )
    task = pipeline.apply_async()

    logger.info(
        "sync.trigger_enqueued",
        user_id=str(current_user.id),
        task_id=str(task.id),
    )
    return SyncTriggerResponse(
        task_id=str(task.id),
        enqueued_at=datetime.now(UTC).isoformat(),
    )


@router.get("/status", response_model=SyncStatusResponse)
async def sync_status(
    task_id: str = Query(...),
    current_user: UserOut = Depends(get_current_user),
) -> SyncStatusResponse:
    """Poll the Celery task state for the chain returned by /sync/trigger."""
    from app.tasks.celery_app import celery_app

    result = AsyncResult(task_id, app=celery_app)
    state = result.state
    done = state in {"SUCCESS", "FAILURE", "REVOKED"}
    error: str | None = None
    if state == "FAILURE":
        # str(result.result) is the exception's repr — safe to surface (no PII).
        error = str(result.result)[:300]

    return SyncStatusResponse(task_id=task_id, state=state, done=done, error=error)
