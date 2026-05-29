from __future__ import annotations

"""``get_lead_categories_breakdown`` chat tool (D-02 + D-03).

Returns lead volume by canonical source category (11 Sofa Belle categories
per :data:`MEFI_SOURCE_ID_TO_NAME`). Wraps
:meth:`DashboardReadService.get_marketing_dashboard`.

D-03: NO new SQL.
DATA-04: Decimals serialized as str.
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


class GetLeadCategoriesBreakdownInput(BaseModel):
    """Input schema for ``get_lead_categories_breakdown``."""

    date_from: date = Field(..., description="Start date (inclusive). Format: YYYY-MM-DD.")
    date_to: date = Field(..., description="End date (inclusive). Format: YYYY-MM-DD.")


def _jsonable(value: object) -> object:
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
    inp: GetLeadCategoriesBreakdownInput,
) -> dict:
    svc = DashboardReadService(session, tenant_id)
    raw = await svc.get_marketing_dashboard(inp.date_from, inp.date_to)
    return _jsonable(raw)  # type: ignore[return-value]


TOOL = Tool(
    name="get_lead_categories_breakdown",
    definition={
        "name": "get_lead_categories_breakdown",
        "description": (
            "Returns lead volume by canonical source category. The 11 Sofa "
            "Belle categories are: showroom, mail, telefon, whatsapp, site, "
            "colaborare, meta, recomandare, arhitect, client_fidel, other. "
            "Also returns junk-by-source counts and a site conversion-rate "
            "approximation (Iteration 2 ad-spend metrics are null in MVP1)."
        ),
        "input_schema": GetLeadCategoriesBreakdownInput.model_json_schema(),
    },
    input_schema=GetLeadCategoriesBreakdownInput,
    handler=_handler,
)
