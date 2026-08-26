"""Unit tests for dashboard response schemas — DATA-04 Decimal serialization.

Verifies that all Decimal | None fields in dashboard schemas serialize as
JSON strings (not floats), per DATA-04 requirement.

T-06-01-03: field_serializer on every Decimal field returns str, preventing
            float precision loss.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal

from app.schemas.dashboards.marketing import JunkBySource, MarketingDashboardResponse
from app.schemas.dashboards.sales import (
    ConversionRates,
    FunnelCounts,
    KpiCards,
    PeriodRange,
    RevenueSeries,
    SalesDashboardResponse,
    SourceBreakdownItem,
    StuckOffer,
)
from app.schemas.dashboards.salespeople import SalespersonRow
from app.schemas.health import HealthDataResponse

# ── Helpers ───────────────────────────────────────────────────────────────────


def _period() -> PeriodRange:
    return PeriodRange(**{"from": date(2026, 5, 1), "to": date(2026, 5, 19)})


def _funnel() -> FunnelCounts:
    return FunnelCounts(leads=217, visits=62, offers=87, contracts=12)


def _conversion_rates() -> ConversionRates:
    return ConversionRates(
        l_to_v=Decimal("0.2857"),
        v_to_o=Decimal("1.4032"),
        l_to_o=Decimal("0.4009"),
        o_to_c=Decimal("0.1379"),
        l_to_c=Decimal("0.0553"),
        l_to_v_wow_delta=Decimal("-0.0500"),
        v_to_o_wow_delta=None,
        l_to_o_wow_delta=None,
        o_to_c_wow_delta=None,
        l_to_c_wow_delta=Decimal("0.1000"),
        l_to_v_mom_delta=None,
        v_to_o_mom_delta=None,
        l_to_o_mom_delta=None,
        o_to_c_mom_delta=None,
        l_to_c_mom_delta=None,
    )


def _kpi_cards() -> KpiCards:
    return KpiCards(
        leads_total=217,
        visits_count=62,
        offers_count=87,
        contracts_count=12,
        revenue=Decimal("85000.00"),
        avg_deal_size=Decimal("7083.33"),
        revenue_wow_delta=Decimal("0.0500"),
        revenue_mom_delta=None,
        leads_total_wow_delta=Decimal("-0.0300"),
        leads_total_mom_delta=None,
    )


def _sales_response() -> SalesDashboardResponse:
    return SalesDashboardResponse(
        period=_period(),
        funnel=_funnel(),
        conversion_rates=_conversion_rates(),
        kpi_cards=_kpi_cards(),
        source_breakdown=[
            SourceBreakdownItem(
                source="showroom",
                leads=62,
                visits=62,
                offers=30,
                deals_won=8,
                revenue=Decimal("40000.00"),
                conversion_rate=Decimal("0.1290"),
            )
        ],
        revenue_series=[
            RevenueSeries(date=date(2026, 5, 1), revenue=Decimal("85000.00"))
        ],
        stuck_offers=[],
    )


# ── DATA-04 Tests ─────────────────────────────────────────────────────────────


def test_decimal_revenue_serialized_as_string() -> None:
    """SalesDashboardResponse revenue serializes as JSON string, not float (DATA-04)."""
    model = _sales_response()
    json_str = model.model_dump_json()
    parsed = json.loads(json_str)

    # revenue in kpi_cards must be a string
    revenue_val = parsed["kpi_cards"]["revenue"]
    assert isinstance(revenue_val, str), f"Expected str, got {type(revenue_val)}: {revenue_val!r}"
    assert revenue_val == "85000.00", f"Expected '85000.00', got {revenue_val!r}"


def test_decimal_conversion_rate_serialized_as_string() -> None:
    """ConversionRates.l_to_v serializes as string, not float (DATA-04)."""
    model = _sales_response()
    json_str = model.model_dump_json()
    parsed = json.loads(json_str)

    l_to_v = parsed["conversion_rates"]["l_to_v"]
    assert isinstance(l_to_v, str), f"Expected str, got {type(l_to_v)}: {l_to_v!r}"
    assert l_to_v == "0.2857"


def test_revenue_series_decimal_serialized_as_string() -> None:
    """RevenueSeries.revenue serializes as string (DATA-04)."""
    series = RevenueSeries(date=date(2026, 5, 1), revenue=Decimal("85000.00"))
    parsed = json.loads(series.model_dump_json())
    assert isinstance(parsed["revenue"], str)
    assert parsed["revenue"] == "85000.00"


def test_salesperson_row_decimal_as_string() -> None:
    """SalespersonRow.revenue serializes as string (DATA-04)."""
    row = SalespersonRow(
        external_id="7",
        name="Raileanu Leon",
        leads_assigned=45,
        visits_conducted=12,
        offers_sent=20,
        deals_won=8,
        revenue=Decimal("72000.00"),
        avg_deal_size=Decimal("9000.00"),
        win_rate=Decimal("0.1778"),
        avg_time_to_first_touch_minutes=142,
        data_completeness_pct=Decimal("88.89"),
        conversion_l_to_v=Decimal("0.2667"),
        conversion_v_to_o=Decimal("1.6667"),
        conversion_o_to_c=Decimal("0.4000"),
        conversion_l_to_c=Decimal("0.1778"),
    )
    parsed = json.loads(row.model_dump_json())
    assert isinstance(parsed["revenue"], str), f"revenue should be str: {parsed['revenue']!r}"
    assert parsed["revenue"] == "72000.00"


def test_marketing_ad_spend_is_null() -> None:
    """MarketingDashboardResponse.ad_spend is always None (MARK-03)."""
    from app.schemas.dashboards.marketing import LeadVolumeBySource

    model = MarketingDashboardResponse(
        period=_period(),
        lead_volume_by_source=[
            LeadVolumeBySource(source="mail_fb_ig", total_leads=55, series=[])
        ],
        site_conversion_rate=Decimal("0.0645"),
        junk_by_source=[],
    )
    assert model.ad_spend is None
    assert model.cpl is None
    assert model.cac is None
    assert model.roas is None

    # Also verify in JSON output
    parsed = json.loads(model.model_dump_json())
    assert parsed["ad_spend"] is None
    assert parsed["cpl"] is None


def test_junk_pct_decimal_as_string() -> None:
    """JunkBySource.junk_pct serializes as string (DATA-04)."""
    junk = JunkBySource(
        source="telefon",
        junk_count=12,
        total_leads=90,
        junk_pct=Decimal("0.1333"),
    )
    parsed = json.loads(junk.model_dump_json())
    assert isinstance(parsed["junk_pct"], str), f"junk_pct should be str: {parsed['junk_pct']!r}"
    assert parsed["junk_pct"] == "0.1333"


def test_health_data_response_stale_flag() -> None:
    """HealthDataResponse.stale=True validates and round-trips correctly."""
    health = HealthDataResponse(
        last_sync_at=datetime(2026, 5, 28, 3, 47, 12, tzinfo=UTC),
        last_pipeline_status="success",
        stale=True,
    )
    assert health.stale is True

    parsed = json.loads(health.model_dump_json())
    assert parsed["stale"] is True
    assert parsed["last_pipeline_status"] == "success"


def test_health_data_response_nullable_fields() -> None:
    """HealthDataResponse with None fields validates correctly."""
    health = HealthDataResponse(
        last_sync_at=None,
        last_pipeline_status=None,
        stale=True,
    )
    assert health.last_sync_at is None
    assert health.stale is True


def test_stuck_offer_schema() -> None:
    """StuckOffer fields validate correctly including nullable salesperson_name."""
    offer = StuckOffer(
        external_id="lead-123",
        days_stuck=21,
        salesperson_name="Raileanu Leon",
    )
    assert offer.external_id == "lead-123"
    assert offer.days_stuck == 21
    assert offer.salesperson_name == "Raileanu Leon"

    # nullable salesperson_name
    offer_no_sp = StuckOffer(
        external_id="lead-456",
        days_stuck=15,
        salesperson_name=None,
    )
    assert offer_no_sp.salesperson_name is None


def test_salesperson_row_ttft_nullable() -> None:
    """SalespersonRow with avg_time_to_first_touch_minutes=None validates (D-05)."""
    row = SalespersonRow(
        external_id="9",
        name="Roibu Valeria",
        leads_assigned=38,
        visits_conducted=9,
        offers_sent=15,
        deals_won=4,
        revenue=Decimal("32000.00"),
        avg_deal_size=Decimal("8000.00"),
        win_rate=Decimal("0.1053"),
        avg_time_to_first_touch_minutes=None,  # nullable — D-05
        data_completeness_pct=Decimal("75.00"),
        conversion_l_to_v=Decimal("0.2368"),
        conversion_v_to_o=Decimal("1.6667"),
        conversion_o_to_c=Decimal("0.2667"),
        conversion_l_to_c=Decimal("0.1053"),
    )
    assert row.avg_time_to_first_touch_minutes is None

    parsed = json.loads(row.model_dump_json())
    assert parsed["avg_time_to_first_touch_minutes"] is None


def test_site_conversion_rate_decimal_as_string() -> None:
    """MarketingDashboardResponse.site_conversion_rate serializes as string (DATA-04)."""
    from app.schemas.dashboards.marketing import LeadVolumeBySource

    model = MarketingDashboardResponse(
        period=_period(),
        lead_volume_by_source=[
            LeadVolumeBySource(source="site", total_leads=30, series=[])
        ],
        site_conversion_rate=Decimal("0.0645"),
        junk_by_source=[],
    )
    parsed = json.loads(model.model_dump_json())
    assert isinstance(parsed["site_conversion_rate"], str)
    assert parsed["site_conversion_rate"] == "0.0645"
