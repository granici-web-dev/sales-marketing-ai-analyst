from __future__ import annotations

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
    # Count and Decimal accumulators keyed by metric name.
    sums: dict[str, Decimal] = {}
    rate_values: dict[str, list[Decimal]] = {}
    counts: dict[str, int] = {}
    revenue_total = Decimal("0")
    contracts_total = 0

    day = inp.date_from
    while day <= inp.date_to:
        row = await svc.compute_for_date(day)
        counts.setdefault("days", 0)
        counts["days"] += 1

        for metric in requested:
            if metric == "leads":
                val = row.get("leads_total") or 0
                sums["leads"] = sums.get("leads", Decimal("0")) + Decimal(int(val))
            elif metric == "visits":
                val = row.get("visits_count") or 0
                sums["visits"] = sums.get("visits", Decimal("0")) + Decimal(int(val))
            elif metric == "offers":
                val = row.get("offers_count") or 0
                sums["offers"] = sums.get("offers", Decimal("0")) + Decimal(int(val))
            elif metric == "contracts":
                val = row.get("contracts_count") or 0
                sums["contracts"] = sums.get("contracts", Decimal("0")) + Decimal(int(val))
            elif metric == "revenue":
                val = row.get("revenue")
                if val is not None:
                    sums["revenue"] = sums.get("revenue", Decimal("0")) + Decimal(str(val))
            elif metric == "avg_deal_size":
                # We need totals to compute the range average — track totals
                rev = row.get("revenue")
                if rev is not None:
                    revenue_total += Decimal(str(rev))
                ct = row.get("contracts_count") or 0
                contracts_total += int(ct)
            elif metric.startswith("conversion_") or metric == "conversion_rate":
                # Rates are averaged over days where the rate is not None.
                key = "conversion_l_to_c" if metric == "conversion_rate" else metric
                val = row.get(key)
                if val is not None:
                    rate_values.setdefault(metric, []).append(Decimal(str(val)))
        day = day + timedelta(days=1)

    output: dict = {
        "period": {
            "date_from": inp.date_from.isoformat(),
            "date_to": inp.date_to.isoformat(),
            "days": counts.get("days", 0),
        },
        "metrics": {},
    }
    for metric, total in sums.items():
        output["metrics"][metric] = str(total)
    for metric, vals in rate_values.items():
        if vals:
            avg = sum(vals, Decimal("0")) / Decimal(len(vals))
            output["metrics"][metric] = str(avg)
        else:
            output["metrics"][metric] = None
    if "avg_deal_size" in requested:
        if contracts_total > 0:
            output["metrics"]["avg_deal_size"] = str(
                revenue_total / Decimal(contracts_total)
            )
        else:
            output["metrics"]["avg_deal_size"] = None

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
