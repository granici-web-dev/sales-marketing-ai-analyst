from __future__ import annotations

"""SQLAlchemy ORM model for salesperson_daily_kpi metric table.

One row per tenant per salesperson per calendar day — per-rep KPIs.
Inherits TenantScopedMixin (id, tenant_id, created_at, updated_at).
UPSERT conflict target: (tenant_id, salesperson_external_id, date) — 3-column key.

Phase 3 Plan 02 — schema foundation for salesperson metric service in Plan 03.

Columns follow SPEC.md §7 DDL exactly, plus Phase 3 extension:
  - data_completeness_pct NUMERIC(5,2) — Schema Gap 2, METR-06
  - Not in SPEC.md §7; added by migration 004.

Per D-17: only rows for is_active=True salespeople are emitted.
Per D-05: avg_time_to_first_touch_minutes is NULL when no mefi_lead_history rows exist.
Per D-06: avg_time_to_first_touch_minutes uses business-hours-adjusted calculation.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, Integer, Numeric, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin, TIMESTAMPTZ


class SalespersonDailyKpi(Base, TenantScopedMixin):
    """One row per tenant per salesperson per calendar day — per-rep KPIs.

    UPSERT conflict target: (tenant_id, salesperson_external_id, date).
    data_completeness_pct NOT in SPEC.md §7 — added by migration 004 (METR-06).

    T-03-02-04: All money cols NUMERIC(12,2), rates NUMERIC(5,4) — no FLOAT (D-16).
    """

    __tablename__ = "salesperson_daily_kpi"

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "salesperson_external_id",
            "date",
            name="uq_salesperson_daily_kpi_tenant_sp_date",
        ),
    )

    # Salesperson identifier (TEXT — matches MefiSalesperson.external_id stored as int,
    # but stored as TEXT here for flexibility and consistency with lead.assigned_to_id usage)
    salesperson_external_id: Mapped[str] = mapped_column(Text, nullable=False)

    # Business date — NOT NULL; part of 3-column UPSERT conflict target
    date: Mapped[date] = mapped_column(Date, nullable=False)

    # ── Lead funnel metrics ───────────────────────────────────────────────────
    leads_assigned: Mapped[int | None] = mapped_column(Integer, nullable=True)
    leads_contacted: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Business-hours-adjusted minutes from lead creation to first history row (D-06).
    # NULL when no mefi_lead_history rows exist for leads in this salesperson's portfolio (D-05).
    avg_time_to_first_touch_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── Funnel stage counts ───────────────────────────────────────────────────
    visits_conducted: Mapped[int | None] = mapped_column(Integer, nullable=True)
    offers_sent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deals_won: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deals_lost: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── Revenue — NUMERIC(12,2) per DATA-04 ──────────────────────────────────
    revenue: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    # ── Conversion rates — NUMERIC(5,4) per SPEC.md §7 ───────────────────────
    conversion_l_to_v: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    conversion_v_to_o: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    conversion_o_to_c: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    conversion_l_to_c: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)

    # ── Revenue per deal ─────────────────────────────────────────────────────
    avg_deal_size: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    # ── Calls (nullable — future telephony integration) ───────────────────────
    calls_made: Mapped[int | None] = mapped_column(Integer, nullable=True)
    calls_answered: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_call_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_sentiment_score: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)

    # ── data_completeness_pct (Schema Gap 2 — METR-06, NOT in SPEC.md §7) ────
    # % of leads with estimated_value set: COUNT(estimated_value) / COUNT(*) * 100
    # Range: 0.00–100.00 per Assumption A3
    # NULL when salesperson has no leads in this period
    data_completeness_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)

    # ── Calculation timestamp ─────────────────────────────────────────────────
    calculated_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default="now()", nullable=False
    )
