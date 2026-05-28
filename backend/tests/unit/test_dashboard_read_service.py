from __future__ import annotations

"""Unit tests for DashboardReadService — RED-state contracts for Phase 6 Plan 02.

Tests mock AsyncSession — no live DB required.
Requirements: SALE-01..07, SALES-01..04, MARK-01..04

All tests will fail with ImportError until Plan 06-02 creates
app.services.dashboards.dashboard_read_service.DashboardReadService.
"""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
FROM_DATE = date(2026, 5, 1)
TO_DATE = date(2026, 5, 19)


def _make_service(mock_session=None):
    """Build DashboardReadService with mocked AsyncSession."""
    from app.services.dashboards.dashboard_read_service import DashboardReadService  # noqa: PLC0415

    session = mock_session or AsyncMock()
    return DashboardReadService(session, TENANT_ID), session


_SENTINEL = object()


def _mock_execute_result(rows=None, scalar=_SENTINEL, first=_SENTINEL):
    """Build a mock result for session.execute() calls."""
    result = MagicMock()
    if rows is not None:
        result.all.return_value = rows
    if scalar is not _SENTINEL:
        result.scalar_one_or_none.return_value = scalar
    if first is not _SENTINEL:
        result.first.return_value = first
    return result


class TestGetSalesDashboard:
    """Tests for DashboardReadService.get_sales_dashboard() — SALE-01..07."""

    @pytest.mark.asyncio
    async def test_get_sales_dashboard_aggregates_funnel(self) -> None:
        """get_sales_dashboard returns funnel.leads = SUM(leads_total) — SALE-01.

        Mock session returns aggregate row; assert funnel.leads is sum value.
        """
        session = AsyncMock()

        # Step 1: aggregate row (leads/visits/funnel)
        agg_row = MagicMock()
        agg_row.leads_total = 100
        agg_row.visits_count = 30
        agg_row.offers_count = 40
        agg_row.contracts_count = 10
        agg_row.revenue = Decimal("85000.00")
        agg_row.avg_deal_size = None  # computed in Python

        # Step 2: rates row (last-day rates)
        rates_row = MagicMock()
        rates_row.conversion_l_to_v = Decimal("0.3000")
        rates_row.conversion_v_to_o = Decimal("1.3333")
        rates_row.conversion_l_to_o = Decimal("0.4000")
        rates_row.conversion_o_to_c = Decimal("0.2500")
        rates_row.conversion_l_to_c = Decimal("0.1000")
        rates_row.leads_total_wow_delta = Decimal("0.1500")
        rates_row.leads_total_mom_delta = Decimal("0.2000")
        rates_row.conversion_l_to_v_wow_delta = None
        rates_row.conversion_l_to_v_mom_delta = None
        rates_row.conversion_v_to_o_wow_delta = None
        rates_row.conversion_v_to_o_mom_delta = None
        rates_row.conversion_l_to_o_wow_delta = None
        rates_row.conversion_l_to_o_mom_delta = None
        rates_row.conversion_o_to_c_wow_delta = None
        rates_row.conversion_o_to_c_mom_delta = None
        rates_row.conversion_l_to_c_wow_delta = None
        rates_row.conversion_l_to_c_mom_delta = None
        rates_row.revenue_wow_delta = None
        rates_row.revenue_mom_delta = None
        rates_row.avg_deal_size_wow_delta = None
        rates_row.avg_deal_size_mom_delta = None

        # Step 3: source breakdown rows
        src_row = MagicMock()
        src_row.source = "showroom"
        src_row.leads = 30
        src_row.visits = None
        src_row.offers = 10
        src_row.deals_won = 3
        src_row.revenue = Decimal("25500.00")
        src_row.conversion_rate = Decimal("0.1000")

        # Step 4: revenue time series rows
        ts_row = MagicMock()
        ts_row.date = date(2026, 5, 1)
        ts_row.revenue = Decimal("5000.00")

        # Step 5: stuck offers (empty)
        stuck_rows = []

        # session.execute side effects for sequential calls
        exec_results = [
            _mock_execute_result(first=agg_row),        # aggregate query
            _mock_execute_result(first=rates_row),       # last-day rates
            _mock_execute_result(rows=[src_row]),        # source breakdown
            _mock_execute_result(rows=[ts_row]),         # revenue time series
            _mock_execute_result(rows=stuck_rows),       # stuck offers
        ]
        session.execute = AsyncMock(side_effect=exec_results)

        svc, _ = _make_service(session)
        result = await svc.get_sales_dashboard(FROM_DATE, TO_DATE)

        assert result["funnel"]["leads"] == 100
        assert result["funnel"]["visits"] == 30
        assert result["funnel"]["offers"] == 40
        assert result["funnel"]["contracts"] == 10

    @pytest.mark.asyncio
    async def test_get_sales_dashboard_revenue_series_daily(self) -> None:
        """Revenue series has daily granularity — SALE-05 locked decision.

        One entry per day in the requested range.
        """
        session = AsyncMock()

        agg_row = MagicMock()
        agg_row.leads_total = 10
        agg_row.visits_count = None
        agg_row.offers_count = 5
        agg_row.contracts_count = 1
        agg_row.revenue = Decimal("15000.00")
        agg_row.avg_deal_size = None

        rates_row = MagicMock()
        rates_row.conversion_l_to_v = Decimal("0.4000")
        rates_row.conversion_v_to_o = Decimal("0.5000")
        rates_row.conversion_l_to_o = Decimal("0.2000")
        rates_row.conversion_o_to_c = Decimal("0.2500")
        rates_row.conversion_l_to_c = Decimal("0.0500")
        rates_row.leads_total_wow_delta = None
        rates_row.leads_total_mom_delta = None
        rates_row.conversion_l_to_v_wow_delta = None
        rates_row.conversion_l_to_v_mom_delta = None
        rates_row.conversion_v_to_o_wow_delta = None
        rates_row.conversion_v_to_o_mom_delta = None
        rates_row.conversion_l_to_o_wow_delta = None
        rates_row.conversion_l_to_o_mom_delta = None
        rates_row.conversion_o_to_c_wow_delta = None
        rates_row.conversion_o_to_c_mom_delta = None
        rates_row.conversion_l_to_c_wow_delta = None
        rates_row.conversion_l_to_c_mom_delta = None
        rates_row.revenue_wow_delta = None
        rates_row.revenue_mom_delta = None
        rates_row.avg_deal_size_wow_delta = None
        rates_row.avg_deal_size_mom_delta = None

        # 3 daily revenue points
        ts_rows = [
            MagicMock(date=date(2026, 5, 1), revenue=Decimal("5000.00")),
            MagicMock(date=date(2026, 5, 2), revenue=Decimal("4000.00")),
            MagicMock(date=date(2026, 5, 3), revenue=Decimal("6000.00")),
        ]

        exec_results = [
            _mock_execute_result(first=agg_row),
            _mock_execute_result(first=rates_row),
            _mock_execute_result(rows=[]),   # source breakdown empty
            _mock_execute_result(rows=ts_rows),
            _mock_execute_result(rows=[]),   # stuck offers empty
        ]
        session.execute = AsyncMock(side_effect=exec_results)

        svc, _ = _make_service(session)
        result = await svc.get_sales_dashboard(
            date(2026, 5, 1), date(2026, 5, 3)
        )

        # Assert daily granularity — 3 entries for 3-day range
        assert len(result["revenue_series"]) == 3
        assert result["revenue_series"][0]["date"] == date(2026, 5, 1)
        assert result["revenue_series"][0]["revenue"] == Decimal("5000.00")

    @pytest.mark.asyncio
    async def test_get_sales_dashboard_empty_range(self) -> None:
        """Empty DB result → zeros for counts, None for rates — SALE-01.

        When no rows exist for the range, funnel counts default to 0, rates to None.
        """
        session = AsyncMock()

        # All aggregate queries return None/empty
        agg_row = MagicMock()
        agg_row.leads_total = 0
        agg_row.visits_count = None
        agg_row.offers_count = 0
        agg_row.contracts_count = 0
        agg_row.revenue = None
        agg_row.avg_deal_size = None

        exec_results = [
            _mock_execute_result(first=agg_row),
            _mock_execute_result(first=None),   # no rates row
            _mock_execute_result(rows=[]),       # no source rows
            _mock_execute_result(rows=[]),       # no ts rows
            _mock_execute_result(rows=[]),       # no stuck offers
        ]
        session.execute = AsyncMock(side_effect=exec_results)

        svc, _ = _make_service(session)
        result = await svc.get_sales_dashboard(FROM_DATE, TO_DATE)

        assert result["funnel"]["leads"] == 0
        assert result["funnel"]["visits"] is None or result["funnel"]["visits"] == 0
        assert result["conversion_rates"]["l_to_v"] is None


class TestGetSalespeopleDashboard:
    """Tests for DashboardReadService.get_salespeople_dashboard() — SALES-01..04."""

    @pytest.mark.asyncio
    async def test_get_salespeople_dashboard_includes_name(self) -> None:
        """Dashboard includes salesperson name from mefi_salespeople JOIN — SALES-01.

        Mock join result includes salesperson name.
        """
        session = AsyncMock()

        sp_row = MagicMock()
        sp_row.salesperson_external_id = "7"
        sp_row.name = "Raileanu Leon"
        sp_row.leads_assigned = 45
        sp_row.visits_conducted = 12
        sp_row.offers_sent = 20
        sp_row.deals_won = 8
        sp_row.revenue = Decimal("72000.00")
        sp_row.avg_ttft = 142
        sp_row.data_completeness_pct = Decimal("88.89")
        sp_row.conversion_l_to_v = Decimal("0.2667")
        sp_row.conversion_v_to_o = Decimal("1.6667")
        sp_row.conversion_o_to_c = Decimal("0.4000")
        sp_row.conversion_l_to_c = Decimal("0.1778")

        session.execute = AsyncMock(
            return_value=_mock_execute_result(rows=[sp_row])
        )

        svc, _ = _make_service(session)
        result = await svc.get_salespeople_dashboard(FROM_DATE, TO_DATE)

        assert len(result["salespeople"]) == 1
        sp = result["salespeople"][0]
        assert sp["name"] == "Raileanu Leon"
        assert sp["external_id"] == "7"

    @pytest.mark.asyncio
    async def test_get_salespeople_dashboard_win_rate_computed(self) -> None:
        """win_rate = deals_won / leads_assigned computed in Python — SALES-01.

        8 / 45 ≈ 0.1778 computed in service layer from aggregated counts.
        """
        session = AsyncMock()

        sp_row = MagicMock()
        sp_row.salesperson_external_id = "7"
        sp_row.name = "Raileanu Leon"
        sp_row.leads_assigned = 45
        sp_row.visits_conducted = 12
        sp_row.offers_sent = 20
        sp_row.deals_won = 8
        sp_row.revenue = Decimal("72000.00")
        sp_row.avg_ttft = None
        sp_row.data_completeness_pct = Decimal("88.89")
        sp_row.conversion_l_to_v = Decimal("0.2667")
        sp_row.conversion_v_to_o = Decimal("1.6667")
        sp_row.conversion_o_to_c = Decimal("0.4000")
        sp_row.conversion_l_to_c = Decimal("0.1778")

        session.execute = AsyncMock(
            return_value=_mock_execute_result(rows=[sp_row])
        )

        svc, _ = _make_service(session)
        result = await svc.get_salespeople_dashboard(FROM_DATE, TO_DATE)

        sp = result["salespeople"][0]
        # 8 / 45 — computed in Python; allow small Decimal rounding
        assert sp["win_rate"] is not None
        assert abs(float(sp["win_rate"]) - 8 / 45) < 0.001


class TestGetMarketingDashboard:
    """Tests for DashboardReadService.get_marketing_dashboard() — MARK-01..04."""

    @pytest.mark.asyncio
    async def test_get_marketing_dashboard_ad_spend_null(self) -> None:
        """Returned dict.ad_spend is None — MARK-03 documented placeholder."""
        session = AsyncMock()

        # Marketing dashboard calls: lead_volume_by_source, site_conversion, junk_by_source
        exec_results = [
            _mock_execute_result(rows=[]),    # lead_volume_by_source time series
            _mock_execute_result(scalar=None),  # site_conversion_rate
            _mock_execute_result(rows=[]),    # junk query
            _mock_execute_result(rows=[]),    # total query
        ]
        session.execute = AsyncMock(side_effect=exec_results)

        svc, _ = _make_service(session)
        result = await svc.get_marketing_dashboard(FROM_DATE, TO_DATE)

        assert result["ad_spend"] is None
        assert result["cpl"] is None
        assert result["cac"] is None
        assert result["roas"] is None

    @pytest.mark.asyncio
    async def test_get_marketing_dashboard_site_conversion_rate(self) -> None:
        """Returns Decimal from SourceDailyKpi site rows — MARK-02."""
        session = AsyncMock()

        # site_conversion_rate result
        exec_results = [
            _mock_execute_result(rows=[]),                      # lead_volume_by_source
            _mock_execute_result(scalar=Decimal("0.0645")),     # site_conversion_rate
            _mock_execute_result(rows=[]),                      # junk query
            _mock_execute_result(rows=[]),                      # total query
        ]
        session.execute = AsyncMock(side_effect=exec_results)

        svc, _ = _make_service(session)
        result = await svc.get_marketing_dashboard(FROM_DATE, TO_DATE)

        assert result["site_conversion_rate"] == Decimal("0.0645")


class TestGetStuckOffers:
    """Tests for DashboardReadService.get_stuck_offers() — SALE-07."""

    @pytest.mark.asyncio
    async def test_get_stuck_offers_returns_list(self) -> None:
        """Mock text query returns stuck offer rows as list of dicts — SALE-07."""
        session = AsyncMock()

        # Mock stuck offers result row
        stuck_row = MagicMock()
        stuck_row.external_id = "1234"
        stuck_row.salesperson_name = "Roibu Valeria"
        stuck_row.days_stuck = 18.5

        session.execute = AsyncMock(
            return_value=_mock_execute_result(rows=[stuck_row])
        )

        svc, _ = _make_service(session)
        result = await svc.get_stuck_offers(FROM_DATE, TO_DATE)

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["external_id"] == "1234"
        assert result[0]["days_stuck"] == 18
        assert result[0]["salesperson_name"] == "Roibu Valeria"
