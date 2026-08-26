"""``get_salesperson_performance`` chat tool (D-02 + D-03).

Returns per-salesperson KPIs (leads, visits, offers, contracts, revenue,
win-rate, TTFT, data completeness). Wraps
:meth:`DashboardReadService.get_salespeople_dashboard`.

When ``salesperson_external_id`` is provided, the handler post-filters the
returned ``salespeople`` list to a single rep (the existing service does
not accept that parameter; filter is applied at the tool layer).

D-03: NO new SQL.
DATA-04 / Phase 5 D-19: Decimals serialized as str.
LM-3: handler signature ``(tenant_id, session, inp)``.
LM-10: required fields use ``Field(..., description=...)``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.chat.tools.base import Tool
from app.services.dashboards.dashboard_read_service import DashboardReadService


class GetSalespersonPerformanceInput(BaseModel):
    """Input schema for ``get_salesperson_performance``."""

    date_from: date = Field(..., description="Start date (inclusive). Format: YYYY-MM-DD.")
    date_to: date = Field(..., description="End date (inclusive). Format: YYYY-MM-DD.")
    salesperson_external_id: int | None = Field(None, description=(
        "Optional MEFI salesperson external_id. When provided, the "
        "response is filtered to that one rep. Omit to return all reps."
    ))


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
    inp: GetSalespersonPerformanceInput,
) -> dict:
    svc = DashboardReadService(session, tenant_id)
    raw = await svc.get_salespeople_dashboard(inp.date_from, inp.date_to)

    salespeople = raw.get("salespeople", [])
    if inp.salesperson_external_id is not None:
        # Compare against string external_ids — the service returns them as
        # either int or str depending on the column type; normalize both.
        target = str(inp.salesperson_external_id)
        salespeople = [
            sp
            for sp in salespeople
            if str(sp.get("external_id")) == target
        ]
        raw = {**raw, "salespeople": salespeople}

    return _jsonable(raw)  # type: ignore[return-value]


TOOL = Tool(
    name="get_salesperson_performance",
    definition={
        "name": "get_salesperson_performance",
        "description": (
            "Returns per-salesperson performance KPIs (leads assigned, visits "
            "conducted, offers sent, deals won, revenue, win-rate, average "
            "time-to-first-touch in minutes, data completeness percentage) for "
            "a date range. If salesperson_external_id is provided, the response "
            "is filtered to that one rep."
        ),
        "input_schema": GetSalespersonPerformanceInput.model_json_schema(),
    },
    input_schema=GetSalespersonPerformanceInput,
    handler=_handler,
)
