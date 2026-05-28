from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.db.deps import get_session
from app.schemas.auth import UserOut

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/insights", tags=["insights"])

RATE_LIMIT_TTL = 3600  # seconds


class InsightEnvelope(BaseModel):
    date: date
    status: str
    generation_failed: bool
    generated_at: datetime | None
    payload: dict | None


class RefreshResponse(BaseModel):
    pipeline_run_id: str
    enqueued_at: str


@router.get("/today", response_model=InsightEnvelope)
async def get_insight_today(
    session: AsyncSession = Depends(get_session),
    current_user: UserOut = Depends(get_current_user),
) -> InsightEnvelope:
    from app.services.insights.insight_read_service import InsightReadService

    svc = InsightReadService(session, UUID(settings.sofa_belle_tenant_id))
    data = await svc.get_today()
    if data is None:
        raise HTTPException(status_code=404, detail="No insight available for today")
    return InsightEnvelope(**data)


@router.get("", response_model=InsightEnvelope)
async def get_insight_by_date(
    query_date: date = Query(..., alias="date"),
    session: AsyncSession = Depends(get_session),
    current_user: UserOut = Depends(get_current_user),
) -> InsightEnvelope:
    from app.services.insights.insight_read_service import InsightReadService

    svc = InsightReadService(session, UUID(settings.sofa_belle_tenant_id))
    data = await svc.get_by_date(query_date)
    if data is None:
        raise HTTPException(status_code=404, detail="No insight for this date")
    return InsightEnvelope(**data)


@router.post("/refresh", status_code=202, response_model=RefreshResponse)
async def refresh_insights(
    response: Response,
    session: AsyncSession = Depends(get_session),
    current_user: UserOut = Depends(get_current_user),
) -> RefreshResponse:
    rate_key = f"rate_limit:refresh:{current_user.id}"

    async with aioredis.from_url(settings.redis_url, decode_responses=True) as r:
        was_set = await r.set(rate_key, "1", nx=True, ex=RATE_LIMIT_TTL)
        if not was_set:
            ttl = await r.ttl(rate_key)
            retry_after = max(ttl, 0)
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Try again in {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)},
            )

    # Per locked decision: trigger the FULL daily_pipeline chain
    # (sync_mefi_leads → calculate_daily_kpis → detect_anomalies → generate_daily_insights)
    from app.tasks.etl.sync_mefi_leads import daily_pipeline

    tenant_id_str = str(UUID(settings.sofa_belle_tenant_id))
    task = daily_pipeline(tenant_id_str).delay()

    logger.info("insights.refresh_enqueued", user_id=str(current_user.id), task_id=str(task.id))
    return RefreshResponse(
        pipeline_run_id=str(task.id),
        enqueued_at=datetime.now(timezone.utc).isoformat(),
    )
