from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.core.tenancy import require_tenant_id
from app.db.deps import get_session
from app.schemas.auth import UserOut
from app.schemas.health import HealthDataResponse, HealthResponse
from app.services.dashboards.health_read_service import HealthReadService

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=HealthResponse)
async def live() -> HealthResponse:
    return HealthResponse(status="ok")


# Свежесть данных — это данные арендатора, и отдавать их без спроса нельзя.
# Раньше эндпоинт был единственным без проверки: арендатор приходил из
# настройки, и любой запрос получал состояние Sofa Belle.
@router.get("/data", response_model=HealthDataResponse)
async def get_health_data(
    session: AsyncSession = Depends(get_session),
    current_user: UserOut = Depends(get_current_user),
) -> HealthDataResponse:
    svc = HealthReadService(session, require_tenant_id())
    data = await svc.get_health()
    return HealthDataResponse(**data)
