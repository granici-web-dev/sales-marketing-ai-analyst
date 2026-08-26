"""``get_kpi`` chat tool — aggregated KPI values for a date range (D-02 + D-03).

Wraps :class:`app.services.metrics.daily_kpi_service.DailyKpiService`. The
underlying service exposes only ``compute_for_date(date) -> dict``; this
handler iterates each day in ``[date_from, date_to]`` and aggregates the
requested metrics in Python.

D-03: NO new SQL — every value comes from DailyKpiService.compute_for_date.
DATA-04 / Phase 5 D-19: monetary Decimals serialized as ``str``.
LM-3: handler signature is ``(tenant_id, session, inp)``.
LM-10: required fields use ``Field(..., description=...)``.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.chat.tools.base import Tool
from app.services.metrics.daily_kpi_service import DailyKpiService

# Metrics accepted by Claude. Each maps to one daily_kpi column (or a
# group of columns). Unknown metrics are silently ignored to keep the
# handler resilient to Claude requesting near-synonyms.
_KNOWN_METRICS: set[str] = {
    "revenue",
    "contracts",
    "leads",
    "visits",
    "offers",
    "avg_deal_size",
    "conversion_rate",
    "conversion_l_to_v",
    "conversion_v_to_o",
    "conversion_l_to_o",
    "conversion_o_to_c",
    "conversion_l_to_c",
}


class GetKpiInput(BaseModel):
    """Input schema for ``get_kpi``."""

    date_from: date = Field(..., description="Start date (inclusive). Format: YYYY-MM-DD.")
    date_to: date = Field(..., description="End date (inclusive). Format: YYYY-MM-DD.")
    metrics: list[str] = Field(..., description=(
        "Metric names to aggregate. Supported: revenue, contracts, leads, "
        "visits, offers, avg_deal_size, conversion_rate, conversion_l_to_v, "
        "conversion_v_to_o, conversion_l_to_o, conversion_o_to_c, "
        "conversion_l_to_c."
    ))


def _to_jsonable(value: object) -> object:
    """Decimal → str per DATA-04 / Phase 5 D-19."""
    if isinstance(value, Decimal):
        return str(value)
    return value


async def _handler(
    tenant_id: UUID,
    session: AsyncSession,
    inp: GetKpiInput,
) -> dict:
    svc = DailyKpiService(session, tenant_id)

    if inp.date_to < inp.date_from:
        return {
            "error": "date_to must be on or after date_from",
            "date_from": inp.date_from.isoformat(),
            "date_to": inp.date_to.isoformat(),
        }

    requested = [m for m in inp.metrics if m in _KNOWN_METRICS]
    # Count + revenue accumulators over the range. We always accumulate all four
    # underlying counts so conversion rates can be computed as PERIOD FUNNEL RATIOS
    # from summed counts (Phase 3 hotfix 2026-05-30) — NOT averaged daily rates.
    # contracts_count is event-based (signed in period) in daily_kpi_service; summing
    # daily values gives the period total that matches MEFI.
    leads_total = 0
    visits_total = 0
    offers_total = 0
    contracts_total = 0
    revenue_total = Decimal("0")
    days = 0

    day = inp.date_from
    while day <= inp.date_to:
        row = await svc.compute_for_date(day)
        days += 1
        leads_total += int(row.get("leads_total") or 0)
        visits_total += int(row.get("visits_count") or 0)
        offers_total += int(row.get("offers_count") or 0)
        contracts_total += int(row.get("contracts_count") or 0)
        rev = row.get("revenue")
        if rev is not None:
            revenue_total += Decimal(str(rev))
        day = day + timedelta(days=1)

    def _ratio(num: int, den: int) -> Decimal | None:
        """Period funnel ratio with NULLIF zero-division guard."""
        if not den:
            return None
        return Decimal(str(num)) / Decimal(str(den))

    # Map each conversion metric to its (numerator, denominator) period counts.
    _rate_map: dict[str, tuple[int, int]] = {
        "conversion_l_to_v": (visits_total, leads_total),
        "conversion_v_to_o": (offers_total, visits_total),
        "conversion_l_to_o": (offers_total, leads_total),
        "conversion_o_to_c": (contracts_total, offers_total),
        "conversion_l_to_c": (contracts_total, leads_total),
        "conversion_rate": (contracts_total, leads_total),  # alias → l_to_c
    }
    _count_map: dict[str, int] = {
        "leads": leads_total,
        "visits": visits_total,
        "offers": offers_total,
        "contracts": contracts_total,
    }

    output: dict = {
        "period": {
            "date_from": inp.date_from.isoformat(),
            "date_to": inp.date_to.isoformat(),
            "days": days,
        },
        "metrics": {},
    }
    for metric in requested:
        if metric in _count_map:
            output["metrics"][metric] = str(Decimal(_count_map[metric]))
        elif metric == "revenue":
            output["metrics"]["revenue"] = str(revenue_total)
        elif metric == "avg_deal_size":
            output["metrics"]["avg_deal_size"] = (
                str(revenue_total / Decimal(contracts_total)) if contracts_total > 0 else None
            )
        elif metric in _rate_map:
            num, den = _rate_map[metric]
            rate = _ratio(num, den)
            output["metrics"][metric] = str(rate) if rate is not None else None

    # Sanitize any stragglers (defensive — DATA-04)
    for k, v in list(output["metrics"].items()):
        output["metrics"][k] = _to_jsonable(v)

    return output


TOOL = Tool(
    name="get_kpi",
    definition={
        "name": "get_kpi",
        "description": (
            "Returns aggregated KPI values for a date range. Use this when "
            "the user asks about revenue, contracts, deal size, conversion "
            "rates, or lead/visit/offer counts."
        ),
        "input_schema": GetKpiInput.model_json_schema(),
    },
    input_schema=GetKpiInput,
    handler=_handler,
)
