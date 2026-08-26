"""Pydantic v2 response schema for the Sales Dashboard.

DATA-04: All Decimal fields use @field_serializer returning str | None to
         prevent float precision loss (NUMERIC(12,2) → "85000.00" string,
         not 85000.0 float).

Exports: SalesDashboardResponse, PeriodRange, FunnelCounts, ConversionRates,
         KpiCards, SourceBreakdownItem, RevenueSeries, StuckOffer
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class PeriodRange(BaseModel):
    """Date range for a dashboard query.

    Uses Field(alias=...) for "from"/"to" JSON keys since `from` is a Python keyword.
    populate_by_name=True allows construction with both Python names (from_date/to_date)
    and JSON aliases ("from"/"to").
    """

    model_config = ConfigDict(populate_by_name=True)

    from_date: date = Field(alias="from")
    to_date: date = Field(alias="to")


class FunnelCounts(BaseModel):
    """Aggregate funnel stage counts for the selected date range."""

    leads: int | None
    visits: int | None  # nullable — KI-03
    offers: int | None
    contracts: int | None


class ConversionRates(BaseModel):
    """Conversion rate ratios and WoW/MoM deltas for all funnel transitions.

    DATA-04: All Decimal | None fields serialized as str | None.
    """

    l_to_v: Decimal | None
    v_to_o: Decimal | None
    l_to_o: Decimal | None
    o_to_c: Decimal | None
    l_to_c: Decimal | None

    # WoW deltas (nullable — NULL when no prior-week data)
    l_to_v_wow_delta: Decimal | None
    v_to_o_wow_delta: Decimal | None
    l_to_o_wow_delta: Decimal | None
    o_to_c_wow_delta: Decimal | None
    l_to_c_wow_delta: Decimal | None

    # MoM deltas (nullable — NULL when no prior-month data)
    l_to_v_mom_delta: Decimal | None
    v_to_o_mom_delta: Decimal | None
    l_to_o_mom_delta: Decimal | None
    o_to_c_mom_delta: Decimal | None
    l_to_c_mom_delta: Decimal | None

    @field_serializer("l_to_v")
    def serialize_l_to_v(self, v: Decimal | None) -> str | None:
        return str(v) if v is not None else None

    @field_serializer("v_to_o")
    def serialize_v_to_o(self, v: Decimal | None) -> str | None:
        return str(v) if v is not None else None

    @field_serializer("l_to_o")
    def serialize_l_to_o(self, v: Decimal | None) -> str | None:
        return str(v) if v is not None else None

    @field_serializer("o_to_c")
    def serialize_o_to_c(self, v: Decimal | None) -> str | None:
        return str(v) if v is not None else None

    @field_serializer("l_to_c")
    def serialize_l_to_c(self, v: Decimal | None) -> str | None:
        return str(v) if v is not None else None

    @field_serializer("l_to_v_wow_delta")
    def serialize_l_to_v_wow_delta(self, v: Decimal | None) -> str | None:
        return str(v) if v is not None else None

    @field_serializer("v_to_o_wow_delta")
    def serialize_v_to_o_wow_delta(self, v: Decimal | None) -> str | None:
        return str(v) if v is not None else None

    @field_serializer("l_to_o_wow_delta")
    def serialize_l_to_o_wow_delta(self, v: Decimal | None) -> str | None:
        return str(v) if v is not None else None

    @field_serializer("o_to_c_wow_delta")
    def serialize_o_to_c_wow_delta(self, v: Decimal | None) -> str | None:
        return str(v) if v is not None else None

    @field_serializer("l_to_c_wow_delta")
    def serialize_l_to_c_wow_delta(self, v: Decimal | None) -> str | None:
        return str(v) if v is not None else None

    @field_serializer("l_to_v_mom_delta")
    def serialize_l_to_v_mom_delta(self, v: Decimal | None) -> str | None:
        return str(v) if v is not None else None

    @field_serializer("v_to_o_mom_delta")
    def serialize_v_to_o_mom_delta(self, v: Decimal | None) -> str | None:
        return str(v) if v is not None else None

    @field_serializer("l_to_o_mom_delta")
    def serialize_l_to_o_mom_delta(self, v: Decimal | None) -> str | None:
        return str(v) if v is not None else None

    @field_serializer("o_to_c_mom_delta")
    def serialize_o_to_c_mom_delta(self, v: Decimal | None) -> str | None:
        return str(v) if v is not None else None

    @field_serializer("l_to_c_mom_delta")
    def serialize_l_to_c_mom_delta(self, v: Decimal | None) -> str | None:
        return str(v) if v is not None else None


class KpiCards(BaseModel):
    """Top-level KPI cards shown on the Sales dashboard.

    DATA-04: Revenue and delta Decimal fields serialized as strings.
    """

    leads_total: int | None
    visits_count: int | None
    offers_count: int | None
    contracts_count: int | None
    revenue: Decimal | None
    avg_deal_size: Decimal | None
    revenue_wow_delta: Decimal | None
    revenue_mom_delta: Decimal | None
    leads_total_wow_delta: Decimal | None
    leads_total_mom_delta: Decimal | None

    @field_serializer("revenue")
    def serialize_revenue(self, v: Decimal | None) -> str | None:
        return str(v) if v is not None else None

    @field_serializer("avg_deal_size")
    def serialize_avg_deal_size(self, v: Decimal | None) -> str | None:
        return str(v) if v is not None else None

    @field_serializer("revenue_wow_delta")
    def serialize_revenue_wow_delta(self, v: Decimal | None) -> str | None:
        return str(v) if v is not None else None

    @field_serializer("revenue_mom_delta")
    def serialize_revenue_mom_delta(self, v: Decimal | None) -> str | None:
        return str(v) if v is not None else None

    @field_serializer("leads_total_wow_delta")
    def serialize_leads_total_wow_delta(self, v: Decimal | None) -> str | None:
        return str(v) if v is not None else None

    @field_serializer("leads_total_mom_delta")
    def serialize_leads_total_mom_delta(self, v: Decimal | None) -> str | None:
        return str(v) if v is not None else None


class SourceBreakdownItem(BaseModel):
    """One row in the lead source breakdown table (SALE-04).

    DATA-04: revenue and conversion_rate serialized as strings.
    """

    source: str
    leads: int | None
    visits: int | None
    offers: int | None
    deals_won: int | None
    revenue: Decimal | None
    conversion_rate: Decimal | None

    @field_serializer("revenue")
    def serialize_revenue(self, v: Decimal | None) -> str | None:
        return str(v) if v is not None else None

    @field_serializer("conversion_rate")
    def serialize_conversion_rate(self, v: Decimal | None) -> str | None:
        return str(v) if v is not None else None


class RevenueSeries(BaseModel):
    """One data point in the revenue time series (SALE-05).

    DATA-04: revenue serialized as string.
    """

    date: date
    revenue: Decimal | None

    @field_serializer("revenue")
    def serialize_revenue(self, v: Decimal | None) -> str | None:
        return str(v) if v is not None else None


class StuckOffer(BaseModel):
    """An offer that has been stuck with no activity for > 14 days (SALE-07)."""

    external_id: str
    days_stuck: int
    salesperson_name: str | None


class SalesDashboardResponse(BaseModel):
    """Top-level response schema for GET /api/v1/dashboards/sales.

    DATA-04 compliance: all Decimal | None fields serialized as str | None
    via field_serializer on each sub-schema.
    """

    period: PeriodRange
    funnel: FunnelCounts
    conversion_rates: ConversionRates
    kpi_cards: KpiCards
    source_breakdown: list[SourceBreakdownItem]
    revenue_series: list[RevenueSeries]
    stuck_offers: list[StuckOffer]
