"""``get_loss_reasons`` chat tool — distribution of LOST leads (D-02 + D-03 NEW).

Thin ``text()`` query on ``v_mefi_leads_active`` (which includes both
active and lost leads) filtered by ``lifecycle='lost'`` and grouped by
either source category or salesperson.

D-02 NOTE: Sofa Belle's MEFI deal-value field is NULL for all leads in
MVP1 (Phase 3 finding). This handler intentionally returns only counts
and percentages — no monetary aggregates.

LM-3: handler signature ``(tenant_id, session, inp)``.
LM-4: tenant_id bound via ``bindparam("tid", type_=PG_UUID(as_uuid=True))``
because ``with_loader_criteria`` does not fire on ``text()`` queries
(Phase 6 Pitfall 5).
LM-10: required fields use ``Field(..., description=...)``.
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

# Canonical 11-source mapping — single source of truth from Phase 6.
from app.services.dashboards.dashboard_read_service import MEFI_SOURCE_ID_TO_NAME

logger = structlog.get_logger(__name__)


class GetLossReasonsInput(BaseModel):
    """Input schema for ``get_loss_reasons``."""

    date_from: date = Field(..., description="Start date (inclusive). Format: YYYY-MM-DD.")
    date_to: date = Field(..., description="End date (inclusive). Format: YYYY-MM-DD.")
    group_by: Literal["source", "salesperson"] = Field(
        "source",
        description=(
            "Group lost leads by canonical source category (11 Sofa Belle "
            "categories) or by salesperson_external_id."
        ),
    )


def _pct(num: int, denom: int) -> Decimal | None:
    if denom == 0:
        return None
    return (Decimal(num) / Decimal(denom) * Decimal("100")).quantize(Decimal("0.01"))


async def _handler(
    tenant_id: UUID,
    session: AsyncSession,
    inp: GetLossReasonsInput,
) -> dict:
    # CR-06: static enum→column map. Pydantic Literal is the first SQLi defense;
    # this dict is the second — KeyError fails closed if the Literal is relaxed.
    _GROUP_COLUMNS: dict[str, str] = {
        "source": "source_id",
        "salesperson": "assigned_to_id",
    }
    # CR-06: dict lookup fails closed (KeyError) if the Pydantic Literal is ever
    # relaxed; group_col comes from a static map, never user input, so the
    # f-string interpolation below stays injection-safe.
    group_col = _GROUP_COLUMNS[inp.group_by]

    sql = text(
        "SELECT "
        f"  {group_col} AS group_key, "
        "  COUNT(*) AS lost_count "
        "FROM v_mefi_leads_active "
        "WHERE tenant_id = :tid "
        "  AND lifecycle = 'lost' "
        "  AND (created_at_source AT TIME ZONE 'Europe/Bucharest')::date BETWEEN :df AND :dt "
        f"GROUP BY {group_col} "
        "ORDER BY lost_count DESC"
    ).bindparams(bindparam("tid", type_=PG_UUID(as_uuid=True)))

    result = await session.execute(
        sql,
        {"tid": tenant_id, "df": inp.date_from, "dt": inp.date_to},
    )
    rows = result.all() if hasattr(result, "all") else list(result)

    # Aggregate counts by canonical name (multiple unmapped source_ids
    # collapse into "other" so categories aren't duplicated in the response).
    by_name: dict[str | int, int] = {}
    for row in rows:
        raw_key = getattr(row, "group_key", None)
        count = int(getattr(row, "lost_count", 0) or 0)
        if inp.group_by == "source":
            name = MEFI_SOURCE_ID_TO_NAME.get(int(raw_key), "other") if raw_key is not None else "other"
        else:
            name = raw_key if raw_key is not None else "unassigned"
        by_name[name] = by_name.get(name, 0) + count

    total_lost = sum(by_name.values())
    groups = [
        {
            "name": name,
            "count": count,
            "pct": str(_pct(count, total_lost)) if total_lost > 0 else None,
        }
        for name, count in sorted(by_name.items(), key=lambda kv: (-kv[1], str(kv[0])))
    ]

    logger.bind(tenant_id=str(tenant_id), service="chat_tool").info(
        "chat.tool.get_loss_reasons.done",
        group_by=inp.group_by,
        total_lost=total_lost,
        groups=len(groups),
    )

    return {
        "groups": groups,
        "total_lost": total_lost,
        "group_by": inp.group_by,
        "period": {"date_from": inp.date_from.isoformat(), "date_to": inp.date_to.isoformat()},
    }


TOOL = Tool(
    name="get_loss_reasons",
    definition={
        "name": "get_loss_reasons",
        "description": (
            "Returns the distribution of LOST leads by source category or "
            "salesperson over a date range. Returns counts + percentages "
            "only — no monetary aggregates (deal-value data is unavailable "
            "in MVP1). Use this when the user asks 'where are we losing "
            "leads?' or 'which source has the highest loss rate?'."
        ),
        "input_schema": GetLossReasonsInput.model_json_schema(),
    },
    input_schema=GetLossReasonsInput,
    handler=_handler,
)
