"""``compare_periods`` chat tool — 2x DashboardReadService + delta math (D-02 + D-03).

Calls :meth:`DashboardReadService.get_sales_dashboard` twice (period A and
period B) and produces a ``deltas`` dict with the per-metric percent change
(`(A - B) / B * 100`, rounded to one decimal place, zero-guard returns null).

D-03: NO new SQL — entirely composed of two existing service calls.
DATA-04: deltas + monetary values serialized as str.
LM-3: handler signature ``(tenant_id, session, inp)``.
LM-10: required fields use ``Field(..., description=...)``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.chat.tools.base import Tool
from app.services.dashboards.dashboard_read_service import DashboardReadService

_DEFAULT_METRICS = ["leads", "contracts", "revenue", "conversion_l_to_c"]


class PeriodInput(BaseModel):
    """A single date range used in ``compare_periods``."""

    date_from: date = Field(..., description="Start date (inclusive). Format: YYYY-MM-DD.")
    date_to: date = Field(..., description="End date (inclusive). Format: YYYY-MM-DD.")


class ComparePeriodsInput(BaseModel):
    """Input schema for ``compare_periods``."""

    period_a: PeriodInput = Field(..., description="The 'current' / newer period.")
    period_b: PeriodInput = Field(..., description="The 'baseline' / older period.")
    metrics: list[str] = Field(
        default_factory=lambda: list(_DEFAULT_METRICS),
        description=(
            "Metrics to compare. Supported: leads, contracts, revenue, "
            "visits, offers, conversion_l_to_v, conversion_l_to_c, conversion_o_to_c."
        ),
    )


def _extract_metric(dashboard: dict, metric: str) -> Decimal | None:
    """Pluck a single metric value out of the sales dashboard dict.

    Falls back across the known nested locations (kpi_cards, funnel,
    conversion_rates) so the caller doesn't need to know the response shape.
    """
    funnel = dashboard.get("funnel", {}) or {}
    kpi = dashboard.get("kpi_cards", {}) or {}
    rates = dashboard.get("conversion_rates", {}) or {}

    if metric == "leads":
        return _as_decimal(funnel.get("leads", kpi.get("leads_total")))
    if metric == "visits":
        return _as_decimal(funnel.get("visits", kpi.get("visits_count")))
    if metric == "offers":
        return _as_decimal(funnel.get("offers", kpi.get("offers_count")))
    if metric == "contracts":
        return _as_decimal(funnel.get("contracts", kpi.get("contracts_count")))
    if metric == "revenue":
        return _as_decimal(kpi.get("revenue"))
    if metric == "avg_deal_size":
        return _as_decimal(kpi.get("avg_deal_size"))
    if metric.startswith("conversion_"):
        # rates dict uses "l_to_c" without the "conversion_" prefix.
        rate_key = metric.removeprefix("conversion_")
        return _as_decimal(rates.get(rate_key))
    return None


def _as_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


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


def _pct_change(a: Decimal | None, b: Decimal | None) -> Decimal | None:
    """(a - b) / b * 100, rounded to 1 decimal. Returns None on zero guard."""
    if a is None or b is None or b == 0:
        return None
    return ((a - b) / b * Decimal("100")).quantize(Decimal("0.1"))


async def _handler(
    tenant_id: UUID,
    session: AsyncSession,
    inp: ComparePeriodsInput,
) -> dict:
    svc = DashboardReadService(session, tenant_id)
    dashboard_a = await svc.get_sales_dashboard(inp.period_a.date_from, inp.period_a.date_to)
    dashboard_b = await svc.get_sales_dashboard(inp.period_b.date_from, inp.period_b.date_to)

    deltas: dict[str, str | None] = {}
    for metric in inp.metrics:
        a_val = _extract_metric(dashboard_a, metric)
        b_val = _extract_metric(dashboard_b, metric)
        delta = _pct_change(a_val, b_val)
        deltas[metric] = str(delta) if delta is not None else None

    return {
        "period_a": _jsonable(dashboard_a),
        "period_b": _jsonable(dashboard_b),
        "deltas": deltas,
        "metrics": list(inp.metrics),
    }


TOOL = Tool(
    name="compare_periods",
    definition={
        "name": "compare_periods",
        "description": (
            "Compares KPIs between two date ranges and returns per-metric "
            "percent change ((A - B) / B * 100). Use for week-over-week, "
            "month-over-month, or arbitrary range comparisons. Returns null "
            "for any metric where the baseline value is zero."
        ),
        "input_schema": ComparePeriodsInput.model_json_schema(),
    },
    input_schema=ComparePeriodsInput,
    handler=_handler,
)
