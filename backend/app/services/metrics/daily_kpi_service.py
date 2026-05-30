from __future__ import annotations

"""Daily KPI aggregation service.

Computes tenant-level daily KPIs from v_mefi_leads_active (D-14):
  - Lead counts by source category (6 MEFI categories; no Google — source_id=1 absent in Sofa Belle)
  - Funnel counts: visits (source_id=5 Showroom walk-ins), offers, contracts
  - 5 conversion rates with NULLIF zero-division guard (METR-02, SC#2)
  - Revenue and avg_deal_size
  - WoW (D-7) and MoM (D-30) deltas; NULL when prior row absent or prior=0 (METR-05, D-11)

visits_count = COUNT(source_id=5) — matches "Vizita" in Sofa Belle's Excel spreadsheet.
"Vizita" means Showroom walk-ins, not a funnel stage reached after the lead is created.

CONTRACT COUNTING (Phase 3 hotfix 2026-05-30, 03-HOTFIX-contract-counting-PLAN.md):
  - contracts_count + revenue use the EVENT model — a lead SIGNED (status→Clienți,
    status_id=1) on kpi_date, keyed on status_changed_at. NOT the creation-date
    cohort. A lead created in February but signed in May is a MAY contract.
  - All OTHER counts (leads, visits, offers) stay creation-date (created_at_source);
    for those, the creation IS the event. Offers cannot be reliably event-counted
    (status_changed_at is overwritten once an offered lead progresses) — known
    limitation, tracked in Phase 9 backlog.
  - Stored daily conversion_o_to_c / conversion_l_to_c divide an event-count
    (contracts) by a creation-cohort count at daily grain — they are noisy and NOT
    meaningful cohort conversions. PERIOD consumers (dashboards, get_kpi) MUST
    recompute these from summed counts over the range, not read/average these
    daily columns. conversion_l_to_v / conversion_v_to_o stay within the creation
    cohort and remain meaningful.

D-14: Never queries raw_mefi_* tables — v_mefi_leads_active only.
D-15: All date grouping via AT TIME ZONE 'Europe/Bucharest'.
D-16: All arithmetic in Decimal — never cast to float.
D-11: NULL deltas on missing prior data — never impute zero.
T-03-03-01: Explicit tenant_id filter in every Core SELECT — bypasses with_loader_criteria.

Phase 3 Plan 03 — service layer for daily_kpi table writes.
"""

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import Numeric as NumericType

# func.nullif is the SQLAlchemy Core equivalent of SQL NULLIF(expr, 0).
# We apply the zero-division guard via Python _rate() helper which mirrors
# the NULLIF pattern for Decimal arithmetic (METR-02, SC#2, D-16).
# Example reference: func.nullif(func.count(v.c.id), 0) for SQL-level guard.

logger = structlog.get_logger(__name__)


class DailyKpiService:
    """Computes tenant-level daily KPIs from conformed MEFI views.

    All queries run against v_mefi_leads_active (D-14).
    Zero-division guard via NULLIF (METR-02).
    WoW/MoM deltas via _fetch_prior_row + _compute_delta (METR-05).
    """

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id

    def _compute_delta(
        self,
        current: Decimal | None,
        prior: Decimal | None,
    ) -> Decimal | None:
        """Compute (current - prior) / prior as fractional delta.

        Returns None if either value is None or prior is 0 (D-11).
        Never raises ZeroDivisionError — guard is explicit.

        Args:
            current: Current period value.
            prior: Prior period value (D-7 for WoW, D-30 for MoM).

        Returns:
            Decimal fraction or None (D-11 — never impute zero).
        """
        if current is None or prior is None or prior == 0:
            return None
        return (current - prior) / prior

    async def _fetch_prior_row(self, kpi_date: date, days_back: int) -> object | None:
        """Read daily_kpi row for (kpi_date - days_back). Returns None if absent (D-11).

        Args:
            kpi_date: The current calculation date.
            days_back: Number of days to look back (7 for WoW, 30 for MoM).

        Returns:
            DailyKpi ORM object or None if no row exists for the prior date.
        """
        from app.models.metrics.daily_kpi import DailyKpi  # deferred — fork-safe

        prior_date = kpi_date - timedelta(days=days_back)
        stmt = select(DailyKpi).where(
            DailyKpi.tenant_id == self._tenant_id,
            DailyKpi.date == prior_date,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_funnel_config(self) -> dict:
        """Read funnel_config from tenants table for the current tenant.

        Returns the funnel_config dict. Falls back to empty dict if missing.
        funnel_config column was added by migration 003 but is not on the ORM model.
        """
        stmt = text(
            "SELECT funnel_config FROM tenants WHERE id = :tenant_id"
        ).bindparams(tenant_id=self._tenant_id)
        result = await self._session.execute(stmt)
        row = result.fetchone()
        if row and row[0]:
            return row[0]
        return {}

    async def compute_for_date(self, kpi_date: date) -> dict:
        """Compute daily KPIs for the given date.

        Queries v_mefi_leads_active for the given kpi_date (Bucharest local).
        Computes: lead counts by source, funnel counts, 5 conversion rates,
        revenue, avg_deal_size, and WoW/MoM deltas for 8 metrics.

        Args:
            kpi_date: The calendar date (Bucharest local) to compute KPIs for.

        Returns:
            Dict matching DailyKpi columns, ready for MetricsRepository.upsert_daily_kpi().
        """
        # All model imports deferred — fork-safety (INFRA-05)
        from app.models.mefi import MefiLeadHistory  # noqa: F401

        log = logger.bind(tenant_id=str(self._tenant_id), service="daily_kpi_service")
        log.info("daily_kpi.compute_start", kpi_date=str(kpi_date))

        # Read funnel_config for source category mapping
        funnel_config = await self._get_funnel_config()
        source_categories: dict = funnel_config.get("source_categories", {})

        # Source category IDs from funnel_config (fall back to Sofa Belle defaults verified 2026-05-28)
        # Showroom (id=5) = walk-in visits; Mail (id=11) only (Meta id=2 goes to alte).
        mail_fb_ig_ids = source_categories.get("mail_fb_ig", source_categories.get("mail", [11]))
        telefon_ids = source_categories.get("telefon", [10])
        whatsapp_ids = source_categories.get("whatsapp", [9])
        site_ids = source_categories.get("site", [6])
        # alte = Meta + Recomandare + Teren + Arhitect + Colaborare + Client Fidel (not Showroom)
        alte_ids = source_categories.get("alte", [2, 3, 4, 7, 12, 13])

        # Build aggregate query against v_mefi_leads_active
        # D-14: view only — never raw_mefi_*
        # D-15: AT TIME ZONE 'Europe/Bucharest' for date grouping
        # T-03-03-01: explicit tenant_id filter in WHERE clause
        query_sql = text("""
            WITH designer_leads AS (
                SELECT DISTINCT lead_external_id
                FROM mefi_lead_history
                WHERE tenant_id = :tid
                  AND to_status_id = 24
            )
            SELECT
                COUNT(*) AS leads_total,
                COUNT(CASE WHEN v.source_id = ANY(:mail_fb_ig_ids) AND d.lead_external_id IS NULL THEN 1 END) AS leads_mail_fb_ig,
                COUNT(CASE WHEN v.source_id = ANY(:telefon_ids) AND d.lead_external_id IS NULL THEN 1 END) AS leads_telefon,
                COUNT(CASE WHEN v.source_id = ANY(:whatsapp_ids) AND d.lead_external_id IS NULL THEN 1 END) AS leads_whatsapp,
                COUNT(CASE WHEN v.source_id = ANY(:site_ids) AND d.lead_external_id IS NULL THEN 1 END) AS leads_site,
                COUNT(CASE WHEN d.lead_external_id IS NOT NULL THEN 1 END) AS leads_designer,
                -- CR-03 FIX: use explicit :alte_ids binding instead of residual catch-all.
                COUNT(CASE WHEN v.source_id = ANY(:alte_ids) AND d.lead_external_id IS NULL THEN 1 END) AS leads_alte,
                -- visits_count = Showroom walk-ins (source_id=5) — matches "Vizita" in Sofa Belle Excel.
                COUNT(CASE WHEN v.source_id = 5 THEN 1 END) AS visits_count,
                COUNT(CASE WHEN v.reached_offer THEN 1 END) AS offers_count
            FROM v_mefi_leads_active v
            LEFT JOIN designer_leads d ON d.lead_external_id = v.external_id
            WHERE v.tenant_id = :tid
              AND (v.created_at_source AT TIME ZONE 'Europe/Bucharest')::date = :kpi_date
        """).bindparams(
            tid=self._tenant_id,
            kpi_date=kpi_date,
            mail_fb_ig_ids=mail_fb_ig_ids,
            telefon_ids=telefon_ids,
            whatsapp_ids=whatsapp_ids,
            site_ids=site_ids,
            alte_ids=alte_ids,  # CR-03 FIX: was fetched from funnel_config but never bound to SQL
        )

        result = await self._session.execute(query_sql)
        agg = result.fetchone()

        # Contracts + revenue use the EVENT model: a contract is a lead signed
        # (status→Clienți, status_id=1) ON kpi_date, keyed on status_changed_at —
        # NOT the creation-date cohort (Phase 3 hotfix 2026-05-30, 03-HOTFIX-*).
        # Reliable because "won" is terminal: a status-1 lead's last status change
        # IS its signing date. status_changed_at comes straight from MEFI (the real
        # value); mefi_lead_history.changed_at is sync-time and must NOT be used here.
        contracts_sql = text("""
            SELECT
                COUNT(*) AS contracts_count,
                SUM(v.estimated_value) AS revenue
            FROM v_mefi_leads_active v
            WHERE v.tenant_id = :tid
              AND v.status_id = 1
              AND (v.status_changed_at AT TIME ZONE 'Europe/Bucharest')::date = :kpi_date
        """).bindparams(tid=self._tenant_id, kpi_date=kpi_date)
        contracts_result = await self._session.execute(contracts_sql)
        contracts_agg = contracts_result.fetchone()

        leads_total = int(agg.leads_total) if agg and agg.leads_total is not None else 0
        # visits_count = Showroom walk-ins (source_id=5) — matches "Vizita" in Sofa Belle Excel.
        visits_count = int(agg.visits_count) if agg and agg.visits_count is not None else 0
        offers_count = int(agg.offers_count) if agg and agg.offers_count is not None else 0
        contracts_count = (
            int(contracts_agg.contracts_count)
            if contracts_agg and contracts_agg.contracts_count is not None
            else 0
        )
        leads_mail_fb_ig = int(agg.leads_mail_fb_ig) if agg and agg.leads_mail_fb_ig is not None else 0
        leads_telefon = int(agg.leads_telefon) if agg and agg.leads_telefon is not None else 0
        leads_whatsapp = int(agg.leads_whatsapp) if agg and agg.leads_whatsapp is not None else 0
        leads_site = int(agg.leads_site) if agg and agg.leads_site is not None else 0
        leads_designer = int(agg.leads_designer) if agg and agg.leads_designer is not None else 0
        leads_alte = int(agg.leads_alte) if agg and agg.leads_alte is not None else 0

        # Revenue and avg_deal_size — Decimal arithmetic (D-16)
        # Revenue follows contracts: estimated_value of deals SIGNED on kpi_date.
        revenue = (
            Decimal(str(contracts_agg.revenue))
            if contracts_agg and contracts_agg.revenue is not None
            else None
        )
        avg_deal_size: Decimal | None = None
        if revenue is not None and contracts_count > 0:
            avg_deal_size = revenue / Decimal(str(contracts_count))

        # 5 conversion rates with zero-division guard (METR-02, SC#2)
        # Pitfall 4: cast counts to Decimal before division to avoid integer truncation
        leads_d = Decimal(str(leads_total)) if leads_total else None
        visits_d = Decimal(str(visits_count)) if visits_count else None  # 0 → None (zero-guard)
        offers_d = Decimal(str(offers_count)) if offers_count else None
        contracts_d = Decimal(str(contracts_count)) if contracts_count else None

        def _rate(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
            """Compute numerator/denominator with zero-division guard (NULLIF pattern)."""
            if numerator is None or denominator is None or denominator == 0:
                return None
            return numerator / denominator

        conversion_l_to_v = _rate(visits_d, leads_d)
        conversion_v_to_o = _rate(offers_d, visits_d)
        conversion_l_to_o = _rate(offers_d, leads_d)
        conversion_o_to_c = _rate(contracts_d, offers_d)
        conversion_l_to_c = _rate(contracts_d, leads_d)

        # WoW (D-7) and MoM (D-30) deltas (METR-05, D-11)
        # timedelta(days=7) for WoW; timedelta(days=30) for MoM
        prior_7 = await self._fetch_prior_row(kpi_date, 7)   # D-7: timedelta(days=7)
        prior_30 = await self._fetch_prior_row(kpi_date, 30)  # D-30: timedelta(days=30)

        def _prior_val(row: object | None, attr: str) -> Decimal | None:
            if row is None:
                return None
            val = getattr(row, attr, None)
            return Decimal(str(val)) if val is not None else None

        row_dict: dict = {
            "tenant_id": self._tenant_id,
            "date": kpi_date,
            # Lead counts by source
            "leads_total": leads_total or None,
            "leads_mail_fb_ig": leads_mail_fb_ig or None,
            "leads_telefon": leads_telefon or None,
            "leads_whatsapp": leads_whatsapp or None,
            "leads_site": leads_site or None,
            "leads_designer": leads_designer or None,
            "leads_alte": leads_alte or None,
            # Funnel counts
            "visits_count": visits_count,
            "offers_count": offers_count,
            "contracts_count": contracts_count,
            # Conversion rates (METR-02)
            "conversion_l_to_v": conversion_l_to_v,
            "conversion_v_to_o": conversion_v_to_o,
            "conversion_l_to_o": conversion_l_to_o,
            "conversion_o_to_c": conversion_o_to_c,
            "conversion_l_to_c": conversion_l_to_c,
            # Revenue (D-16)
            "revenue": revenue,
            "avg_deal_size": avg_deal_size,
            # WoW deltas (METR-05, D-11)
            "leads_total_wow_delta": self._compute_delta(
                Decimal(str(leads_total)) if leads_total else None,
                _prior_val(prior_7, "leads_total"),
            ),
            "leads_total_mom_delta": self._compute_delta(
                Decimal(str(leads_total)) if leads_total else None,
                _prior_val(prior_30, "leads_total"),
            ),
            "conversion_l_to_v_wow_delta": self._compute_delta(conversion_l_to_v, _prior_val(prior_7, "conversion_l_to_v")),
            "conversion_l_to_v_mom_delta": self._compute_delta(conversion_l_to_v, _prior_val(prior_30, "conversion_l_to_v")),
            "conversion_v_to_o_wow_delta": self._compute_delta(conversion_v_to_o, _prior_val(prior_7, "conversion_v_to_o")),
            "conversion_v_to_o_mom_delta": self._compute_delta(conversion_v_to_o, _prior_val(prior_30, "conversion_v_to_o")),
            "conversion_l_to_o_wow_delta": self._compute_delta(conversion_l_to_o, _prior_val(prior_7, "conversion_l_to_o")),
            "conversion_l_to_o_mom_delta": self._compute_delta(conversion_l_to_o, _prior_val(prior_30, "conversion_l_to_o")),
            "conversion_o_to_c_wow_delta": self._compute_delta(conversion_o_to_c, _prior_val(prior_7, "conversion_o_to_c")),
            "conversion_o_to_c_mom_delta": self._compute_delta(conversion_o_to_c, _prior_val(prior_30, "conversion_o_to_c")),
            "conversion_l_to_c_wow_delta": self._compute_delta(conversion_l_to_c, _prior_val(prior_7, "conversion_l_to_c")),
            "conversion_l_to_c_mom_delta": self._compute_delta(conversion_l_to_c, _prior_val(prior_30, "conversion_l_to_c")),
            "revenue_wow_delta": self._compute_delta(revenue, _prior_val(prior_7, "revenue")),
            "revenue_mom_delta": self._compute_delta(revenue, _prior_val(prior_30, "revenue")),
            "avg_deal_size_wow_delta": self._compute_delta(avg_deal_size, _prior_val(prior_7, "avg_deal_size")),
            "avg_deal_size_mom_delta": self._compute_delta(avg_deal_size, _prior_val(prior_30, "avg_deal_size")),
        }

        log.info("daily_kpi.compute_done", kpi_date=str(kpi_date), leads_total=leads_total)
        return row_dict
