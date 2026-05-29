from __future__ import annotations

"""``get_funnel_data`` chat tool (D-02 + D-03).

Returns Lead → Vizita → Oferta → Contract funnel counts and conversion
rates for a date range. Thin wrapper around
:meth:`app.services.dashboards.dashboard_read_service.DashboardReadService.get_sales_dashboard`.

D-03: NO new SQL — entirely delegates to the Phase 6 read service.
DATA-04: monetary Decimals serialized as str via Python conversion.
LM-3: handler signature ``(tenant_id, session, inp)``.
LM-10: required fields use ``Field(..., description=...)``.
"""

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.chat.tools.base import Tool
from app.services.dashboards.dashboard_read_service import DashboardReadService


class GetFunnelDataInput(BaseModel):
    """Input schema for ``get_funnel_data``."""

    date_from: date = Field(..., description="Start date (inclusive). Format: YYYY-MM-DD.")
    date_to: date = Field(..., description="End date (inclusive). Format: YYYY-MM-DD.")


def _jsonable(value: object) -> object:
    """Recursive Decimal→str + date→ISO normalization (DATA-04)."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value


async def _handler(
    tenant_id: UUID,
    session: AsyncSession,
    inp: GetFunnelDataInput,
) -> dict:
    svc = DashboardReadService(session, tenant_id)
    raw = await svc.get_sales_dashboard(inp.date_from, inp.date_to)
    return _jsonable(raw)  # type: ignore[return-value]


TOOL = Tool(
    name="get_funnel_data",
    definition={
        "name": "get_funnel_data",
        "description": (
            "Returns Lead → Vizita → Oferta → Contract funnel counts and "
            "conversion rates for a date range. Includes WoW/MoM deltas, "
            "revenue, and per-source breakdown."
        ),
        "input_schema": GetFunnelDataInput.model_json_schema(),
    },
    input_schema=GetFunnelDataInput,
    handler=_handler,
)
