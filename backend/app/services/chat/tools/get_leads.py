from __future__ import annotations

"""``get_leads`` chat tool — thin v_mefi_leads_active text() query (D-02 + D-03 NEW).

Returns a small sample of leads (max 50) with optional filters on lifecycle,
salesperson, source, and creation date range. This is one of the three
documented thin-text() queries the registry adds beyond the existing Phase
3/6 services (per D-03 exception).

LM-4 enforcement: tenant_id is bound explicitly via
``bindparam("tid", type_=PG_UUID(as_uuid=True))`` because
``text()`` queries do NOT trigger ``with_loader_criteria`` (Phase 6 Pitfall 5).

LM-10: required fields use ``Field(..., description=...)``.
DATA-04: monetary values serialized as str.

When ``lifecycle='junk'`` the handler queries ``raw_mefi_leads`` directly
(the conformed view ``v_mefi_leads_active`` excludes junk by design).
Otherwise the query targets ``v_mefi_leads_active``.
"""

from datetime import date, datetime
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


class GetLeadsInput(BaseModel):
    """Input schema for ``get_leads``."""

    lifecycle: Literal["active", "lost", "junk", "all"] = Field(
        "all",
        description=(
            "Filter by lifecycle. 'all' returns active+lost (the default — "
            "Sofa Belle excludes junk from metrics). 'junk' queries the "
            "raw table (marketing hygiene analysis)."
        ),
    )
    salesperson_external_id: int | None = Field(
        None, description="Optional MEFI salesperson external_id."
    )
    source_id: int | None = Field(
        None, description="Optional MEFI source_id (1-13)."
    )
    date_from: date | None = Field(
        None, description="Optional inclusive lower bound on created date."
    )
    date_to: date | None = Field(
        None, description="Optional inclusive upper bound on created date."
    )
    limit: int = Field(
        50, ge=1, le=50, description="Max number of leads (capped at 50)."
    )


def _serialize_lead(row: object) -> dict:
    """Convert a query row into a JSON-safe dict (DATA-04)."""
    created = getattr(row, "created_at_source", None)
    est = getattr(row, "estimated_value", None)
    return {
        "external_id": getattr(row, "external_id", None),
        "lifecycle": getattr(row, "lifecycle", None),
        "source_id": getattr(row, "source_id", None),
        "salesperson_external_id": getattr(row, "assigned_to_id", None),
        "created_at_source": (
            created.isoformat() if isinstance(created, datetime) else created
        ),
        "estimated_value": str(est) if isinstance(est, Decimal) else est,
    }


async def _handler(
    tenant_id: UUID,
    session: AsyncSession,
    inp: GetLeadsInput,
) -> dict:
    # Choose source table — junk lives only in raw_mefi_leads (the conformed
    # view filters lifecycle IN ('active','lost')).
    source_table = "raw_mefi_leads" if inp.lifecycle == "junk" else "v_mefi_leads_active"

    where_clauses: list[str] = ["tenant_id = :tid"]
    bindkwargs: dict = {
        "tid": tenant_id,
        "lim": inp.limit,
    }

    if inp.lifecycle == "all":
        # v_mefi_leads_active already restricts to active|lost — no clause needed.
        pass
    elif inp.lifecycle == "active":
        where_clauses.append("lifecycle = 'active'")
    elif inp.lifecycle == "lost":
        where_clauses.append("lifecycle = 'lost'")
    elif inp.lifecycle == "junk":
        where_clauses.append("lifecycle = 'junk'")

    if inp.salesperson_external_id is not None:
        where_clauses.append("assigned_to_id = :sp_id")
        bindkwargs["sp_id"] = inp.salesperson_external_id
    if inp.source_id is not None:
        where_clauses.append("source_id = :src_id")
        bindkwargs["src_id"] = inp.source_id
    if inp.date_from is not None:
        where_clauses.append("(created_at_source AT TIME ZONE 'Europe/Bucharest')::date >= :df")
        bindkwargs["df"] = inp.date_from
    if inp.date_to is not None:
        where_clauses.append("(created_at_source AT TIME ZONE 'Europe/Bucharest')::date <= :dt")
        bindkwargs["dt"] = inp.date_to

    sql = (
        "SELECT external_id, lifecycle, source_id, assigned_to_id, "
        "       created_at_source, estimated_value "
        f"FROM {source_table} "
        f"WHERE {' AND '.join(where_clauses)} "
        "ORDER BY created_at_source DESC NULLS LAST "
        "LIMIT :lim"
    )
    # LM-4: bind tenant_id explicitly via PG_UUID — text() bypasses
    # with_loader_criteria. Other params bind via .params() at execute time.
    stmt = text(sql).bindparams(bindparam("tid", type_=PG_UUID(as_uuid=True)))

    result = await session.execute(stmt, bindkwargs)
    rows = result.all() if hasattr(result, "all") else list(result)

    leads = [_serialize_lead(r) for r in rows]
    logger.bind(tenant_id=str(tenant_id), service="chat_tool").info(
        "chat.tool.get_leads.done",
        lifecycle=inp.lifecycle,
        count=len(leads),
        limit=inp.limit,
    )

    return {
        "leads": leads,
        "count": len(leads),
        "limit": inp.limit,
        "lifecycle": inp.lifecycle,
    }


TOOL = Tool(
    name="get_leads",
    definition={
        "name": "get_leads",
        "description": (
            "Returns a sample of leads (max 50) with optional filters: "
            "lifecycle (active/lost/junk/all), salesperson_external_id, "
            "source_id, created date range. Does NOT include client PII "
            "(names, phones, emails) — only structural identifiers."
        ),
        "input_schema": GetLeadsInput.model_json_schema(),
    },
    input_schema=GetLeadsInput,
    handler=_handler,
)
