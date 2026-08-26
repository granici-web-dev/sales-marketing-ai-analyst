"""Dashboard read service — assembles pre-computed metrics for FastAPI routers.

Queries daily_kpi, salesperson_daily_kpi, source_daily_kpi, and raw_mefi_leads
(documented exception) to produce response dicts for the three dashboard endpoints
and the stuck-offers widget.

Phase 6 Plan 02 — read service layer for dashboard routers in Plan 03.

Security:
  T-06-02-01: All ORM queries include .where(Model.tenant_id == self._tenant_id)
  T-06-02-02: text() queries bind :tid parameter explicitly (MARK-04 exception)
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy import Integer as SAInteger
from sqlalchemy import and_, cast, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mefi import MefiSalesperson
from app.models.metrics.daily_kpi import DailyKpi
from app.models.metrics.salesperson_kpi import SalespersonDailyKpi
from app.models.metrics.source_kpi import SourceDailyKpi

logger = structlog.get_logger(__name__)

# MEFI source_id → source category name mapping (canonical 11-category).
# Mirrors app/services/metrics/source_kpi_service.py so Marketing junk-by-source
# uses the same buckets as Sales source breakdown. Source IDs verified from
# 1219 ingested leads (2026-05-28). Unmapped IDs fall back to "other".
MEFI_SOURCE_ID_TO_NAME: dict[int, str] = {
    5: "showroom",  # Walk-in to physical showroom — "Vizita" in client Excel
    11: "mail",  # Email leads
    10: "telefon",  # Inbound phone calls
    9: "whatsapp",  # WhatsApp Business
    6: "site",  # Website contact forms
    2: "meta",  # Facebook/Instagram paid ads
    3: "recomandare",  # Word-of-mouth referrals
    12: "colaborare",  # Partner/collaboration
    7: "arhitect",  # Interior architect referrals
    13: "client_fidel",  # Repeat customers
}


class DashboardReadService:
    """Read-only service that assembles dashboard response dicts from pre-computed tables.

    All methods are async and filter by tenant_id (T-06-02-01).
    No INSERT/UPDATE — read-only service.

    Usage:
        svc = DashboardReadService(session, tenant_id)
        data = await svc.get_sales_dashboard(from_date, to_date)
    """

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def get_sales_dashboard(self, from_date: date, to_date: date) -> dict:
        """Assemble sales dashboard data for the given date range.

        Queries:
          1. Aggregate daily_kpi for funnel + revenue totals
          2. Last-day rates and WoW/MoM deltas from daily_kpi
          3. Source breakdown from source_daily_kpi
          4. Revenue time series (always daily granularity — SALE-05 locked decision)
          5. Stuck offers from v_mefi_leads_active + mefi_lead_history

        Args:
            from_date: Start of date range (inclusive).
            to_date: End of date range (inclusive).

        Returns:
            Dict matching SalesDashboardResponse structure.
        """
        log = logger.bind(
            tenant_id=str(self._tenant_id),
            from_date=str(from_date),
            to_date=str(to_date),
        )
        log.info("dashboard.sales.start")

        # ── Step 1: Aggregate daily_kpi for funnel counts and revenue ─────────
        stmt_agg = select(
            func.coalesce(func.sum(DailyKpi.leads_total), 0).label("leads_total"),
            func.sum(DailyKpi.visits_count).label("visits_count"),  # keep NULL — KI-03
            func.coalesce(func.sum(DailyKpi.offers_count), 0).label("offers_count"),
            func.coalesce(func.sum(DailyKpi.contracts_count), 0).label("contracts_count"),
            func.sum(DailyKpi.revenue).label("revenue"),
        ).where(
            DailyKpi.tenant_id == self._tenant_id,
            DailyKpi.date >= from_date,
            DailyKpi.date <= to_date,
        )
        agg_result = await self._session.execute(stmt_agg)
        agg = agg_result.first()

        leads_total = int(agg.leads_total) if agg and agg.leads_total is not None else 0
        visits_count = int(agg.visits_count) if agg and agg.visits_count is not None else None
        offers_count = int(agg.offers_count) if agg and agg.offers_count is not None else 0
        contracts_count = int(agg.contracts_count) if agg and agg.contracts_count is not None else 0
        revenue: Decimal | None = (
            Decimal(str(agg.revenue)) if agg and agg.revenue is not None else None
        )
        # avg_deal_size for range = total revenue / total contracts (D-16)
        avg_deal_size: Decimal | None = None
        if revenue is not None and contracts_count > 0:
            avg_deal_size = revenue / Decimal(str(contracts_count))

        # Period funnel ratios — recompute from SUMMED counts over the range
        # (Phase 3 hotfix 2026-05-30). Contracts are event-based (signed in period)
        # while leads/visits/offers are creation-cohort; the period ratio
        # contracts_signed_in_period / leads_created_in_period is the funnel ratio
        # the CEO/MEFI compare against — NOT the last-day stored rate, and NOT an
        # average of noisy daily rates. NULLIF zero-division guard via _ratio.
        def _ratio(num: int | None, den: int | None) -> Decimal | None:
            if num is None or not den:  # den None or 0 → None
                return None
            return Decimal(str(num)) / Decimal(str(den))

        period_l_to_v = _ratio(visits_count, leads_total)
        period_v_to_o = _ratio(offers_count, visits_count)
        period_l_to_o = _ratio(offers_count, leads_total)
        period_o_to_c = _ratio(contracts_count, offers_count)
        period_l_to_c = _ratio(contracts_count, leads_total)

        # ── Step 2: Last-day rates and deltas (last row in range DESC) ────────
        stmt_rates = (
            select(
                DailyKpi.conversion_l_to_v,
                DailyKpi.conversion_v_to_o,
                DailyKpi.conversion_l_to_o,
                DailyKpi.conversion_o_to_c,
                DailyKpi.conversion_l_to_c,
                DailyKpi.leads_total_wow_delta,
                DailyKpi.leads_total_mom_delta,
                DailyKpi.conversion_l_to_v_wow_delta,
                DailyKpi.conversion_l_to_v_mom_delta,
                DailyKpi.conversion_v_to_o_wow_delta,
                DailyKpi.conversion_v_to_o_mom_delta,
                DailyKpi.conversion_l_to_o_wow_delta,
                DailyKpi.conversion_l_to_o_mom_delta,
                DailyKpi.conversion_o_to_c_wow_delta,
                DailyKpi.conversion_o_to_c_mom_delta,
                DailyKpi.conversion_l_to_c_wow_delta,
                DailyKpi.conversion_l_to_c_mom_delta,
                DailyKpi.revenue_wow_delta,
                DailyKpi.revenue_mom_delta,
                DailyKpi.avg_deal_size_wow_delta,
                DailyKpi.avg_deal_size_mom_delta,
            )
            .where(
                DailyKpi.tenant_id == self._tenant_id,
                DailyKpi.date >= from_date,
                DailyKpi.date <= to_date,
            )
            .order_by(DailyKpi.date.desc())
            .limit(1)
        )
        rates_result = await self._session.execute(stmt_rates)
        rates_row = rates_result.first()

        def _dec(row: object | None, attr: str) -> Decimal | None:
            """Safely extract Decimal attribute from row."""
            if row is None:
                return None
            val = getattr(row, attr, None)
            return Decimal(str(val)) if val is not None else None

        # ── Step 3: Source breakdown from source_daily_kpi ────────────────────
        stmt_src = (
            select(
                SourceDailyKpi.source,
                func.coalesce(func.sum(SourceDailyKpi.leads), 0).label("leads"),
                func.sum(SourceDailyKpi.visits).label("visits"),
                func.coalesce(func.sum(SourceDailyKpi.offers), 0).label("offers"),
                func.coalesce(func.sum(SourceDailyKpi.deals_won), 0).label("deals_won"),
                func.sum(SourceDailyKpi.revenue).label("revenue"),
                # conversion_rate recomputed from summed counts below (hotfix 2026-05-30) —
                # NOT averaged daily rates (deals_won is event-based; leads is cohort).
            )
            .where(
                SourceDailyKpi.tenant_id == self._tenant_id,
                SourceDailyKpi.date >= from_date,
                SourceDailyKpi.date <= to_date,
            )
            .group_by(SourceDailyKpi.source)
        )
        src_result = await self._session.execute(stmt_src)
        src_rows = src_result.all()

        def _src_rate(deals_won: int, leads: int) -> Decimal | None:
            if not leads:
                return None
            return Decimal(str(deals_won)) / Decimal(str(leads))

        source_breakdown = []
        for r in src_rows:
            src_leads = int(r.leads) if r.leads is not None else 0
            src_deals_won = int(r.deals_won) if r.deals_won is not None else 0
            source_breakdown.append(
                {
                    "source": r.source,
                    "leads": src_leads,
                    "visits": int(r.visits) if r.visits is not None else None,
                    "offers": int(r.offers) if r.offers is not None else 0,
                    "deals_won": src_deals_won,
                    "revenue": Decimal(str(r.revenue)) if r.revenue is not None else None,
                    "conversion_rate": _src_rate(src_deals_won, src_leads),
                }
            )

        # ── Step 4: Revenue time series — always daily granularity (SALE-05) ─
        stmt_ts = (
            select(DailyKpi.date, DailyKpi.revenue)
            .where(
                DailyKpi.tenant_id == self._tenant_id,
                DailyKpi.date >= from_date,
                DailyKpi.date <= to_date,
            )
            .order_by(DailyKpi.date.asc())
        )
        ts_result = await self._session.execute(stmt_ts)
        ts_rows = ts_result.all()

        revenue_series = [
            {
                "date": r.date,
                "revenue": Decimal(str(r.revenue)) if r.revenue is not None else None,
            }
            for r in ts_rows
        ]

        # ── Step 5: Stuck offers ──────────────────────────────────────────────
        stuck_offers = await self.get_stuck_offers(from_date, to_date)

        log.info("dashboard.sales.done", leads_total=leads_total)

        return {
            "period": {"from": from_date, "to": to_date},
            "funnel": {
                "leads": leads_total,
                "visits": visits_count,
                "offers": offers_count,
                "contracts": contracts_count,
            },
            "conversion_rates": {
                # Period funnel ratios recomputed from summed counts (hotfix 2026-05-30).
                "l_to_v": period_l_to_v,
                "v_to_o": period_v_to_o,
                "l_to_o": period_l_to_o,
                "o_to_c": period_o_to_c,
                "l_to_c": period_l_to_c,
                "l_to_v_wow_delta": _dec(rates_row, "conversion_l_to_v_wow_delta"),
                "l_to_v_mom_delta": _dec(rates_row, "conversion_l_to_v_mom_delta"),
                "v_to_o_wow_delta": _dec(rates_row, "conversion_v_to_o_wow_delta"),
                "v_to_o_mom_delta": _dec(rates_row, "conversion_v_to_o_mom_delta"),
                "l_to_o_wow_delta": _dec(rates_row, "conversion_l_to_o_wow_delta"),
                "l_to_o_mom_delta": _dec(rates_row, "conversion_l_to_o_mom_delta"),
                "o_to_c_wow_delta": _dec(rates_row, "conversion_o_to_c_wow_delta"),
                "o_to_c_mom_delta": _dec(rates_row, "conversion_o_to_c_mom_delta"),
                "l_to_c_wow_delta": _dec(rates_row, "conversion_l_to_c_wow_delta"),
                "l_to_c_mom_delta": _dec(rates_row, "conversion_l_to_c_mom_delta"),
                "leads_total_wow_delta": _dec(rates_row, "leads_total_wow_delta"),
                "leads_total_mom_delta": _dec(rates_row, "leads_total_mom_delta"),
                "revenue_wow_delta": _dec(rates_row, "revenue_wow_delta"),
                "revenue_mom_delta": _dec(rates_row, "revenue_mom_delta"),
                "avg_deal_size_wow_delta": _dec(rates_row, "avg_deal_size_wow_delta"),
                "avg_deal_size_mom_delta": _dec(rates_row, "avg_deal_size_mom_delta"),
            },
            "kpi_cards": {
                "leads_total": leads_total,
                "visits_count": visits_count,
                "offers_count": offers_count,
                "contracts_count": contracts_count,
                "revenue": revenue,
                "avg_deal_size": avg_deal_size,
                "revenue_wow_delta": _dec(rates_row, "revenue_wow_delta"),
                "revenue_mom_delta": _dec(rates_row, "revenue_mom_delta"),
                "leads_total_wow_delta": _dec(rates_row, "leads_total_wow_delta"),
                "leads_total_mom_delta": _dec(rates_row, "leads_total_mom_delta"),
                "avg_deal_size_wow_delta": _dec(rates_row, "avg_deal_size_wow_delta"),
                "avg_deal_size_mom_delta": _dec(rates_row, "avg_deal_size_mom_delta"),
            },
            "source_breakdown": source_breakdown,
            "revenue_series": revenue_series,
            "stuck_offers": stuck_offers,
        }

    async def get_salespeople_dashboard(self, from_date: date, to_date: date) -> dict:
        """Assemble salespeople dashboard for the given date range.

        Aggregates SalespersonDailyKpi per salesperson over the range, JOIN with
        MefiSalesperson for human-readable names. win_rate computed in Python.

        Args:
            from_date: Start of date range (inclusive).
            to_date: End of date range (inclusive).

        Returns:
            Dict with salespeople list matching SalespeopleDashboardResponse.
        """
        log = logger.bind(tenant_id=str(self._tenant_id))
        log.info("dashboard.salespeople.start")

        stmt = (
            select(
                SalespersonDailyKpi.salesperson_external_id,
                MefiSalesperson.name,
                func.coalesce(func.sum(SalespersonDailyKpi.leads_assigned), 0).label(
                    "leads_assigned"
                ),
                func.coalesce(func.sum(SalespersonDailyKpi.visits_conducted), 0).label(
                    "visits_conducted"
                ),
                func.coalesce(func.sum(SalespersonDailyKpi.offers_sent), 0).label("offers_sent"),
                func.coalesce(func.sum(SalespersonDailyKpi.deals_won), 0).label("deals_won"),
                func.sum(SalespersonDailyKpi.revenue).label("revenue"),
                func.avg(SalespersonDailyKpi.avg_time_to_first_touch_minutes).label("avg_ttft"),
                func.avg(SalespersonDailyKpi.data_completeness_pct).label("data_completeness_pct"),
                # Conversion rates recomputed from SUMMED counts below (hotfix 2026-05-30) —
                # NOT averaged daily rates (which mix event-based deals_won with cohort
                # denominators and are noisy). deals_won is event-based (signed in period).
            )
            .outerjoin(
                MefiSalesperson,
                and_(
                    MefiSalesperson.tenant_id == SalespersonDailyKpi.tenant_id,
                    cast(SalespersonDailyKpi.salesperson_external_id, SAInteger)
                    == MefiSalesperson.external_id,
                ),
            )
            .where(
                SalespersonDailyKpi.tenant_id == self._tenant_id,
                SalespersonDailyKpi.date >= from_date,
                SalespersonDailyKpi.date <= to_date,
            )
            .group_by(SalespersonDailyKpi.salesperson_external_id, MefiSalesperson.name)
        )

        result = await self._session.execute(stmt)
        rows = result.all()

        salespeople = []
        for r in rows:
            leads_assigned = int(r.leads_assigned) if r.leads_assigned is not None else 0
            deals_won = int(r.deals_won) if r.deals_won is not None else 0
            visits_conducted = int(r.visits_conducted) if r.visits_conducted is not None else 0
            offers_sent = int(r.offers_sent) if r.offers_sent is not None else 0
            revenue = Decimal(str(r.revenue)) if r.revenue is not None else None

            # win_rate = deals_won / leads_assigned (Python — T-06-02-03)
            win_rate: Decimal | None = None
            if leads_assigned > 0:
                win_rate = Decimal(str(deals_won)) / Decimal(str(leads_assigned))

            # Period funnel ratios from SUMMED counts (hotfix 2026-05-30) — NULLIF guard.
            def _ratio(num: int, den: int) -> Decimal | None:
                if not den:
                    return None
                return Decimal(str(num)) / Decimal(str(den))

            sp_conversion_l_to_v = _ratio(visits_conducted, leads_assigned)
            sp_conversion_v_to_o = _ratio(offers_sent, visits_conducted)
            sp_conversion_o_to_c = _ratio(deals_won, offers_sent)
            sp_conversion_l_to_c = _ratio(deals_won, leads_assigned)

            # avg_deal_size for range (Python)
            avg_deal_size: Decimal | None = None
            if revenue is not None and deals_won > 0:
                avg_deal_size = revenue / Decimal(str(deals_won))

            salespeople.append(
                {
                    "external_id": r.salesperson_external_id,
                    "name": r.name,
                    "leads_assigned": leads_assigned,
                    "visits_conducted": visits_conducted,
                    "offers_sent": offers_sent,
                    "deals_won": deals_won,
                    "revenue": revenue,
                    "win_rate": win_rate,
                    "avg_deal_size": avg_deal_size,
                    "avg_time_to_first_touch_minutes": (
                        int(r.avg_ttft) if r.avg_ttft is not None else None
                    ),
                    "data_completeness_pct": (
                        Decimal(str(r.data_completeness_pct))
                        if r.data_completeness_pct is not None
                        else None
                    ),
                    "conversion_l_to_v": sp_conversion_l_to_v,
                    "conversion_v_to_o": sp_conversion_v_to_o,
                    "conversion_o_to_c": sp_conversion_o_to_c,
                    "conversion_l_to_c": sp_conversion_l_to_c,
                }
            )

        log.info("dashboard.salespeople.done", count=len(salespeople))
        return {
            "period": {"from": from_date, "to": to_date},
            "salespeople": salespeople,
        }

    async def get_marketing_dashboard(self, from_date: date, to_date: date) -> dict:
        """Assemble marketing dashboard for the given date range.

        Returns lead volume by source time series, site conversion rate, junk by source,
        and placeholder null fields for ad spend metrics (MARK-03).

        MARK-04 documented exception: raw_mefi_leads queried directly via text() SQL;
        no pre-computed junk-by-source view exists. tenant_id bound explicitly (T-06-02-02).

        Args:
            from_date: Start of date range (inclusive).
            to_date: End of date range (inclusive).

        Returns:
            Dict matching MarketingDashboardResponse structure.
        """
        log = logger.bind(tenant_id=str(self._tenant_id))
        log.info("dashboard.marketing.start")

        # ── Step 1: Lead volume by source time series (MARK-01) ──────────────
        stmt_vol = (
            select(
                SourceDailyKpi.source,
                SourceDailyKpi.date,
                SourceDailyKpi.leads,
            )
            .where(
                SourceDailyKpi.tenant_id == self._tenant_id,
                SourceDailyKpi.date >= from_date,
                SourceDailyKpi.date <= to_date,
            )
            .order_by(SourceDailyKpi.source, SourceDailyKpi.date.asc())
        )
        vol_result = await self._session.execute(stmt_vol)
        vol_rows = vol_result.all()

        # Group by source → {source: [{date, leads}]} (Python grouping)
        vol_by_source: dict[str, list[dict]] = {}
        for r in vol_rows:
            src = r.source
            if src not in vol_by_source:
                vol_by_source[src] = []
            vol_by_source[src].append(
                {
                    "date": r.date,
                    "leads": int(r.leads) if r.leads is not None else 0,
                }
            )

        lead_volume_by_source = [
            {
                "source": src,
                "series": series,
                "total_leads": sum(point["leads"] for point in series),
            }
            for src, series in vol_by_source.items()
        ]

        # ── Step 2: Site conversion rate (MARK-02) ────────────────────────────
        # Period ratio = SUM(deals_won) / SUM(leads) over the range (hotfix 2026-05-30)
        # — NOT the average of daily rates (deals_won is event-based, leads cohort).
        stmt_site = select(
            func.coalesce(func.sum(SourceDailyKpi.deals_won), 0).label("deals_won"),
            func.coalesce(func.sum(SourceDailyKpi.leads), 0).label("leads"),
        ).where(
            SourceDailyKpi.tenant_id == self._tenant_id,
            SourceDailyKpi.source == "site",
            SourceDailyKpi.date >= from_date,
            SourceDailyKpi.date <= to_date,
        )
        site_result = await self._session.execute(stmt_site)
        site_row = site_result.first()
        site_conversion_rate: Decimal | None = None
        if site_row and site_row.leads:
            site_conversion_rate = Decimal(str(site_row.deals_won)) / Decimal(str(site_row.leads))

        # ── Step 3: Junk by source (MARK-04 documented exception) ────────────
        # MARK-04 documented exception: raw_mefi_leads queried directly; no pre-computed
        # junk-by-source view exists. text() query binds tenant_id explicitly (T-06-02-02,
        # Pitfall 5: with_loader_criteria does NOT fire on text() queries).
        junk_sql = text("""
            SELECT source_id, COUNT(*) as junk_count
            FROM raw_mefi_leads
            WHERE tenant_id = :tid
              AND lifecycle = 'junk'
              AND created_at_source >= :from_d
              AND created_at_source < :to_d_plus1
            GROUP BY source_id
        """)
        total_sql = text("""
            SELECT source_id, COUNT(*) as total
            FROM raw_mefi_leads
            WHERE tenant_id = :tid
              AND created_at_source >= :from_d
              AND created_at_source < :to_d_plus1
            GROUP BY source_id
        """)
        tid_str = str(self._tenant_id)
        to_d_plus1 = to_date + timedelta(days=1)

        junk_result = await self._session.execute(
            junk_sql,
            {"tid": tid_str, "from_d": from_date, "to_d_plus1": to_d_plus1},
        )
        total_result = await self._session.execute(
            total_sql,
            {"tid": tid_str, "from_d": from_date, "to_d_plus1": to_d_plus1},
        )

        # Aggregate raw source_id rows by canonical category so each category
        # appears once (e.g. multiple unmapped IDs all collapse to "other").
        junk_by_category: dict[str, int] = {}
        total_by_category: dict[str, int] = {}
        for r in junk_result.all():
            category = MEFI_SOURCE_ID_TO_NAME.get(r.source_id, "other")
            junk_by_category[category] = junk_by_category.get(category, 0) + int(r.junk_count)
        for r in total_result.all():
            category = MEFI_SOURCE_ID_TO_NAME.get(r.source_id, "other")
            total_by_category[category] = total_by_category.get(category, 0) + int(r.total)

        junk_by_source: list[dict] = []
        all_categories = sorted(set(junk_by_category.keys()) | set(total_by_category.keys()))
        for category in all_categories:
            junk_count = junk_by_category.get(category, 0)
            total = total_by_category.get(category, 0)
            junk_pct: Decimal | None = None
            if total > 0:
                junk_pct = Decimal(str(junk_count)) / Decimal(str(total))
            junk_by_source.append(
                {
                    "source": category,
                    "junk_count": junk_count,
                    "total_leads": total,
                    "junk_pct": junk_pct,
                }
            )

        log.info("dashboard.marketing.done")

        return {
            "period": {"from": from_date, "to": to_date},
            "lead_volume_by_source": lead_volume_by_source,
            "site_conversion_rate": site_conversion_rate,
            "junk_by_source": junk_by_source,
            "ad_spend": None,  # MARK-03: ad spend deferred to Iteration 2
            "cpl": None,
            "cac": None,
            "roas": None,
        }

    async def get_stuck_offers(self, from_date: date, to_date: date) -> list[dict]:
        """Return list of offers stuck > 14 days without any activity — SALE-07.

        Queries v_mefi_leads_active (VIEW — not ORM model) joined to mefi_lead_history
        and mefi_salespeople via text() SQL. Tenant_id bound explicitly.

        Args:
            from_date: Start of date range (unused in query but kept for interface consistency).
            to_date: End of date range (unused in query but kept for interface consistency).

        Returns:
            List of {external_id, days_stuck (int), salesperson_name (str | None)} dicts,
            ordered by days_stuck DESC, limited to 50 records.
        """
        stuck_sql = text("""
            SELECT v.external_id,
                   ms.name AS salesperson_name,
                   EXTRACT(EPOCH FROM (now() - MAX(h.changed_at))) / 86400 AS days_stuck
            FROM v_mefi_leads_active v
            LEFT JOIN mefi_lead_history h
                ON h.lead_external_id = v.external_id
               AND h.tenant_id = :tid
            LEFT JOIN mefi_salespeople ms
                ON ms.external_id::text = v.assigned_to_id::text
               AND ms.tenant_id = :tid
            WHERE v.tenant_id = :tid
              AND v.reached_offer = true
              AND v.lifecycle NOT IN ('junk')
            GROUP BY v.external_id, ms.name
            HAVING MAX(h.changed_at) < now() - interval '14 days'
                OR MAX(h.changed_at) IS NULL
            ORDER BY days_stuck DESC NULLS LAST
            LIMIT 50
        """)

        result = await self._session.execute(
            stuck_sql,
            {"tid": str(self._tenant_id)},
        )
        rows = result.all()

        return [
            {
                "external_id": r.external_id,
                "days_stuck": int(r.days_stuck) if r.days_stuck is not None else None,
                "salesperson_name": r.salesperson_name,
            }
            for r in rows
        ]
