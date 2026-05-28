from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.deps import get_session
from app.schemas.health import HealthDataResponse, HealthResponse
from app.services.dashboards.health_read_service import HealthReadService

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=HealthResponse)
async def live() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/data", response_model=HealthDataResponse)
async def get_health_data(
    session: AsyncSession = Depends(get_session),
) -> HealthDataResponse:
    svc = HealthReadService(session, UUID(settings.sofa_belle_tenant_id))
    data = await svc.get_health()
    return HealthDataResponse(**data)
