"""``get_recent_insight`` chat tool — wraps InsightReadService (D-02 + D-03).

Returns today's (yesterday in Europe/Bucharest — Phase 5 timing) AI-generated
daily insight, or the insight for a specific date when ``date`` is provided.

D-03: NO new SQL — entirely delegates to
:class:`app.services.insights.insight_read_service.InsightReadService`.
LM-3: handler signature ``(tenant_id, session, inp)``.
LM-10: required fields use ``Field(..., description=...)`` (the only required
field here is ``metric_name`` in sibling tools; ``date`` here is optional).
DATA-04: monetary values inside the insight payload remain strings (Phase 5
already serializes Decimals via ``model_dump(mode='json')``).
"""

from __future__ import annotations

from datetime import date as date_type
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.chat.tools.base import Tool
from app.services.insights.insight_read_service import InsightReadService


class GetRecentInsightInput(BaseModel):
    """Input schema for ``get_recent_insight``."""

    date: date_type | None = Field(
        None,
        description=(
            "If null, returns the most recent insight (yesterday in "
            "Europe/Bucharest — Phase 5 pipeline runs at 06:00 for the "
            "previous day's data). Else returns the insight for that "
            "specific calendar date."
        ),
    )


def _jsonable(value: object) -> object:
    """Recursive Decimal→str + date→ISO normalization (DATA-04)."""
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
    inp: GetRecentInsightInput,
) -> dict:
    svc = InsightReadService(session, tenant_id)
    if inp.date is None:
        raw = await svc.get_today()
    else:
        raw = await svc.get_by_date(inp.date)

    if raw is None:
        return {"insight": None}
    return {"insight": _jsonable(raw)}


TOOL = Tool(
    name="get_recent_insight",
    definition={
        "name": "get_recent_insight",
        "description": (
            "Returns the most recent (or for a specific date) AI-generated "
            "daily insight report — top problems, recommended actions, and "
            "Romanian summary. Use this when the user asks 'what should I "
            "do today?' or wants to revisit an earlier insight."
        ),
        "input_schema": GetRecentInsightInput.model_json_schema(),
    },
    input_schema=GetRecentInsightInput,
    handler=_handler,
)
