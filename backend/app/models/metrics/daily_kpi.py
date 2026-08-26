"""SQLAlchemy ORM model for daily_kpi metric table.

One row per tenant per calendar day — aggregate daily KPIs.
Inherits TenantScopedMixin (id, tenant_id, created_at, updated_at).
UPSERT conflict target: (tenant_id, date) — see migration 004.

Phase 3 Plan 02 — schema foundation for metric services in Plan 03.

Columns follow SPEC.md §7 DDL exactly, plus Phase 3 extensions:
  - WoW/MoM delta columns (8 metrics × 2 = 16 columns) — Schema Gap 1, METR-05
  - Not in SPEC.md §7; added by migration 004.

Ad-spend, GA4, and calls columns are NULLABLE — populated by future phases.
visits_count/offers_count/contracts_count are NOT NULL with server_default=0.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, Integer, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TIMESTAMPTZ, Base, TenantScopedMixin


class DailyKpi(Base, TenantScopedMixin):
    """One row per tenant per calendar day — aggregate daily KPIs.

    UPSERT conflict target: (tenant_id, date).
    Ad-spend, GA4, and calls columns are NULLABLE — populated by future phases.
    WoW/MoM delta columns are NOT in SPEC.md §7; added by migration 004 (METR-05).

    T-03-02-04: All money cols NUMERIC(12,2), rates NUMERIC(5,4),
    deltas NUMERIC(8,4) — no FLOAT anywhere (D-16).
    """

    __tablename__ = "daily_kpi"

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "date",
            name="uq_daily_kpi_tenant_date",
        ),
    )

    # Business date — NOT NULL; UPSERT conflict target with tenant_id
    date: Mapped[date] = mapped_column(Date, nullable=False)

    # ── Ad spend (nullable — populated Iteration 2) ───────────────────────────
    spend_meta: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    spend_google: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    spend_tiktok: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    spend_digital_total: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    # ── GA4 (nullable — populated Iteration 3) ───────────────────────────────
    web_sessions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    web_conversion_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)

    # ── Lead volume by source (nullable — 0 means "calculated but zero") ─────
    leads_mail_fb_ig: Mapped[int | None] = mapped_column(Integer, nullable=True)
    leads_telefon: Mapped[int | None] = mapped_column(Integer, nullable=True)
    leads_whatsapp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    leads_site: Mapped[int | None] = mapped_column(Integer, nullable=True)
    leads_designer: Mapped[int | None] = mapped_column(Integer, nullable=True)
    leads_alte: Mapped[int | None] = mapped_column(Integer, nullable=True)
    leads_total: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── CPL (nullable — populated Iteration 2) ───────────────────────────────
    cpl_overall: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    cpl_by_channel: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ── Funnel counts ─────────────────────────────────────────────────────────
    # visits_count is NULL when MEFI history is unavailable (KI-03 / migration 006).
    visits_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    offers_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    contracts_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    # ── Conversion rates — NUMERIC(8,4) — widened from NUMERIC(5,4) in migration 005
    # Daily counts are cohort-independent: e.g. 13 offers / 1 visit = 13.0 is valid.
    conversion_l_to_v: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    conversion_v_to_o: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    conversion_l_to_o: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    conversion_o_to_c: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    conversion_l_to_c: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)

    # ── Revenue — NUMERIC(12,2) per DATA-04 ──────────────────────────────────
    revenue: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    avg_deal_size: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    avg_deal_size_per_day: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    cost_acquisition_contract: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    # ── CAC / ROAS (nullable — Iteration 2) ──────────────────────────────────
    cac: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    roas: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)

    # ── Calls (nullable — future telephony integration) ───────────────────────
    calls_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    calls_answered: Mapped[int | None] = mapped_column(Integer, nullable=True)
    calls_missed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_call_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_sentiment_score: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)

    # ── WoW / MoM delta columns (Schema Gap 1 — METR-05, NOT in SPEC.md §7) ─
    # 8 metrics × 2 deltas = 16 columns
    # NUMERIC(8,4) — range covers [-1, +infinity) as fractional change
    # NULL when prior-period row is absent (D-11 — never impute zero)
    leads_total_wow_delta: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    leads_total_mom_delta: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)

    conversion_l_to_v_wow_delta: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    conversion_l_to_v_mom_delta: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)

    conversion_v_to_o_wow_delta: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    conversion_v_to_o_mom_delta: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)

    conversion_l_to_o_wow_delta: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    conversion_l_to_o_mom_delta: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)

    conversion_o_to_c_wow_delta: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    conversion_o_to_c_mom_delta: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)

    conversion_l_to_c_wow_delta: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    conversion_l_to_c_mom_delta: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)

    revenue_wow_delta: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    revenue_mom_delta: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)

    avg_deal_size_wow_delta: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    avg_deal_size_mom_delta: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)

    # ── Calculation timestamp ─────────────────────────────────────────────────
    calculated_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default="now()", nullable=False
    )
