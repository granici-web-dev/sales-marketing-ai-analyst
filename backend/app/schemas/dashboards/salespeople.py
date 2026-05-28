from __future__ import annotations

"""Pydantic v2 response schema for the Salespeople Dashboard.

DATA-04: All Decimal fields use @field_serializer returning str | None.

Exports: SalespeopleDashboardResponse, SalespersonRow
"""

from decimal import Decimal

from pydantic import BaseModel, field_serializer

from app.schemas.dashboards.sales import PeriodRange


class SalespersonRow(BaseModel):
    """One row in the salesperson leaderboard (SALES-01, SALES-02, SALES-03, SALES-04).

    DATA-04: All Decimal | None fields serialized as str | None.

    avg_time_to_first_touch_minutes: int | None — NULL when no mefi_lead_history
    rows exist for this salesperson's leads (KI-03 / D-05). Displayed as "N/A"
    in the frontend when None.
    """

    external_id: str
    name: str | None

    # Funnel counts (SALES-03)
    leads_assigned: int | None
    visits_conducted: int | None
    offers_sent: int | None
    deals_won: int | None

    # Revenue (DATA-04)
    revenue: Decimal | None
    avg_deal_size: Decimal | None

    # Win rate (DATA-04)
    win_rate: Decimal | None

    # Time to first touch in minutes (SALES-02); nullable when no history
    avg_time_to_first_touch_minutes: int | None

    # Data quality (SALES-04)
    data_completeness_pct: Decimal | None

    # Per-salesperson conversion rates
    conversion_l_to_v: Decimal | None
    conversion_v_to_o: Decimal | None
    conversion_o_to_c: Decimal | None
    conversion_l_to_c: Decimal | None

    @field_serializer("revenue")
    def serialize_revenue(self, v: Decimal | None) -> str | None:
        return str(v) if v is not None else None

    @field_serializer("avg_deal_size")
    def serialize_avg_deal_size(self, v: Decimal | None) -> str | None:
        return str(v) if v is not None else None

    @field_serializer("win_rate")
    def serialize_win_rate(self, v: Decimal | None) -> str | None:
        return str(v) if v is not None else None

    @field_serializer("data_completeness_pct")
    def serialize_data_completeness_pct(self, v: Decimal | None) -> str | None:
        return str(v) if v is not None else None

    @field_serializer("conversion_l_to_v")
    def serialize_conversion_l_to_v(self, v: Decimal | None) -> str | None:
        return str(v) if v is not None else None

    @field_serializer("conversion_v_to_o")
    def serialize_conversion_v_to_o(self, v: Decimal | None) -> str | None:
        return str(v) if v is not None else None

    @field_serializer("conversion_o_to_c")
    def serialize_conversion_o_to_c(self, v: Decimal | None) -> str | None:
        return str(v) if v is not None else None

    @field_serializer("conversion_l_to_c")
    def serialize_conversion_l_to_c(self, v: Decimal | None) -> str | None:
        return str(v) if v is not None else None


class SalespeopleDashboardResponse(BaseModel):
    """Top-level response schema for GET /api/v1/dashboards/salespeople.

    DATA-04 compliance: all Decimal | None fields in SalespersonRow serialized as strings.
    """

    period: PeriodRange
    salespeople: list[SalespersonRow]
