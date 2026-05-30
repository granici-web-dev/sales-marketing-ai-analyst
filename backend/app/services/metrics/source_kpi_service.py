from __future__ import annotations

"""Per-source KPI aggregation service.

Computes per-source daily KPIs from v_mefi_leads_active (D-14).
One row per MEFI source category per day; zero-fill for categories with no leads.

CONTRACT COUNTING (Phase 3 hotfix 2026-05-30, 03-HOTFIX-contract-counting-PLAN.md):
  deals_won + revenue per source use the EVENT model — contracts SIGNED on kpi_date
  (status→Clienți, status_id=1), keyed on status_changed_at, grouped by source. leads,
  offers, visits stay on the creation cohort (created_at_source). The per-day
  conversion_rate (deals_won/leads) is therefore event/cohort and noisy at daily
  grain; period reads (dashboards) recompute it from summed counts over the range.

Source categories (verified 2026-05-28 from Sofa Belle raw_mefi_leads):
  showroom     | source_id=5  | Walk-in to physical showroom — "Vizita" in client Excel
  mail         | source_id=11 | Email leads
  telefon      | source_id=10 | Inbound phone calls
  whatsapp     | source_id=9  | WhatsApp Business
  site         | source_id=6  | Website contact forms
  meta         | source_id=2  | Facebook/Instagram paid ads
  recomandare  | source_id=3  | Word-of-mouth referrals
  colaborare   | source_id=12 | Partner/collaboration
  arhitect     | source_id=7  | Interior architect referrals
  client_fidel | source_id=13 | Repeat customers
  other        | null/unknown | Catch-all for unmapped source IDs

Note: source_id=1 (Google) is NOT present in Sofa Belle's data — Google traffic
arrives via source_id=6 (Site). Designer (status_id=24) is a MEFI status, not a
source, and is tracked separately in daily_kpi.leads_designer.

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

# Canonical category order — emitted for every date even when leads=0.
# Verified against Sofa Belle source IDs 2026-05-28.
CANONICAL_CATEGORIES = [
    "showroom", "mail", "telefon", "whatsapp", "site",
    "meta", "recomandare", "colaborare", "arhitect", "client_fidel", "other",
]


class SourceKpiService:
    """Computes per-source daily KPIs from conformed MEFI views.

    One row per MEFI source category per day, zero-filled for missing categories.
    Source category mapping from funnel_config.source_categories (falls back to
    Sofa Belle defaults verified 2026-05-28).
    """

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id

    def _categorize_lead(self, source_id: int | None) -> str:
        """Map a single lead's source_id to a category name.

        Verified against Sofa Belle source IDs 2026-05-28.

        Args:
            source_id: MEFI source_id from the lead, or None.

        Returns:
            Category string from CANONICAL_CATEGORIES.
        """
        mapping = {
            5: "showroom",
            11: "mail",
            10: "telefon",
            9: "whatsapp",
            6: "site",
            2: "meta",
            3: "recomandare",
            12: "colaborare",
            7: "arhitect",
            13: "client_fidel",
        }
        return mapping.get(source_id, "other")  # type: ignore[arg-type]

    async def _get_source_categories(self) -> dict:
        """Read source_categories from tenants.funnel_config JSONB.

        Returns the source_categories dict. Falls back to Sofa Belle defaults.
        """
        stmt = text(
            "SELECT funnel_config FROM tenants WHERE id = :tenant_id"
        ).bindparams(tenant_id=self._tenant_id)
        result = await self._session.execute(stmt)
        row = result.fetchone()
        if row and row[0] and "source_categories" in row[0]:
            return row[0]["source_categories"]
        # Fall back to Sofa Belle defaults (verified 2026-05-28 from raw_mefi_leads)
        return {
            "showroom": [5],
            "mail": [11],
            "telefon": [10],
            "whatsapp": [9],
            "site": [6],
            "meta": [2],
            "recomandare": [3],
            "colaborare": [12],
            "arhitect": [7],
            "client_fidel": [13],
            "other": [],  # null/unknown source_id — handled by ELSE in SQL
        }

    async def compute_source_kpis(self, kpi_date: date) -> list[dict]:
        """Compute per-source KPIs for the given date.

        Public method aliased from compute_for_date for test compatibility.
        """
        return await self.compute_for_date(kpi_date)

    async def compute_for_date(self, kpi_date: date) -> list[dict]:
        """Compute per-source daily KPIs for the given date.

        Returns one dict per canonical category (11 total), zero-filled for
        categories with no leads on that date.

        Args:
            kpi_date: The calendar date (Bucharest local) to compute KPIs for.

        Returns:
            List of 11 dicts matching SourceDailyKpi columns.
        """
        log = logger.bind(tenant_id=str(self._tenant_id), service="source_kpi_service")
        log.info("source_kpi.compute_start", kpi_date=str(kpi_date))

        # Source category → source_id list mapping from funnel_config or Sofa Belle defaults
        source_categories = await self._get_source_categories()

        showroom_ids     = source_categories.get("showroom",     [5])
        mail_ids         = source_categories.get("mail",         [11])
        telefon_ids      = source_categories.get("telefon",      [10])
        whatsapp_ids     = source_categories.get("whatsapp",     [9])
        site_ids         = source_categories.get("site",         [6])
        meta_ids         = source_categories.get("meta",         [2])
        recomandare_ids  = source_categories.get("recomandare",  [3])
        colaborare_ids   = source_categories.get("colaborare",   [12])
        arhitect_ids     = source_categories.get("arhitect",     [7])
        client_fidel_ids = source_categories.get("client_fidel", [13])

        # All known source_ids — everything else → 'other'
        known_ids = (
            showroom_ids + mail_ids + telefon_ids + whatsapp_ids + site_ids
            + meta_ids + recomandare_ids + colaborare_ids + arhitect_ids + client_fidel_ids
        )

        # Query 1 — leads + offers on the CREATION cohort (created_at_source).
        per_source_sql = text("""
            WITH categorized AS (
                SELECT
                    v.reached_offer,
                    CASE
                        WHEN v.source_id = ANY(:showroom_ids)     THEN 'showroom'
                        WHEN v.source_id = ANY(:mail_ids)         THEN 'mail'
                        WHEN v.source_id = ANY(:telefon_ids)      THEN 'telefon'
                        WHEN v.source_id = ANY(:whatsapp_ids)     THEN 'whatsapp'
                        WHEN v.source_id = ANY(:site_ids)         THEN 'site'
                        WHEN v.source_id = ANY(:meta_ids)         THEN 'meta'
                        WHEN v.source_id = ANY(:recomandare_ids)  THEN 'recomandare'
                        WHEN v.source_id = ANY(:colaborare_ids)   THEN 'colaborare'
                        WHEN v.source_id = ANY(:arhitect_ids)     THEN 'arhitect'
                        WHEN v.source_id = ANY(:client_fidel_ids) THEN 'client_fidel'
                        ELSE 'other'
                    END AS source_category
                FROM v_mefi_leads_active v
                WHERE v.tenant_id = :tid
                  AND (v.created_at_source AT TIME ZONE 'Europe/Bucharest')::date = :kpi_date
            )
            SELECT
                source_category,
                COUNT(*) AS leads,
                COUNT(CASE WHEN reached_offer THEN 1 END) AS offers
            FROM categorized
            GROUP BY source_category
        """).bindparams(
            tid=self._tenant_id,
            kpi_date=kpi_date,
            showroom_ids=showroom_ids,
            mail_ids=mail_ids,
            telefon_ids=telefon_ids,
            whatsapp_ids=whatsapp_ids,
            site_ids=site_ids,
            meta_ids=meta_ids,
            recomandare_ids=recomandare_ids,
            colaborare_ids=colaborare_ids,
            arhitect_ids=arhitect_ids,
            client_fidel_ids=client_fidel_ids,
        )

        result = await self._session.execute(per_source_sql)
        db_rows = result.all()

        # Build lookup from DB results
        db_lookup: dict[str, object] = {}
        for r in db_rows:
            db_lookup[r.source_category] = r

        # Query 2 — deals_won + revenue on the EVENT model: contracts SIGNED on
        # kpi_date (status→Clienți, status_id=1), keyed on status_changed_at, grouped
        # by the same source category (Phase 3 hotfix 2026-05-30). The lead's SOURCE
        # is its origin channel; signing date is when the deal closed.
        contracts_sql = text("""
            WITH categorized AS (
                SELECT
                    v.estimated_value,
                    CASE
                        WHEN v.source_id = ANY(:showroom_ids)     THEN 'showroom'
                        WHEN v.source_id = ANY(:mail_ids)         THEN 'mail'
                        WHEN v.source_id = ANY(:telefon_ids)      THEN 'telefon'
                        WHEN v.source_id = ANY(:whatsapp_ids)     THEN 'whatsapp'
                        WHEN v.source_id = ANY(:site_ids)         THEN 'site'
                        WHEN v.source_id = ANY(:meta_ids)         THEN 'meta'
                        WHEN v.source_id = ANY(:recomandare_ids)  THEN 'recomandare'
                        WHEN v.source_id = ANY(:colaborare_ids)   THEN 'colaborare'
                        WHEN v.source_id = ANY(:arhitect_ids)     THEN 'arhitect'
                        WHEN v.source_id = ANY(:client_fidel_ids) THEN 'client_fidel'
                        ELSE 'other'
                    END AS source_category
                FROM v_mefi_leads_active v
                WHERE v.tenant_id = :tid
                  AND v.status_id = 1
                  AND (v.status_changed_at AT TIME ZONE 'Europe/Bucharest')::date = :kpi_date
            )
            SELECT
                source_category,
                COUNT(*) AS deals_won,
                SUM(estimated_value) AS revenue
            FROM categorized
            GROUP BY source_category
        """).bindparams(
            tid=self._tenant_id,
            kpi_date=kpi_date,
            showroom_ids=showroom_ids,
            mail_ids=mail_ids,
            telefon_ids=telefon_ids,
            whatsapp_ids=whatsapp_ids,
            site_ids=site_ids,
            meta_ids=meta_ids,
            recomandare_ids=recomandare_ids,
            colaborare_ids=colaborare_ids,
            arhitect_ids=arhitect_ids,
            client_fidel_ids=client_fidel_ids,
        )

        contracts_result = await self._session.execute(contracts_sql)
        contracts_lookup: dict[str, object] = {}
        for r in contracts_result.all():
            contracts_lookup[r.source_category] = r

        # Emit one row per canonical category — fill missing with zeros.
        # "showroom" leads are the visits metric: leads who walked into the showroom.
        output: list[dict] = []
        for category in CANONICAL_CATEGORIES:
            r = db_lookup.get(category)
            if r is not None:
                leads = int(r.leads) if r.leads is not None else 0
                offers = int(r.offers) if r.offers is not None else 0
            else:
                leads = 0
                offers = 0

            c = contracts_lookup.get(category)
            if c is not None:
                deals_won = int(c.deals_won) if c.deals_won is not None else 0
                revenue = Decimal(str(c.revenue)) if c.revenue is not None else None
            else:
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
                "visits": leads if category == "showroom" else None,  # showroom leads ARE visits
                "offers": offers,
                "deals_won": deals_won,
                "revenue": revenue,
                "conversion_rate": conversion_rate,
                # ad_spend, cpl, cac, roas left NULL (D-08 — Iteration 2)
            })

        log.info("source_kpi.compute_done", kpi_date=str(kpi_date), records=len(output))
        return output
