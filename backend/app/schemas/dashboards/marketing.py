from __future__ import annotations

"""Pydantic v2 response schema for the Marketing Dashboard.

DATA-04: All Decimal fields use @field_serializer returning str | None.
MARK-03: ad_spend, cpl, cac, roas are always None — placeholder for Iteration 2.

Exports: MarketingDashboardResponse, LeadVolumeBySource, LeadVolumeBySourcePoint,
         JunkBySource
"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, field_serializer

from app.schemas.dashboards.sales import PeriodRange


class LeadVolumeBySourcePoint(BaseModel):
    """One data point in a source's lead volume time series (MARK-01)."""

    date: date
    leads: int | None


class LeadVolumeBySource(BaseModel):
    """Lead volume over time for a single source category (MARK-01)."""

    source: str
    total_leads: int | None
    series: list[LeadVolumeBySourcePoint]


class JunkBySource(BaseModel):
    """Junk lead percentage breakdown per source (MARK-04).

    DATA-04: junk_pct serialized as string.
    Exception: junk lead count comes from raw_mefi_leads directly (no pre-computed table).
    """

    source: str
    junk_count: int | None
    total_leads: int | None
    junk_pct: Decimal | None

    @field_serializer("junk_pct")
    def serialize_junk_pct(self, v: Decimal | None) -> str | None:
        return str(v) if v is not None else None


class MarketingDashboardResponse(BaseModel):
    """Top-level response schema for GET /api/v1/dashboards/marketing.

    MARK-03: ad_spend, cpl, cac, roas are always None (explicit null) — ad spend
             integration deferred to Iteration 2. Frontend should display
             "Coming in next update" for these fields.

    DATA-04 compliance: site_conversion_rate and junk_pct serialized as strings.
    """

    period: PeriodRange
    lead_volume_by_source: list[LeadVolumeBySource]
    site_conversion_rate: Decimal | None
    junk_by_source: list[JunkBySource]

    # MARK-03: explicit null placeholders — Iteration 2
    ad_spend: None = None
    cpl: None = None
    cac: None = None
    roas: None = None

    @field_serializer("site_conversion_rate")
    def serialize_site_conversion_rate(self, v: Decimal | None) -> str | None:
        return str(v) if v is not None else None
