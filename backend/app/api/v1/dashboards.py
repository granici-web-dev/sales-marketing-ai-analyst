from __future__ import annotations

from datetime import date
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.db.deps import get_session
from app.schemas.auth import UserOut
from app.schemas.dashboards.marketing import MarketingDashboardResponse
from app.schemas.dashboards.sales import SalesDashboardResponse
from app.schemas.dashboards.salespeople import SalespeopleDashboardResponse
from app.services.dashboards.dashboard_read_service import DashboardReadService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/dashboards", tags=["dashboards"])


@router.get("/sales", response_model=SalesDashboardResponse)
async def get_sales_dashboard(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    session: AsyncSession = Depends(get_session),
    current_user: UserOut = Depends(get_current_user),
) -> SalesDashboardResponse:
    logger.debug("dashboards.sales.request", user_id=str(current_user.id))
    svc = DashboardReadService(session, UUID(settings.sofa_belle_tenant_id))
    data = await svc.get_sales_dashboard(from_date, to_date)
    return SalesDashboardResponse(**data)


@router.get("/salespeople", response_model=SalespeopleDashboardResponse)
async def get_salespeople_dashboard(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    session: AsyncSession = Depends(get_session),
    current_user: UserOut = Depends(get_current_user),
) -> SalespeopleDashboardResponse:
    logger.debug("dashboards.salespeople.request", user_id=str(current_user.id))
    svc = DashboardReadService(session, UUID(settings.sofa_belle_tenant_id))
    data = await svc.get_salespeople_dashboard(from_date, to_date)
    return SalespeopleDashboardResponse(**data)


@router.get("/marketing", response_model=MarketingDashboardResponse)
async def get_marketing_dashboard(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    session: AsyncSession = Depends(get_session),
    current_user: UserOut = Depends(get_current_user),
) -> MarketingDashboardResponse:
    logger.debug("dashboards.marketing.request", user_id=str(current_user.id))
    svc = DashboardReadService(session, UUID(settings.sofa_belle_tenant_id))
    data = await svc.get_marketing_dashboard(from_date, to_date)
    return MarketingDashboardResponse(**data)
