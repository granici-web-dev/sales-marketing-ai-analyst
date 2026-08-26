"""Per-salesperson KPI aggregation service.

Computes per-salesperson daily KPIs from v_mefi_leads_active (D-14):
  - One row per ACTIVE salesperson (is_active=True only — D-17)
  - leads_assigned, leads_contacted, visits_conducted (source_id=5 walk-ins), offers_sent, deals_won, deals_lost
  - avg_time_to_first_touch_minutes: business-hours-adjusted (D-06)
  - revenue, 4 conversion rates with NULLIF guard
  - data_completeness_pct: % leads with estimated_value filled (METR-06)

CONTRACT COUNTING (Phase 3 hotfix 2026-05-30, 03-HOTFIX-contract-counting-PLAN.md):
  - deals_won + revenue use the EVENT model — deals SIGNED on kpi_date
    (status→Clienți, status_id=1), keyed on status_changed_at via a separate
    per-rep query. NOT the creation-date cohort.
  - leads_assigned, leads_contacted, visits_conducted, offers_sent, deals_lost,
    TTFT, data_completeness_pct stay on the creation cohort (created_at_source).
    deals_won (event) and deals_lost (cohort) are deliberately asymmetric —
    deals_lost is out of scope for this hotfix.
  - conversion_o_to_c / conversion_l_to_c stored daily are event/cohort and noisy;
    period reads recompute from summed counts. win_rate (read service) already
    recomputes from sums.

D-05: "First touch" = first row in mefi_lead_history. NULL for leads with no history.
D-06: Business-hours-adjusted minutes (zoneinfo, DST-safe).
D-17: Filter MefiSalesperson.is_active == True (not NULL).
D-14: Never queries raw_mefi_* tables — v_mefi_leads_active only.
D-15: AT TIME ZONE 'Europe/Bucharest' for date grouping.
D-16: All arithmetic in Decimal — never cast to float.
T-03-03-01: Explicit tenant_id filter in every Core SELECT.

Phase 3 Plan 03 — service layer for salesperson_daily_kpi table writes.
"""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

# Default Sofa Belle business hours (D-07 fallback)
_DEFAULT_BH = {
    "days": [0, 1, 2, 3, 4, 5, 6],
    "open": "09:00",
    "close": "19:00",
    "tz": "Europe/Bucharest",
}


class SalespersonKpiService:
    """Computes per-salesperson daily KPIs from conformed MEFI views.

    One row per active salesperson per day.
    business_hours config read from tenants.funnel_config (D-07).
    avg_time_to_first_touch_minutes uses business_minutes_between (D-06).
    """

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def _get_business_hours(self) -> dict:
        """Read business_hours config from tenants.funnel_config JSONB (D-07).

        Returns default Sofa Belle schedule if not configured or malformed.
        T-03-03-04: Falls back to hardcoded D-07 default to prevent injection.
        """
        stmt = text("SELECT funnel_config FROM tenants WHERE id = :tenant_id").bindparams(
            tenant_id=self._tenant_id
        )
        result = await self._session.execute(stmt)
        row = result.fetchone()
        if row and row[0] and "business_hours" in row[0]:
            return row[0]["business_hours"]
        return dict(_DEFAULT_BH)

    def _compute_time_to_first_touch(
        self,
        lead_external_id: str,
        history_rows: list[dict],
        lead_created_at: datetime | None = None,
        open_time: time | None = None,
        close_time: time | None = None,
        work_days: list[int] | None = None,
        tz: ZoneInfo | None = None,
    ) -> int | None:
        """Compute business-hours-adjusted time to first touch for a single lead.

        D-05: "First touch" = first row in mefi_lead_history (earliest changed_at).
        D-06: business-hours-adjusted — only working minutes count.
        Returns None when history_rows is empty (D-05 — incomplete history, not imputed).

        Args:
            lead_external_id: Lead identifier (for logging).
            history_rows: List of history dicts with 'changed_at' timestamps.
            lead_created_at: Lead creation timestamp.
            open_time: Business open time (D-07 default if None).
            close_time: Business close time (D-07 default if None).
            work_days: Work day ints (D-07 default if None).
            tz: Timezone (D-07 Bucharest if None).

        Returns:
            Integer minutes or None (D-05).
        """
        if not history_rows or lead_created_at is None:
            return None

        # Find first touch (earliest changed_at)
        # CR-02 FIX: collect to list first so we can check emptiness before calling min().
        # min() on an empty generator raises ValueError, not returns None — the guard
        # below it was dead code. A non-empty history_rows where all changed_at are None
        # is a valid data-quality condition (history row written before timestamp available).
        valid_timestamps = [
            row["changed_at"] for row in history_rows if row.get("changed_at") is not None
        ]
        if not valid_timestamps:
            return None
        first_touch = min(valid_timestamps)

        from app.services.metrics.business_hours import business_minutes_between  # deferred

        if open_time is None:
            open_time = time(9, 0)
        if close_time is None:
            close_time = time(19, 0)
        if work_days is None:
            work_days = [0, 1, 2, 3, 4, 5, 6]
        if tz is None:
            tz = ZoneInfo("Europe/Bucharest")

        return business_minutes_between(
            lead_created_at, first_touch, open_time, close_time, work_days, tz
        )

    async def compute_salesperson_kpis(self, kpi_date: date) -> list[dict]:
        """Compute per-salesperson KPIs for the given date.

        Public method aliased from compute_for_date for backwards compatibility
        with tests. Calls compute_for_date internally.

        Args:
            kpi_date: The calendar date (Bucharest local) to compute KPIs for.

        Returns:
            List of dicts, one per active salesperson.
        """
        return await self.compute_for_date(kpi_date)

    async def compute_for_date(self, kpi_date: date) -> list[dict]:
        """Compute per-salesperson KPIs for the given date.

        Queries MefiSalesperson for active salespeople (D-17), then for each
        queries v_mefi_leads_active for leads assigned to them on kpi_date.
        Computes TTFT via business_minutes_between (D-06).

        Args:
            kpi_date: The calendar date (Bucharest local) to compute KPIs for.

        Returns:
            List of dicts matching SalespersonDailyKpi columns.
        """
        from app.models.mefi import MefiSalesperson  # deferred — fork-safe

        log = logger.bind(tenant_id=str(self._tenant_id), service="salesperson_kpi_service")
        log.info("salesperson_kpi.compute_start", kpi_date=str(kpi_date))

        # Read business hours config (D-07)
        bh = await self._get_business_hours()
        try:
            open_time = time(int(bh["open"].split(":")[0]), int(bh["open"].split(":")[1]))
            close_time = time(int(bh["close"].split(":")[0]), int(bh["close"].split(":")[1]))
            work_days = list(bh["days"])
            if not work_days:
                # CR-04 FIX: empty work_days would cause _next_open to loop forever
                # (while True: candidate_date.weekday() in [] → always False → infinite loop).
                # Raise ValueError so the except block below falls back to the safe default.
                raise ValueError("business_hours.days must not be empty")
            tz = ZoneInfo(bh.get("tz", "Europe/Bucharest"))
        except (KeyError, ValueError, AttributeError):
            # T-03-03-04: malformed config falls back to D-07 default
            open_time = time(9, 0)
            close_time = time(19, 0)
            work_days = [0, 1, 2, 3, 4, 5, 6]
            tz = ZoneInfo("Europe/Bucharest")

        # Fetch active salespeople (D-17: is_active == True, excludes NULL)
        sp_stmt = select(
            MefiSalesperson.external_id,
            MefiSalesperson.name,
        ).where(
            MefiSalesperson.tenant_id == self._tenant_id,
            MefiSalesperson.is_active.is_(True),  # IS TRUE — excludes NULL (D-17)
        )
        sp_result = await self._session.execute(sp_stmt)
        salespeople = sp_result.all()

        rows: list[dict] = []
        for sp in salespeople:
            sp_external_id = sp.external_id

            # Per-rep query against v_mefi_leads_active (D-14)
            # D-15: AT TIME ZONE 'Europe/Bucharest' for date grouping
            # T-03-03-01: explicit tenant_id filter
            per_rep_sql = text("""
                SELECT
                    v.external_id AS lead_external_id,
                    v.created_at_source,
                    v.source_id,
                    v.reached_offer,
                    v.reached_contract,
                    v.estimated_value
                FROM v_mefi_leads_active v
                WHERE v.tenant_id = :tid
                  AND v.assigned_to_id = :sp_id
                  AND (v.created_at_source AT TIME ZONE 'Europe/Bucharest')::date = :kpi_date
            """).bindparams(
                tid=self._tenant_id,
                sp_id=sp_external_id,
                kpi_date=kpi_date,
            )
            lead_result = await self._session.execute(per_rep_sql)
            leads = lead_result.all()

            leads_assigned = len(leads)
            # visits_conducted = Showroom walk-ins (source_id=5) — matches "Vizita" in Sofa Belle Excel.
            visits_conducted = sum(1 for lead in leads if lead.source_id == 5)
            offers_sent = sum(1 for lead in leads if lead.reached_offer)
            # deals_lost stays on the creation cohort (out of scope for the contract
            # hotfix; not a MEFI-comparison metric). Note the deliberate asymmetry with
            # deals_won (event model) documented in the module docstring.
            deals_lost = sum(
                1 for lead in leads if not lead.reached_contract and not lead.reached_offer
            )

            # deals_won + revenue use the EVENT model: deals this rep SIGNED on
            # kpi_date (status→Clienți, status_id=1), keyed on status_changed_at —
            # NOT the creation-date cohort (Phase 3 hotfix 2026-05-30). A lead created
            # last month but signed today counts for today's row.
            won_sql = text("""
                SELECT v.estimated_value
                FROM v_mefi_leads_active v
                WHERE v.tenant_id = :tid
                  AND v.assigned_to_id = :sp_id
                  AND v.status_id = 1
                  AND (v.status_changed_at AT TIME ZONE 'Europe/Bucharest')::date = :kpi_date
            """).bindparams(tid=self._tenant_id, sp_id=sp_external_id, kpi_date=kpi_date)
            won_result = await self._session.execute(won_sql)
            won_rows = won_result.all()

            deals_won = len(won_rows)

            # Revenue — sum estimated_value for deals signed on kpi_date (D-16 Decimal)
            revenue: Decimal | None = None
            won_values = [
                Decimal(str(w.estimated_value)) for w in won_rows if w.estimated_value is not None
            ]
            if won_values:
                revenue = sum(won_values, Decimal("0"))

            # data_completeness_pct (METR-06)
            data_completeness_pct: Decimal | None = None
            if leads_assigned > 0:
                non_null_count = sum(1 for lead in leads if lead.estimated_value is not None)
                data_completeness_pct = (
                    Decimal(str(non_null_count)) / Decimal(str(leads_assigned)) * Decimal("100")
                )

            # WR-03 FIX: Initialize history_by_lead unconditionally to avoid implicit
            # scoping dependency between two separate `if leads_assigned > 0` blocks.
            # Without this, the `leads_contacted` block below silently depends on
            # history_by_lead being set in the first block — fragile after refactors.
            history_by_lead: dict[str, list[dict]] = {}

            # Time to first touch — fetch lead history for this rep's leads (D-05, D-06)
            ttft_minutes: int | None = None
            if leads_assigned > 0:
                lead_ids = [str(lead.lead_external_id) for lead in leads]
                history_sql = text("""
                    SELECT lead_external_id, changed_at
                    FROM mefi_lead_history
                    WHERE tenant_id = :tid
                      AND lead_external_id = ANY(:lead_ids)
                    ORDER BY lead_external_id, changed_at ASC
                """).bindparams(tid=self._tenant_id, lead_ids=lead_ids)
                hist_result = await self._session.execute(history_sql)
                history_rows_all = hist_result.all()

                # Build per-lead history map (initialized unconditionally above)
                for h in history_rows_all:
                    lid = str(h.lead_external_id)
                    if lid not in history_by_lead:
                        history_by_lead[lid] = []
                    history_by_lead[lid].append({"changed_at": h.changed_at})

                # Compute TTFT for each lead and average
                ttft_values: list[int] = []
                for lead in leads:
                    if lead.created_at_source is None:
                        continue
                    lead_history = history_by_lead.get(str(lead.lead_external_id), [])
                    ttft = self._compute_time_to_first_touch(
                        str(lead.lead_external_id),
                        lead_history,
                        lead_created_at=lead.created_at_source,
                        open_time=open_time,
                        close_time=close_time,
                        work_days=work_days,
                        tz=tz,
                    )
                    if ttft is not None:
                        ttft_values.append(ttft)

                if ttft_values:
                    ttft_minutes = int(sum(ttft_values) / len(ttft_values))

            # 4 conversion rates with NULLIF guard (METR-04)
            leads_d = Decimal(str(leads_assigned)) if leads_assigned else None
            visits_d = Decimal(str(visits_conducted)) if visits_conducted else None
            offers_d = Decimal(str(offers_sent)) if offers_sent else None
            contracts_d = Decimal(str(deals_won)) if deals_won else None

            def _rate(num: Decimal | None, den: Decimal | None) -> Decimal | None:
                if num is None or den is None or den == 0:
                    return None
                return num / den

            avg_deal_size: Decimal | None = None
            if revenue is not None and deals_won > 0:
                avg_deal_size = revenue / Decimal(str(deals_won))

            # leads_contacted — count leads that have at least one history row
            # history_by_lead is always defined (initialized unconditionally above)
            if leads_assigned > 0:
                leads_contacted = sum(
                    1 for lead in leads if str(lead.lead_external_id) in history_by_lead
                )
            else:
                leads_contacted = 0

            row: dict = {
                "tenant_id": self._tenant_id,
                "date": kpi_date,
                "salesperson_external_id": str(sp_external_id),
                "leads_assigned": leads_assigned,
                "leads_contacted": leads_contacted,
                "avg_time_to_first_touch_minutes": ttft_minutes,
                "visits_conducted": visits_conducted,
                "offers_sent": offers_sent,
                "deals_won": deals_won,
                "deals_lost": deals_lost,
                "revenue": revenue,
                "conversion_l_to_v": _rate(visits_d, leads_d),
                "conversion_v_to_o": _rate(offers_d, visits_d),
                "conversion_o_to_c": _rate(contracts_d, offers_d),
                "conversion_l_to_c": _rate(contracts_d, leads_d),
                "avg_deal_size": avg_deal_size,
                "data_completeness_pct": data_completeness_pct,
            }
            rows.append(row)

        log.info("salesperson_kpi.compute_done", kpi_date=str(kpi_date), records=len(rows))
        return rows
