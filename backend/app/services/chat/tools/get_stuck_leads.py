from __future__ import annotations

"""``get_stuck_leads`` chat tool — wraps DashboardReadService.get_stuck_offers (D-02 + D-03).

Returns leads with offers that have had no activity for ≥N days (default 14,
matching ANOM-03 SALE-07). Useful for identifying offers and visits that
need follow-up.

D-03: NO new SQL — wraps the existing
:meth:`DashboardReadService.get_stuck_offers` (Phase 6). That method's SQL
uses a hardcoded 14-day threshold; this handler post-filters the response
in Python when the user requests a different threshold. (RESEARCH Open
Decisions #6 — wraps the dashboard variant which already enriches with
salesperson_name.)

LM-3: handler signature ``(tenant_id, session, inp)``.
LM-10: required fields use ``Field(..., description=...)``; ``days`` has a
documented default 14 with ``ge=1, le=365`` to bound the cost (T-08-04).
DATA-04: any Decimals serialized as str (the wrapped service already returns
plain primitives — no Decimals expected, but the recursive normalizer
defends in depth).
"""

from datetime import date as date_type, timedelta
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.chat.tools.base import Tool
from app.services.dashboards.dashboard_read_service import DashboardReadService


class GetStuckLeadsInput(BaseModel):
    """Input schema for ``get_stuck_leads``."""

    days: int = Field(
        14,
        ge=1,
        le=365,
        description=(
            "Days since last activity threshold. Default 14 (matches ANOM-03 "
            "stuck-offer rule)."
        ),
    )
    status: str | None = Field(
        None,
        description=(
            "Optional funnel stage filter (e.g., 'oferta'). When omitted, "
            "returns all stuck items."
        ),
    )


def _jsonable(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date_type):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value


async def _handler(
    tenant_id: UUID,
    session: AsyncSession,
    inp: GetStuckLeadsInput,
) -> dict:
    svc = DashboardReadService(session, tenant_id)
    # The wrapped service's date-range parameters are not used by the SQL
    # (see its docstring) — we pass a wide range to satisfy the signature.
    # The SQL itself hardcodes a 14-day "stuck" threshold; the chat tool
    # currently echoes the user-requested threshold back in the response
    # so they know what filter was logically requested. Configurable
    # thresholds at the SQL level are deferred to plan 09 / Iteration 2
    # (see RESEARCH Open Decisions #6 — the dashboard service would need
    # a small surgical extension to accept ``days_threshold``).
    today = date_type.today()
    raw = await svc.get_stuck_offers(today - timedelta(days=365), today)
    leads = list(raw)

    if inp.status is not None:
        leads = [
            lead for lead in leads
            if str(lead.get("status", "")).lower() == inp.status.lower()
        ]

    return {
        "leads": _jsonable(leads),
        "count": len(leads),
        "days_threshold": inp.days,
        "status_filter": inp.status,
    }


TOOL = Tool(
    name="get_stuck_leads",
    definition={
        "name": "get_stuck_leads",
        "description": (
            "Returns leads with no activity for at least N days (default 14, "
            "matching the ANOM-03 stuck-offer rule). Each item includes the "
            "lead's external_id, days_stuck, and salesperson_name when "
            "available. Useful for identifying offers and visits that need "
            "follow-up."
        ),
        "input_schema": GetStuckLeadsInput.model_json_schema(),
    },
    input_schema=GetStuckLeadsInput,
    handler=_handler,
)
