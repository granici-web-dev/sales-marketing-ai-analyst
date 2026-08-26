"""``get_trend`` chat tool — time series of one metric (D-02 + D-03).

Returns the daily time series of one metric (revenue, contracts, leads, or
a conversion rate) over the last 7 / 30 / 90 days, optionally aggregated
to weekly granularity in Python.

D-03: NO new SQL — calls
:meth:`DailyKpiService.compute_for_date` once per day in the window.
DATA-04: every numeric value serialized as str.
LM-3: handler signature ``(tenant_id, session, inp)``.
LM-10: required fields use ``Field(..., description=...)``.

Note: ``DailyKpiService`` exposes only a per-day method (no
``aggregate_for_range``); we loop in Python — acceptable for the small
fixed windows allowed by ``period_days: Literal[7, 30, 90]`` (T-08-04 cost
guard).
"""

from __future__ import annotations

from datetime import date as date_type
from datetime import timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.chat.tools.base import Tool
from app.services.metrics.daily_kpi_service import DailyKpiService

MetricName = Literal[
    "revenue",
    "contracts",
    "leads",
    "visits",
    "offers",
    "conversion_l_to_v",
    "conversion_v_to_o",
    "conversion_l_to_o",
    "conversion_o_to_c",
    "conversion_l_to_c",
]


_METRIC_TO_COLUMN: dict[str, str] = {
    "revenue": "revenue",
    "contracts": "contracts_count",
    "leads": "leads_total",
    "visits": "visits_count",
    "offers": "offers_count",
    "conversion_l_to_v": "conversion_l_to_v",
    "conversion_v_to_o": "conversion_v_to_o",
    "conversion_l_to_o": "conversion_l_to_o",
    "conversion_o_to_c": "conversion_o_to_c",
    "conversion_l_to_c": "conversion_l_to_c",
}


class GetTrendInput(BaseModel):
    """Input schema for ``get_trend``."""

    metric_name: MetricName = Field(
        ...,
        description=(
            "One metric to track over time. Supported: revenue, contracts, "
            "leads, visits, offers, and the 5 conversion rates "
            "(conversion_l_to_v, conversion_v_to_o, conversion_l_to_o, "
            "conversion_o_to_c, conversion_l_to_c)."
        ),
    )
    period_days: Literal[7, 30, 90] = Field(
        30, description="Time window in days (must be 7, 30, or 90)."
    )
    granularity: Literal["day", "week"] = Field(
        "day", description="Aggregation granularity — 'day' (default) or 'week'."
    )


def _to_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001 — defensive cast
        return None


def _aggregate_weekly(
    points: list[dict],
    column: str,
    is_rate: bool,
) -> list[dict]:
    """Roll daily points up to weekly buckets (Mon-anchored ISO weeks).

    For rate metrics, the weekly value is the simple mean of non-null
    daily rates in the week. For counters and revenue, it is the sum.
    """
    by_week: dict[tuple[int, int], list[Decimal]] = {}
    for point in points:
        d: date_type = point["date"]
        val: Decimal | None = point["raw_value"]
        if val is None:
            continue
        iso = d.isocalendar()
        key = (iso.year, iso.week)
        by_week.setdefault(key, []).append(val)

    weekly: list[dict] = []
    for (iso_year, iso_week), values in sorted(by_week.items()):
        if is_rate:
            agg = sum(values, Decimal("0")) / Decimal(len(values))
        else:
            agg = sum(values, Decimal("0"))
        # Represent the bucket by its Monday date.
        monday = date_type.fromisocalendar(iso_year, iso_week, 1)
        weekly.append(
            {
                "date": monday.isoformat(),
                "value": str(agg),
            }
        )
    return weekly


async def _handler(
    tenant_id: UUID,
    session: AsyncSession,
    inp: GetTrendInput,
) -> dict:
    svc = DailyKpiService(session, tenant_id)
    column = _METRIC_TO_COLUMN[inp.metric_name]
    is_rate = inp.metric_name.startswith("conversion_")

    today = date_type.today()
    start = today - timedelta(days=inp.period_days - 1)

    # Collect per-day points.
    raw_points: list[dict] = []
    day = start
    while day <= today:
        row = await svc.compute_for_date(day)
        val = _to_decimal(row.get(column)) if row else None
        raw_points.append({"date": day, "raw_value": val})
        day = day + timedelta(days=1)

    if inp.granularity == "day":
        points = [
            {
                "date": p["date"].isoformat(),
                "value": str(p["raw_value"]) if p["raw_value"] is not None else None,
            }
            for p in raw_points
        ]
    else:
        points = _aggregate_weekly(raw_points, column, is_rate)

    return {
        "metric": inp.metric_name,
        "granularity": inp.granularity,
        "period_days": inp.period_days,
        "points": points,
    }


TOOL = Tool(
    name="get_trend",
    definition={
        "name": "get_trend",
        "description": (
            "Returns a time series of one metric (revenue, contracts, leads, "
            "or a conversion rate) over the last 7, 30, or 90 days with "
            "daily or weekly granularity. Use this when the user asks about "
            "trends — 'how has revenue evolved this month?'."
        ),
        "input_schema": GetTrendInput.model_json_schema(),
    },
    input_schema=GetTrendInput,
    handler=_handler,
)
