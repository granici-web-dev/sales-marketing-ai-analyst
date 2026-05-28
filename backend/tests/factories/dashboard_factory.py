from __future__ import annotations

"""DashboardFactory — builds valid response dicts for all 3 dashboards + health.

Plain class (not factory-boy) with class methods that return dict objects
matching the Pydantic response schema structures.

Used by unit tests to construct schema instances without a database connection.

Sofa Belle pilot reference values:
  - Revenue: 85,000 RON range (SPEC.md §3)
  - Salespeople: Raileanu Leon (external_id="7"), Roibu Valeria (external_id="9")
  - Sources: mail_fb_ig, showroom (telefon), site
"""

from datetime import date, datetime, timezone
from decimal import Decimal


class DashboardFactory:
    """Factory for building valid dashboard response dicts.

    All class methods return plain dicts that can be passed directly to
    the corresponding Pydantic response model constructors, e.g.:
        SalesDashboardResponse(**DashboardFactory.build_sales_response())
    """

    @classmethod
    def build_sales_response(
        cls,
        from_date: date = date(2026, 5, 1),
        to_date: date = date(2026, 5, 19),
    ) -> dict:
        """Return a dict matching SalesDashboardResponse structure.

        Uses representative Sofa Belle values: ~85,000 RON revenue,
        typical funnel ratios from SPEC.md verified data.
        """
        return {
            "period": {"from": str(from_date), "to": str(to_date)},
            "funnel": {
                "leads": 217,
                "visits": 62,
                "offers": 87,
                "contracts": 12,
            },
            "conversion_rates": {
                "l_to_v": Decimal("0.2857"),
                "v_to_o": Decimal("1.4032"),
                "l_to_o": Decimal("0.4009"),
                "o_to_c": Decimal("0.1379"),
                "l_to_c": Decimal("0.0553"),
                "l_to_v_wow_delta": Decimal("-0.0500"),
                "v_to_o_wow_delta": None,
                "l_to_o_wow_delta": None,
                "o_to_c_wow_delta": None,
                "l_to_c_wow_delta": Decimal("0.1000"),
                "l_to_v_mom_delta": None,
                "v_to_o_mom_delta": None,
                "l_to_o_mom_delta": None,
                "o_to_c_mom_delta": None,
                "l_to_c_mom_delta": None,
            },
            "kpi_cards": {
                "leads_total": 217,
                "visits_count": 62,
                "offers_count": 87,
                "contracts_count": 12,
                "revenue": Decimal("85000.00"),
                "avg_deal_size": Decimal("7083.33"),
                "revenue_wow_delta": Decimal("0.0500"),
                "revenue_mom_delta": None,
                "leads_total_wow_delta": Decimal("-0.0300"),
                "leads_total_mom_delta": None,
            },
            "source_breakdown": [
                {
                    "source": "showroom",
                    "leads": 62,
                    "visits": 62,
                    "offers": 30,
                    "deals_won": 8,
                    "revenue": Decimal("40000.00"),
                    "conversion_rate": Decimal("0.1290"),
                },
                {
                    "source": "mail_fb_ig",
                    "leads": 55,
                    "visits": None,
                    "offers": 20,
                    "deals_won": 3,
                    "revenue": Decimal("25000.00"),
                    "conversion_rate": Decimal("0.0545"),
                },
                {
                    "source": "site",
                    "leads": 30,
                    "visits": None,
                    "offers": 10,
                    "deals_won": 1,
                    "revenue": Decimal("20000.00"),
                    "conversion_rate": Decimal("0.0333"),
                },
            ],
            "revenue_series": [
                {"date": date(2026, 5, 1), "revenue": Decimal("4500.00")},
                {"date": date(2026, 5, 2), "revenue": Decimal("5200.00")},
                {"date": date(2026, 5, 3), "revenue": Decimal("0.00")},
                {"date": date(2026, 5, 4), "revenue": Decimal("6100.00")},
                {"date": date(2026, 5, 5), "revenue": Decimal("3800.00")},
            ],
            "stuck_offers": [],
        }

    @classmethod
    def build_salespeople_response(
        cls,
        from_date: date = date(2026, 5, 1),
        to_date: date = date(2026, 5, 19),
    ) -> dict:
        """Return a dict matching SalespeopleDashboardResponse structure.

        Two representative Sofa Belle salespeople with realistic KPI values.
        Raileanu Leon (external_id="7") and Roibu Valeria (external_id="9").
        """
        return {
            "period": {"from": str(from_date), "to": str(to_date)},
            "salespeople": [
                {
                    "external_id": "7",
                    "name": "Raileanu Leon",
                    "leads_assigned": 45,
                    "visits_conducted": 12,
                    "offers_sent": 20,
                    "deals_won": 8,
                    "revenue": Decimal("72000.00"),
                    "avg_deal_size": Decimal("9000.00"),
                    "win_rate": Decimal("0.1778"),
                    "avg_time_to_first_touch_minutes": 142,
                    "data_completeness_pct": Decimal("88.89"),
                    "conversion_l_to_v": Decimal("0.2667"),
                    "conversion_v_to_o": Decimal("1.6667"),
                    "conversion_o_to_c": Decimal("0.4000"),
                    "conversion_l_to_c": Decimal("0.1778"),
                },
                {
                    "external_id": "9",
                    "name": "Roibu Valeria",
                    "leads_assigned": 38,
                    "visits_conducted": 9,
                    "offers_sent": 15,
                    "deals_won": 4,
                    "revenue": Decimal("32000.00"),
                    "avg_deal_size": Decimal("8000.00"),
                    "win_rate": Decimal("0.1053"),
                    "avg_time_to_first_touch_minutes": None,
                    "data_completeness_pct": Decimal("75.00"),
                    "conversion_l_to_v": Decimal("0.2368"),
                    "conversion_v_to_o": Decimal("1.6667"),
                    "conversion_o_to_c": Decimal("0.2667"),
                    "conversion_l_to_c": Decimal("0.1053"),
                },
            ],
        }

    @classmethod
    def build_marketing_response(
        cls,
        from_date: date = date(2026, 5, 1),
        to_date: date = date(2026, 5, 19),
    ) -> dict:
        """Return a dict matching MarketingDashboardResponse structure.

        3 source entries for lead_volume_by_source, 2 junk_by_source entries,
        ad_spend=None (MARK-03 — Iteration 2 placeholder).
        """
        return {
            "period": {"from": str(from_date), "to": str(to_date)},
            "lead_volume_by_source": [
                {
                    "source": "mail_fb_ig",
                    "total_leads": 55,
                    "series": [
                        {"date": date(2026, 5, 1), "leads": 3},
                        {"date": date(2026, 5, 2), "leads": 4},
                        {"date": date(2026, 5, 3), "leads": 2},
                    ],
                },
                {
                    "source": "telefon",
                    "total_leads": 40,
                    "series": [
                        {"date": date(2026, 5, 1), "leads": 2},
                        {"date": date(2026, 5, 2), "leads": 3},
                        {"date": date(2026, 5, 3), "leads": 1},
                    ],
                },
                {
                    "source": "site",
                    "total_leads": 30,
                    "series": [
                        {"date": date(2026, 5, 1), "leads": 1},
                        {"date": date(2026, 5, 2), "leads": 2},
                        {"date": date(2026, 5, 3), "leads": 3},
                    ],
                },
            ],
            "site_conversion_rate": Decimal("0.0645"),
            "junk_by_source": [
                {
                    "source": "telefon",
                    "junk_count": 12,
                    "total_leads": 90,
                    "junk_pct": Decimal("0.1333"),
                },
                {
                    "source": "whatsapp",
                    "junk_count": 5,
                    "total_leads": 40,
                    "junk_pct": Decimal("0.1250"),
                },
            ],
            "ad_spend": None,
            "cpl": None,
            "cac": None,
            "roas": None,
        }

    @classmethod
    def build_health_response(cls, stale: bool = False) -> dict:
        """Return a dict matching HealthDataResponse structure.

        Args:
            stale: Whether the data freshness flag should be True.

        Returns:
            Dict with last_sync_at as ISO datetime string, last_pipeline_status,
            and stale flag.
        """
        return {
            "last_sync_at": datetime(2026, 5, 28, 3, 47, 12, tzinfo=timezone.utc),
            "last_pipeline_status": "success",
            "stale": stale,
        }
