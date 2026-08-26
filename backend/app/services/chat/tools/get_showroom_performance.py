"""``get_showroom_performance`` chat tool — per-showroom funnel (D-02 + D-03 NEW).

Thin ``text()`` query on ``v_mefi_leads_active`` grouped by ``showroom``.
The view exposes ``showroom`` as a TEXT column (populated from raw custom
field ``form-cf-14``) storing one of the 3 Sofa Belle showroom names:
Brașov, București, Cluj-Napoca. Returns funnel counts and conversion rate
per showroom.

LM-3: handler signature ``(tenant_id, session, inp)``.
LM-4: tenant_id bound via ``bindparam("tid", type_=PG_UUID(as_uuid=True))``
because ``text()`` queries bypass ``with_loader_criteria`` (Phase 6 Pitfall 5).
LM-10: required fields use ``Field(..., description=...)``.

Sofa Belle context: showroom is the primary conversion channel (29.5% of
leads, 55% of contracts per Phase 3 verified-COMPLETE finding). See
``docs/SOFABELLE.md`` for the 3 showroom names.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

import structlog
from pydantic import BaseModel, Field
from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.chat.tools.base import Tool

logger = structlog.get_logger(__name__)


ShowroomName = Literal["Brașov", "București", "Cluj-Napoca"]


class GetShowroomPerformanceInput(BaseModel):
    """Input schema for ``get_showroom_performance``."""

    date_from: date = Field(..., description="Start date (inclusive). Format: YYYY-MM-DD.")
    date_to: date = Field(..., description="End date (inclusive). Format: YYYY-MM-DD.")
    showroom: ShowroomName | None = Field(
        None,
        description=(
            "Optional showroom filter. Allowed values: Brașov, București, "
            "Cluj-Napoca. Omit to return all 3 showrooms."
        ),
    )


def _conv(num: int, denom: int) -> str | None:
    if denom == 0:
        return None
    return str((Decimal(num) / Decimal(denom)).quantize(Decimal("0.0001")))


async def _handler(
    tenant_id: UUID,
    session: AsyncSession,
    inp: GetShowroomPerformanceInput,
) -> dict:
    # leads / visits / offers on the CREATION cohort (created_at_source).
    sql = text(
        "SELECT "
        "  showroom AS showroom, "
        "  COUNT(*) AS leads, "
        "  COUNT(*) FILTER (WHERE reached_visit) AS visits, "
        "  COUNT(*) FILTER (WHERE reached_offer) AS offers "
        "FROM v_mefi_leads_active "
        "WHERE tenant_id = :tid "
        "  AND showroom IS NOT NULL "
        "  AND (created_at_source AT TIME ZONE 'Europe/Bucharest')::date BETWEEN :df AND :dt "
        "GROUP BY showroom "
        "ORDER BY leads DESC"
    ).bindparams(bindparam("tid", type_=PG_UUID(as_uuid=True)))

    result = await session.execute(
        sql,
        {"tid": tenant_id, "df": inp.date_from, "dt": inp.date_to},
    )
    rows = result.all() if hasattr(result, "all") else list(result)

    # contracts on the EVENT model: deals SIGNED in the period (status→Clienți,
    # status_id=1), keyed on status_changed_at, grouped by showroom (Phase 3 hotfix
    # 2026-05-30). A lead created earlier but signed in-period counts here.
    contracts_sql = text(
        "SELECT showroom AS showroom, COUNT(*) AS contracts "
        "FROM v_mefi_leads_active "
        "WHERE tenant_id = :tid "
        "  AND showroom IS NOT NULL "
        "  AND status_id = 1 "
        "  AND (status_changed_at AT TIME ZONE 'Europe/Bucharest')::date BETWEEN :df AND :dt "
        "GROUP BY showroom"
    ).bindparams(bindparam("tid", type_=PG_UUID(as_uuid=True)))
    contracts_result = await session.execute(
        contracts_sql,
        {"tid": tenant_id, "df": inp.date_from, "dt": inp.date_to},
    )
    contracts_rows = (
        contracts_result.all() if hasattr(contracts_result, "all") else list(contracts_result)
    )
    contracts_by_showroom: dict[str, int] = {
        getattr(r, "showroom", None): int(getattr(r, "contracts", 0) or 0) for r in contracts_rows
    }
    leads_lookup = {getattr(r, "showroom", None): r for r in rows}

    # Union showroom names from both queries so a showroom with in-period contracts
    # but no in-period new leads is still emitted (ordered by leads desc, like before).
    ordered_names = [getattr(r, "showroom", None) for r in rows]
    for name in contracts_by_showroom:
        if name not in leads_lookup:
            ordered_names.append(name)

    showrooms = []
    for showroom_name in ordered_names:
        row = leads_lookup.get(showroom_name)
        leads = int(getattr(row, "leads", 0) or 0) if row is not None else 0
        visits = int(getattr(row, "visits", 0) or 0) if row is not None else 0
        offers = int(getattr(row, "offers", 0) or 0) if row is not None else 0
        contracts = contracts_by_showroom.get(showroom_name, 0)
        showrooms.append(
            {
                "showroom": showroom_name,
                "leads": leads,
                "visits": visits,
                "offers": offers,
                "contracts": contracts,
                "conversion_l_to_v": _conv(visits, leads),
                "conversion_l_to_c": _conv(contracts, leads),
                "conversion_o_to_c": _conv(contracts, offers),
            }
        )

    if inp.showroom is not None:
        showrooms = [s for s in showrooms if s["showroom"] == inp.showroom]

    logger.bind(tenant_id=str(tenant_id), service="chat_tool").info(
        "chat.tool.get_showroom_performance.done",
        filter=inp.showroom,
        count=len(showrooms),
    )

    return {
        "showrooms": showrooms,
        "period": {"date_from": inp.date_from.isoformat(), "date_to": inp.date_to.isoformat()},
        "filter": inp.showroom,
    }


TOOL = Tool(
    name="get_showroom_performance",
    definition={
        "name": "get_showroom_performance",
        "description": (
            "Returns funnel and conversion KPIs broken down by showroom "
            "(Brașov, București, Cluj-Napoca). Showroom is the primary "
            "conversion channel for Sofa Belle (29.5% of leads, 55% of "
            "contracts). Set the optional showroom filter to compare one "
            "branch to the others."
        ),
        "input_schema": GetShowroomPerformanceInput.model_json_schema(),
    },
    input_schema=GetShowroomPerformanceInput,
    handler=_handler,
)
