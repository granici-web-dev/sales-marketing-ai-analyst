from __future__ import annotations

"""Per-source KPI aggregation service.

Computes per-source daily KPIs from v_mefi_leads_active (D-14):
  - Exactly 7 rows per day per tenant (D-04): mail_fb_ig | telefon | whatsapp |
    site | designer | alte | google
  - Designer detection via mefi_lead_history.to_status_id = 24 (D-02)
  - Google = source_id = 1 (D-01, hardcoded)
  - Source ID → category mapping from tenants.funnel_config.source_categories
  - leads, visits, offers, deals_won, revenue, conversion_rate per category
  - Zero counts emitted for categories with no leads (D-04)

D-01: Google (source_id=1) stored as a single 'google' row.
D-02: Designer leads from mefi_lead_history.to_status_id=24 — overrides source_id.
D-04: Exactly 7 rows in canonical order.
D-14: Never queries raw_mefi_* tables — v_mefi_leads_active only.
D-15: AT TIME ZONE 'Europe/Bucharest' for date grouping.
D-16: All arithmetic in Decimal — never cast to float.
T-03-03-01: Explicit tenant_id filter in Core SELECTs (bypasses with_loader_criteria).

Phase 3 Plan 03 — service layer for source_daily_kpi table writes.
"""

from datetime import date
from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

# D-04: canonical category order (must always emit exactly these 7)
CANONICAL_CATEGORIES = ["mail_fb_ig", "telefon", "whatsapp", "site", "designer", "alte", "google"]


class SourceKpiService:
    """Computes per-source daily KPIs from conformed MEFI views.

    Exactly 7 source categories per day (D-04).
    Designer detection via mefi_lead_history JOIN (D-02).
    Source category mapping from funnel_config.source_categories.
    """

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id

    def _categorize_lead(self, source_id: int | None, is_designer: bool) -> str:
        """Map a single lead's source_id to a category name.

        Designer flag takes precedence (D-02).
        Google is source_id=1 (D-01).
        Source category mapping uses Sofa Belle defaults.

        Args:
            source_id: MEFI source_id from the lead.
            is_designer: True if lead ever had to_status_id=24 in history (D-02).

        Returns:
            Category string from CANONICAL_CATEGORIES.
        """
        if is_designer:
            return "designer"
        if source_id == 1:
            return "google"
        if source_id in (2, 11):
            return "mail_fb_ig"
        if source_id == 10:
            return "telefon"
        if source_id == 9:
            return "whatsapp"
        if source_id == 6:
            return "site"
        return "alte"

    async def _get_source_categories(self) -> dict:
        """Read source_categories from tenants.funnel_config JSONB.

        Returns the source_categories dict. Falls back to Sofa Belle defaults.
        """
        stmt = text(
            "SELECT funnel_config FROM tenants WHERE id = :tenant_id"
        ).bindparams(tenant_id=str(self._tenant_id))
        result = await self._session.execute(stmt)
        row = result.fetchone()
        if row and row[0] and "source_categories" in row[0]:
            return row[0]["source_categories"]
        # Fall back to Sofa Belle defaults (D-01, D-02, D-03, D-04)
        return {
            "mail_fb_ig": [2, 11],
            "telefon": [10],
            "whatsapp": [9],
            "site": [6],
            "designer": [],  # derived from history, not source_id (D-02)
            "alte": [3, 4, 5, 7, 12, 13],
        }

    async def compute_source_kpis(self, kpi_date: date) -> list[dict]:
        """Compute per-source KPIs for the given date.

        Public method aliased from compute_for_date for test compatibility.
        """
        return await self.compute_for_date(kpi_date)

    async def compute_for_date(self, kpi_date: date) -> list[dict]:
        """Compute per-source daily KPIs for the given date.

        Returns exactly 7 dicts (D-04) in canonical order, even when some
        categories have 0 leads.

        Args:
            kpi_date: The calendar date (Bucharest local) to compute KPIs for.

        Returns:
            List of 7 dicts matching SourceDailyKpi columns.
        """
        log = logger.bind(tenant_id=str(self._tenant_id), service="source_kpi_service")
        log.info("source_kpi.compute_start", kpi_date=str(kpi_date))

        # Read source categories mapping from funnel_config
        source_categories = await self._get_source_categories()

        # Build category → source_id mapping
        mail_fb_ig_ids = source_categories.get("mail_fb_ig", [2, 11])
        telefon_ids = source_categories.get("telefon", [10])
        whatsapp_ids = source_categories.get("whatsapp", [9])
        site_ids = source_categories.get("site", [6])
        alte_ids = source_categories.get("alte", [3, 4, 5, 7, 12, 13])

        # Designer detection subquery (D-02)
        # MUST include tenant_id filter — Core queries bypass with_loader_criteria (T-03-03-01)
        # to_status_id = 24 in mefi_lead_history marks designer leads
        per_source_sql = text("""
            WITH designer_leads AS (
                SELECT DISTINCT lead_external_id
                FROM mefi_lead_history
                WHERE tenant_id = :tid
                  AND to_status_id = 24
            ),
            categorized AS (
                SELECT
                    v.external_id,
                    v.reached_visit,
                    v.reached_offer,
                    v.reached_contract,
                    v.estimated_value,
                    -- CR-03 FIX: use explicit :alte_ids binding instead of residual ELSE catch-all.
                    -- The ELSE 'alte' ignored tenants with custom alte_ids in funnel_config.
                    CASE
                        WHEN d.lead_external_id IS NOT NULL THEN 'designer'
                        WHEN v.source_id = 1 THEN 'google'
                        WHEN v.source_id = ANY(:mail_fb_ig_ids) THEN 'mail_fb_ig'
                        WHEN v.source_id = ANY(:telefon_ids) THEN 'telefon'
                        WHEN v.source_id = ANY(:whatsapp_ids) THEN 'whatsapp'
                        WHEN v.source_id = ANY(:site_ids) THEN 'site'
                        WHEN v.source_id = ANY(:alte_ids) THEN 'alte'
                        ELSE 'alte'
                    END AS source_category
                FROM v_mefi_leads_active v
                LEFT JOIN designer_leads d ON d.lead_external_id = v.external_id
                WHERE v.tenant_id = :tid
                  AND (v.created_at_source AT TIME ZONE 'Europe/Bucharest')::date = :kpi_date
            )
            SELECT
                source_category,
                COUNT(*) AS leads,
                COUNT(CASE WHEN reached_visit THEN 1 END) AS visits,
                COUNT(CASE WHEN reached_offer THEN 1 END) AS offers,
                COUNT(CASE WHEN reached_contract THEN 1 END) AS deals_won,
                SUM(CASE WHEN reached_contract THEN estimated_value ELSE NULL END) AS revenue
            FROM categorized
            GROUP BY source_category
        """).bindparams(
            tid=str(self._tenant_id),
            kpi_date=kpi_date,
            mail_fb_ig_ids=mail_fb_ig_ids,
            telefon_ids=telefon_ids,
            whatsapp_ids=whatsapp_ids,
            site_ids=site_ids,
            alte_ids=alte_ids,  # CR-03 FIX: was fetched from funnel_config but never bound to SQL
        )

        result = await self._session.execute(per_source_sql)
        db_rows = result.all()

        # Build lookup from DB results
        db_lookup: dict[str, object] = {}
        for r in db_rows:
            db_lookup[r.source_category] = r

        # Emit exactly 7 rows in canonical order (D-04) — fill missing with zeros
        output: list[dict] = []
        for category in CANONICAL_CATEGORIES:
            r = db_lookup.get(category)
            if r is not None:
                leads = int(r.leads) if r.leads is not None else 0
                visits = int(r.visits) if r.visits is not None else 0
                offers = int(r.offers) if r.offers is not None else 0
                deals_won = int(r.deals_won) if r.deals_won is not None else 0
                revenue = Decimal(str(r.revenue)) if r.revenue is not None else None
            else:
                leads = 0
                visits = 0
                offers = 0
                deals_won = 0
                revenue = None

            # Conversion rate = deals_won / leads with NULLIF zero-division guard
            conversion_rate: Decimal | None = None
            if leads > 0:
                conversion_rate = Decimal(str(deals_won)) / Decimal(str(leads))

            output.append({
                "tenant_id": self._tenant_id,
                "source": category,
                "date": kpi_date,
                "leads": leads,
                "visits": visits,
                "offers": offers,
                "deals_won": deals_won,
                "revenue": revenue,
                "conversion_rate": conversion_rate,
                # ad_spend, cpl, cac, roas left NULL (D-08 — Iteration 2)
            })

        log.info("source_kpi.compute_done", kpi_date=str(kpi_date), records=len(output))
        return output
