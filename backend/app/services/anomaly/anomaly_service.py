from __future__ import annotations

"""Anomaly detection rule engine for Phase 4.

Implements 5 rule methods + run_all_rules() orchestrator called by the Celery task.

Design decisions:
  D-09: Single AnomalyService class with all 5 rule methods + orchestrator
  D-11: junk_ids computed ONCE in run_all_rules() and passed to all non-junk rules
  D-14: slow_first_touch checks yesterday-only leads (kpi_date leads, not prior days)
  D-20: Thresholds locked — slow_first_touch 5h (300min), stuck_offer 15d, drop 35%, sp 30%, junk 25%

Rule severities:
  slow_first_touch            → high    (ROADMAP SC#2)
  stuck_offer                 → medium  (ROADMAP SC#3)
  showroom_traffic_drop       → medium
  underperforming_salesperson → medium
  junk_lead_quality           → low

Loss formulas (CONTEXT.md D-04 through D-08):
  D-06: slow_first_touch loss = count × avg_deal_size × 0.25
  D-07: stuck_offer loss = sum(estimated_value) × trailing_close_rate
  D-08: junk_lead_quality loss = junk_count × avg_deal_size × trailing_close_rate
  D-05: trend rules use lost-opportunity formula with avg_deal_size × trailing_close_rate

T-04-03-01: Log only counts, dates, rule names — never log lead_ids (CLAUDE.md Principle #6)
T-04-03-02: Every DB query includes tenant_id filter (CLAUDE.md Principle #3)
T-04-03-03: All monetary values as Decimal — never float (D-19)

Testing pattern:
  Each detect_* method accepts pre-fetched data as optional keyword args for testability.
  When called with data (unit tests), no DB queries are made.
  When called without data (from run_all_rules()), data is fetched from DB internally.
  run_all_rules() only calls _get_junk_ids() and the detect methods — no separate pre-fetch.
"""

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

# Module-level constants — all thresholds locked per D-20
AVG_DEAL_SIZE_FALLBACK = Decimal("20000.00")  # Known Sofa Belle value for MVP1
SLOW_FIRST_TOUCH_THRESHOLD_MINUTES = 300  # 5 business hours (D-20)
STUCK_OFFER_DAYS = 15  # (D-20)
SHOWROOM_DROP_THRESHOLD = Decimal("0.65")  # 1 - 0.35 = fires when current < baseline × 0.65 (D-20)
UNDERPERFORMING_THRESHOLD = Decimal("0.70")  # 1 - 0.30 = fires when sp_rate < team_avg × 0.70 (D-20)
JUNK_RATE_THRESHOLD = Decimal("0.25")  # 25% (D-20, ROADMAP SC#6; overrides REQUIREMENTS.md 20%)
SLOW_TOUCH_DROP_FACTOR = Decimal("0.25")  # 25% reduced close probability (D-06)
MIN_BASELINE_DAYS = 7  # Minimum baseline rows for trend-based rules (D-13)
CLOSE_RATE_FALLBACK = Decimal("0.15")  # Safe default when < 7 baseline rows


class AnomalyService:
    """Anomaly detection rule engine for Phase 4.

    Each detect_* method accepts pre-fetched data as optional kwargs (for unit tests)
    and fetches from DB when called without data (from run_all_rules()).

    run_all_rules() orchestrates: fetches junk_ids ONCE (D-11), calls each detect method.

    All monetary calculations use Decimal (D-19).
    No PII logged — only counts and rule names (T-04-03-01).
    Every DB query includes tenant_id filter (T-04-03-02).
    """

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id
        self._log = structlog.get_logger(__name__).bind(
            tenant_id=str(tenant_id), service="anomaly_service"
        )

    # ── Baseline value extractors ─────────────────────────────────────────────

    def _extract_close_rate(self, baseline_rows: list[dict]) -> Decimal:
        """Extract trailing close rate (conversion_o_to_c avg) from baseline rows.

        Uses all available non-None conversion_o_to_c values.
        Falls back to CLOSE_RATE_FALLBACK if no values available.
        """
        rates = [
            Decimal(str(row["conversion_o_to_c"]))
            for row in baseline_rows
            if row.get("conversion_o_to_c") is not None
        ]
        if rates:
            return sum(rates, Decimal("0")) / Decimal(str(len(rates)))
        return CLOSE_RATE_FALLBACK

    def _extract_avg_deal_size(self, baseline_rows: list[dict]) -> Decimal:
        """Extract avg_deal_size from baseline rows (first non-None value).

        Falls back to AVG_DEAL_SIZE_FALLBACK (20000 RON) if unavailable.
        """
        for row in baseline_rows:
            val = row.get("avg_deal_size")
            if val is not None:
                return Decimal(str(val))
        return AVG_DEAL_SIZE_FALLBACK

    # ── Private DB helpers ────────────────────────────────────────────────────

    async def _get_junk_ids(self, kpi_date: date) -> set[str]:
        """Fetch external_ids of junk leads for current tenant.

        Used by run_all_rules() to compute junk set once (D-11).

        T-04-03-02: Explicit tenant_id filter in WHERE clause.
        """
        from sqlalchemy import text  # deferred — fork-safe

        stmt = text(
            "SELECT external_id FROM v_mefi_leads_junk WHERE tenant_id = :tenant_id"
        ).bindparams(tenant_id=self._tenant_id)
        result = await self._session.execute(stmt)
        rows = result.fetchall()
        return {row[0] for row in rows}

    async def _db_fetch_trailing_metrics(self, kpi_date: date) -> list[dict]:
        """Fetch trailing 30-day daily_kpi baseline rows from DB."""
        from app.models.metrics.daily_kpi import DailyKpi  # deferred — fork-safe
        from sqlalchemy import select  # deferred — fork-safe

        start_date = kpi_date - timedelta(days=30)
        stmt = (
            select(
                DailyKpi.date,
                DailyKpi.conversion_l_to_v,
                DailyKpi.conversion_o_to_c,
                DailyKpi.avg_deal_size,
            )
            .where(
                DailyKpi.tenant_id == self._tenant_id,
                DailyKpi.date >= start_date,
                DailyKpi.date < kpi_date,
            )
            .order_by(DailyKpi.date.desc())
        )
        result = await self._session.execute(stmt)
        rows = result.fetchall()
        return [
            {
                "date": row.date,
                "conversion_l_to_v": row.conversion_l_to_v,
                "conversion_o_to_c": row.conversion_o_to_c,
                "avg_deal_size": row.avg_deal_size,
            }
            for row in rows
        ]

    async def _db_fetch_current_kpi(self, kpi_date: date) -> dict | None:
        """Fetch today's daily_kpi row from DB."""
        from app.models.metrics.daily_kpi import DailyKpi  # deferred — fork-safe
        from sqlalchemy import select  # deferred — fork-safe

        stmt = select(
            DailyKpi.date,
            DailyKpi.conversion_l_to_v,
            DailyKpi.conversion_o_to_c,
            DailyKpi.avg_deal_size,
        ).where(
            DailyKpi.tenant_id == self._tenant_id,
            DailyKpi.date == kpi_date,
        )
        result = await self._session.execute(stmt)
        row = result.fetchone()
        if row is None:
            return None
        return {
            "date": row.date,
            "conversion_l_to_v": row.conversion_l_to_v,
            "conversion_o_to_c": row.conversion_o_to_c,
            "avg_deal_size": row.avg_deal_size,
        }

    async def _db_fetch_slow_leads(self, kpi_date: date) -> list[dict]:
        """Fetch leads created on kpi_date for slow_first_touch from DB."""
        from sqlalchemy import text  # deferred — fork-safe

        stmt = text("""
            SELECT external_id, time_to_first_touch_minutes
            FROM v_mefi_leads_active
            WHERE tenant_id = :tenant_id
              AND created_date_local = :kpi_date
              AND lifecycle = 'active'
        """).bindparams(tenant_id=self._tenant_id, kpi_date=kpi_date)
        result = await self._session.execute(stmt)
        rows = result.fetchall()
        return [
            {
                "external_id": row[0],
                "time_to_first_touch_minutes": row[1],
            }
            for row in rows
        ]

    async def _db_fetch_stuck_leads(self, kpi_date: date) -> list[dict]:
        """Fetch leads in oferta stage stuck 15+ days from DB."""
        from sqlalchemy import text  # deferred — fork-safe

        cutoff = kpi_date - timedelta(days=STUCK_OFFER_DAYS)
        stmt = text("""
            SELECT external_id, last_status_changed_at, estimated_value
            FROM v_mefi_leads_active
            WHERE tenant_id = :tenant_id
              AND funnel_stage = 'oferta'
              AND last_status_changed_at < :cutoff
              AND lifecycle = 'active'
        """).bindparams(tenant_id=self._tenant_id, cutoff=cutoff)
        result = await self._session.execute(stmt)
        rows = result.fetchall()
        return [
            {
                "external_id": row[0],
                "last_status_changed_at": row[1],
                "estimated_value": Decimal(str(row[2])) if row[2] is not None else None,
            }
            for row in rows
        ]

    async def _db_fetch_salesperson_kpis(self, kpi_date: date) -> list[dict]:
        """Fetch salesperson_daily_kpi rows for kpi_date from DB."""
        from app.models.metrics.salesperson_kpi import SalespersonDailyKpi  # deferred — fork-safe
        from sqlalchemy import select  # deferred — fork-safe

        stmt = select(
            SalespersonDailyKpi.salesperson_external_id,
            SalespersonDailyKpi.conversion_o_to_c,
            SalespersonDailyKpi.contracts_count,
        ).where(
            SalespersonDailyKpi.tenant_id == self._tenant_id,
            SalespersonDailyKpi.date == kpi_date,
            SalespersonDailyKpi.conversion_o_to_c.is_not(None),
        )
        result = await self._session.execute(stmt)
        rows = result.fetchall()
        return [
            {
                "salesperson_external_id": row.salesperson_external_id,
                "conversion_o_to_c": Decimal(str(row.conversion_o_to_c)),
                "deals_won": row.contracts_count or 0,
            }
            for row in rows
        ]

    async def _db_fetch_junk_counts(self, kpi_date: date) -> tuple[int, int]:
        """Fetch (junk_count, total_leads) for kpi_date from DB."""
        from sqlalchemy import text  # deferred — fork-safe

        junk_stmt = text("""
            SELECT COUNT(*)
            FROM v_mefi_leads_junk
            WHERE tenant_id = :tenant_id
              AND created_date_local = :kpi_date
        """).bindparams(tenant_id=self._tenant_id, kpi_date=kpi_date)
        junk_result = await self._session.execute(junk_stmt)
        junk_count = int(junk_result.scalar() or 0)

        active_stmt = text("""
            SELECT COUNT(*)
            FROM v_mefi_leads_active
            WHERE tenant_id = :tenant_id
              AND created_date_local = :kpi_date
        """).bindparams(tenant_id=self._tenant_id, kpi_date=kpi_date)
        active_result = await self._session.execute(active_stmt)
        active_count = int(active_result.scalar() or 0)

        return junk_count, active_count + junk_count

    # ── Rule methods ──────────────────────────────────────────────────────────

    async def detect_slow_first_touch(
        self,
        kpi_date: date,
        slow_leads: list[dict] | None = None,
        baseline_rows: list[dict] | None = None,
        junk_ids: set[str] | None = None,
    ) -> dict | None:
        """Detect leads created on kpi_date with no contact in 5+ business hours.

        ANOM-01, ANOM-02: slow_first_touch fires when any lead created on kpi_date
        has time_to_first_touch_minutes > 300 (or NULL = no contact at all) after
        excluding junk leads (D-11).

        D-06 loss formula: count × avg_deal_size × 0.25 drop factor.
        D-14: checks yesterday-only leads, not chronic untouched leads.
        D-20: 300-minute (5 business hour) threshold.
        T-04-03-01: Log only counts — never log lead_ids.

        Args:
            kpi_date: The KPI calculation date (yesterday in daily pipeline).
            slow_leads: Pre-fetched leads or None (fetched from DB if None).
            baseline_rows: Pre-fetched trailing daily_kpi rows or None (fetched if None).
            junk_ids: Set of external_ids to exclude or None (empty set if None).

        Returns:
            DetectedProblem row dict or None if no qualifying leads.
        """
        if slow_leads is None:
            slow_leads = await self._db_fetch_slow_leads(kpi_date)
        if baseline_rows is None:
            baseline_rows = await self._db_fetch_trailing_metrics(kpi_date)
        if junk_ids is None:
            junk_ids = set()

        # Filter: exclude junk leads (D-11), qualify by threshold (D-20)
        # NULL time_to_first_touch = no contact at all = slow (D-14, ROADMAP SC#2)
        # time == 0 = adjusted for outside-hours creation — NOT slow (ROADMAP SC#2)
        qualifying = []
        for lead in slow_leads:
            if lead["external_id"] in junk_ids:
                continue
            touch_minutes = lead.get("time_to_first_touch_minutes")
            # time == 0 means outside-hours creation adjusted to 0 — not slow
            if touch_minutes == 0:
                continue
            # NULL = no contact at all → slow; > threshold → slow
            if touch_minutes is None or touch_minutes > SLOW_FIRST_TOUCH_THRESHOLD_MINUTES:
                qualifying.append(lead)

        if not qualifying:
            return None

        avg_deal_size = self._extract_avg_deal_size(baseline_rows)
        count = len(qualifying)
        estimated_loss = Decimal(str(count)) * avg_deal_size * SLOW_TOUCH_DROP_FACTOR

        # Max minutes for reporting (T-04-03-01: only aggregate value, not IDs)
        minutes_values = [
            lead["time_to_first_touch_minutes"]
            for lead in qualifying
            if lead.get("time_to_first_touch_minutes") is not None
        ]
        max_minutes = max(minutes_values) if minutes_values else 0
        worst_hours = float(max_minutes / 60) if max_minutes else None

        # T-04-03-01: Log only count, not lead IDs
        self._log.info(
            "anomaly.slow_first_touch.fired",
            kpi_date=str(kpi_date),
            count=count,
        )

        return {
            "tenant_id": self._tenant_id,
            "date": kpi_date,
            "rule_id": "slow_first_touch",
            "severity": "high",
            "metric": "time_to_first_touch_minutes",
            "current_value": Decimal(str(max_minutes)),
            "expected_value": Decimal(str(SLOW_FIRST_TOUCH_THRESHOLD_MINUTES)),
            "estimated_loss_ron": estimated_loss,
            "context_json": {
                "count": count,
                "lead_ids": [lead["external_id"] for lead in qualifying],
                "worst_hours_elapsed": worst_hours,
            },
        }

    async def detect_stuck_offer(
        self,
        kpi_date: date,
        stuck_leads: list[dict] | None = None,
        baseline_rows: list[dict] | None = None,
    ) -> dict | None:
        """Detect leads in 'oferta' stage with no status change for 15+ days.

        ANOM-03: stuck_offer fires when any active lead in oferta stage has not
        changed status for STUCK_OFFER_DAYS (15 days) — D-20 threshold.

        D-07 loss formula: sum(estimated_value) × trailing_close_rate.
        NULL estimated_value contributes 0 to sum (D-07 — no imputation).

        Args:
            kpi_date: The KPI calculation date.
            stuck_leads: Pre-fetched leads or None (fetched from DB if None).
            baseline_rows: Pre-fetched trailing daily_kpi rows or None (fetched if None).

        Returns:
            DetectedProblem row dict or None if no stuck leads.
        """
        if stuck_leads is None:
            stuck_leads = await self._db_fetch_stuck_leads(kpi_date)
        if baseline_rows is None:
            baseline_rows = await self._db_fetch_trailing_metrics(kpi_date)

        if not stuck_leads:
            return None

        close_rate = self._extract_close_rate(baseline_rows)

        # D-07: NULL estimated_value contributes 0 to sum (no imputation)
        total_value = Decimal("0")
        for lead in stuck_leads:
            val = lead.get("estimated_value")
            if val is not None:
                total_value += Decimal(str(val)) if not isinstance(val, Decimal) else val
        estimated_loss = total_value * close_rate

        # max_days_stuck for context
        max_days_stuck = 0
        for lead in stuck_leads:
            changed_at = lead.get("last_status_changed_at")
            if changed_at is not None:
                if hasattr(changed_at, "date"):
                    changed_date = changed_at.date()
                else:
                    changed_date = changed_at
                days_stuck = (kpi_date - changed_date).days
                if days_stuck > max_days_stuck:
                    max_days_stuck = days_stuck

        count = len(stuck_leads)

        self._log.info(
            "anomaly.stuck_offer.fired",
            kpi_date=str(kpi_date),
            count=count,
        )

        return {
            "tenant_id": self._tenant_id,
            "date": kpi_date,
            "rule_id": "stuck_offer",
            "severity": "medium",
            "metric": "days_since_status_change",
            "current_value": Decimal(str(max_days_stuck)),
            "expected_value": Decimal(str(STUCK_OFFER_DAYS)),
            "estimated_loss_ron": estimated_loss,
            "context_json": {
                "count": count,
                "lead_ids": [lead["external_id"] for lead in stuck_leads],
                "max_days_stuck": max_days_stuck,
            },
        }

    async def detect_showroom_traffic_drop(
        self,
        kpi_date: date,
        current_kpi: dict | None = None,
        baseline_rows: list[dict] | None = None,
    ) -> dict | None:
        """Detect significant drop in L→V (lead-to-showroom-visit) conversion.

        ANOM-04: fires when current conversion_l_to_v drops 35%+ below the
        trailing 30-day baseline (D-20 threshold, D-13 minimum 7-day baseline).

        Baseline minimum: 7 rows required (D-13). Fewer → rule skipped, returns None.

        Args:
            kpi_date: The KPI calculation date.
            current_kpi: Today's daily_kpi row dict or None (fetched from DB if None).
            baseline_rows: Pre-fetched trailing daily_kpi rows or None (fetched if None).

        Returns:
            DetectedProblem row dict or None if rule skips.
        """
        if baseline_rows is None:
            baseline_rows = await self._db_fetch_trailing_metrics(kpi_date)
        if current_kpi is None:
            current_kpi = await self._db_fetch_current_kpi(kpi_date)

        # D-13: minimum 7-day baseline required
        non_null_baseline = [
            row for row in baseline_rows
            if row.get("conversion_l_to_v") is not None
        ]
        if len(non_null_baseline) < MIN_BASELINE_DAYS:
            self._log.info(
                "anomaly.rule_skipped",
                rule="showroom_traffic_drop",
                reason="insufficient_baseline",
                available_days=len(non_null_baseline),
            )
            return None

        # No current data → skip
        if current_kpi is None or current_kpi.get("conversion_l_to_v") is None:
            return None

        current_rate = Decimal(str(current_kpi["conversion_l_to_v"]))
        baseline_values = [Decimal(str(row["conversion_l_to_v"])) for row in non_null_baseline]
        baseline_rate = sum(baseline_values, Decimal("0")) / Decimal(str(len(baseline_values)))

        # D-20: fires when current < baseline × 0.65 (i.e., drops more than 35%)
        if current_rate >= baseline_rate * SHOWROOM_DROP_THRESHOLD:
            return None

        estimated_loss = Decimal("0")  # fallback — visits data not available per-day

        self._log.info(
            "anomaly.showroom_traffic_drop.fired",
            kpi_date=str(kpi_date),
            current_rate=str(current_rate),
            baseline_rate=str(baseline_rate),
        )

        return {
            "tenant_id": self._tenant_id,
            "date": kpi_date,
            "rule_id": "showroom_traffic_drop",
            "severity": "medium",
            "metric": "conversion_l_to_v",
            "current_value": current_rate,
            "expected_value": baseline_rate,
            "estimated_loss_ron": estimated_loss,
            "context_json": {
                "baseline_days": len(non_null_baseline),
                "drop_pct": float((baseline_rate - current_rate) / baseline_rate * 100),
            },
        }

    async def detect_underperforming_salesperson(
        self,
        kpi_date: date,
        salesperson_kpis: list[dict] | None = None,
        baseline_rows: list[dict] | None = None,
    ) -> dict | None:
        """Detect salespeople with win rate 30%+ below team average.

        ANOM-05: fires when any salesperson's conversion_o_to_c (win rate)
        is more than 30% below the team average — D-20 threshold.

        Requires at least 2 salespeople (D-03 — cannot compute team avg with 1 person).

        D-05 loss formula: conservative proxy = len(underperforming) × avg_deal_size × 0.30.

        Args:
            kpi_date: The KPI calculation date.
            salesperson_kpis: Pre-fetched salesperson KPI rows or None (fetched if None).
            baseline_rows: Pre-fetched trailing daily_kpi rows or None (fetched if None).

        Returns:
            DetectedProblem row dict or None if no underperformers.
        """
        if salesperson_kpis is None:
            salesperson_kpis = await self._db_fetch_salesperson_kpis(kpi_date)
        if baseline_rows is None:
            baseline_rows = await self._db_fetch_trailing_metrics(kpi_date)

        # Cannot compute team avg with < 2 salespeople (D-03)
        if len(salesperson_kpis) < 2:
            return None

        win_rates = [
            Decimal(str(sp["conversion_o_to_c"])) if not isinstance(sp["conversion_o_to_c"], Decimal)
            else sp["conversion_o_to_c"]
            for sp in salesperson_kpis
        ]
        team_avg = sum(win_rates, Decimal("0")) / Decimal(str(len(win_rates)))

        # D-20: underperforming = win_rate < team_avg × 0.70 (30% below threshold)
        underperforming = []
        for i, sp in enumerate(salesperson_kpis):
            sp_rate = win_rates[i]
            if sp_rate < team_avg * UNDERPERFORMING_THRESHOLD:
                underperforming.append((sp, sp_rate))

        if not underperforming:
            return None

        avg_deal_size = self._extract_avg_deal_size(baseline_rows)
        # D-05 conservative proxy when per-day contracts not available
        estimated_loss = Decimal(str(len(underperforming))) * avg_deal_size * Decimal("0.30")

        details = [
            {
                "id": sp["salesperson_external_id"],
                "win_rate": float(sp_rate),
                "team_avg": float(team_avg),
            }
            for sp, sp_rate in underperforming
        ]

        self._log.info(
            "anomaly.underperforming_salesperson.fired",
            kpi_date=str(kpi_date),
            count=len(underperforming),
        )

        return {
            "tenant_id": self._tenant_id,
            "date": kpi_date,
            "rule_id": "underperforming_salesperson",
            "severity": "medium",
            "metric": "win_rate",
            "current_value": min(win_rates),
            "expected_value": team_avg * UNDERPERFORMING_THRESHOLD,
            "estimated_loss_ron": estimated_loss,
            "context_json": {
                "count": len(underperforming),
                "salesperson_ids": [sp["salesperson_external_id"] for sp, _ in underperforming],
                "details": details,
            },
        }

    async def detect_junk_lead_quality(
        self,
        kpi_date: date,
        total_leads: int | None = None,
        junk_count: int | None = None,
        baseline_rows: list[dict] | None = None,
    ) -> dict | None:
        """Detect excessive junk lead rate (25%+ of total leads).

        ANOM-06, ANOM-07: fires when junk_count / total >= JUNK_RATE_THRESHOLD (25%).
        D-20 locks threshold at 25% (overrides REQUIREMENTS.md baseline of 20%).
        ROADMAP SC#6 confirms 25% threshold.

        D-08 loss formula: junk_count × avg_deal_size × trailing_close_rate.

        Args:
            kpi_date: The KPI calculation date.
            total_leads: Total leads (active + junk) or None (fetched from DB if None).
            junk_count: Number of junk leads or None (fetched from DB if None).
            baseline_rows: Pre-fetched trailing daily_kpi rows or None (fetched if None).

        Returns:
            DetectedProblem row dict or None if junk rate below threshold.
        """
        if total_leads is None or junk_count is None:
            junk_count, total_leads = await self._db_fetch_junk_counts(kpi_date)
        if baseline_rows is None:
            baseline_rows = await self._db_fetch_trailing_metrics(kpi_date)

        if total_leads == 0:
            return None

        junk_rate = Decimal(str(junk_count)) / Decimal(str(total_leads))

        if junk_rate < JUNK_RATE_THRESHOLD:
            return None

        avg_deal_size = self._extract_avg_deal_size(baseline_rows)
        close_rate = self._extract_close_rate(baseline_rows)
        # D-08: junk_count × avg_deal_size × trailing_close_rate
        estimated_loss = Decimal(str(junk_count)) * avg_deal_size * close_rate

        self._log.info(
            "anomaly.junk_lead_quality.fired",
            kpi_date=str(kpi_date),
            junk_count=junk_count,
            total_leads=total_leads,
        )

        return {
            "tenant_id": self._tenant_id,
            "date": kpi_date,
            "rule_id": "junk_lead_quality",
            "severity": "low",
            "metric": "junk_rate",
            "current_value": junk_rate,
            "expected_value": JUNK_RATE_THRESHOLD,
            "estimated_loss_ron": estimated_loss,
            "context_json": {
                "count": junk_count,
                "total": total_leads,
                "junk_rate": float(junk_rate),
            },
        }

    # ── Orchestrator ──────────────────────────────────────────────────────────

    async def run_all_rules(self, kpi_date: date) -> list[dict]:
        """Run all 5 anomaly detection rules for the given date.

        Orchestrates rule execution:
        1. Computes junk_ids ONCE (D-11) and passes to non-junk rules
        2. Calls each detect method (methods fetch their own data from DB)
        3. Returns list of non-None results

        Args:
            kpi_date: The KPI calculation date to check for anomalies.

        Returns:
            List of DetectedProblem row dicts (empty if no anomalies found).

        D-09: This is the entry point called by the detect_anomalies Celery task.
        D-11: _get_junk_ids() called exactly once, result passed to non-junk rules.
        """
        self._log.info("anomaly.run_start", kpi_date=str(kpi_date))

        # D-11: compute junk IDs ONCE and pass to all non-junk rules
        junk_ids = await self._get_junk_ids(kpi_date)

        results: list[dict] = []

        # Run all 5 detect methods — each method fetches its own data from DB
        r = await self.detect_slow_first_touch(kpi_date=kpi_date, junk_ids=junk_ids)
        if r is not None:
            results.append(r)

        r = await self.detect_stuck_offer(kpi_date=kpi_date)
        if r is not None:
            results.append(r)

        r = await self.detect_showroom_traffic_drop(kpi_date=kpi_date)
        if r is not None:
            results.append(r)

        r = await self.detect_underperforming_salesperson(kpi_date=kpi_date)
        if r is not None:
            results.append(r)

        r = await self.detect_junk_lead_quality(kpi_date=kpi_date)
        if r is not None:
            results.append(r)

        self._log.info(
            "anomaly.run_complete",
            kpi_date=str(kpi_date),
            problems_found=len(results),
        )

        return results
