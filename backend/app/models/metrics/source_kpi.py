from __future__ import annotations

"""SQLAlchemy ORM model for source_daily_kpi metric table.

One row per tenant per source category per calendar day — per-source KPIs.
Inherits TenantScopedMixin (id, tenant_id, created_at, updated_at).
UPSERT conflict target: (tenant_id, source, date) — 3-column key (Pitfall 5).

Phase 3 Plan 02 — schema foundation for source metric service in Plan 03.

Columns follow SPEC.md §7 DDL exactly.

Per D-04: source TEXT uses funnel_config category names (not SPEC.md generic names).
Seven rows per day per tenant: mail_fb_ig | telefon | whatsapp | site | designer | alte | google
Per D-09: source is TEXT, not an enum constraint — deferred to Iteration 4.

Pitfall 5: UNIQUE constraint is (tenant_id, source, date) — 3 columns.
Using only (tenant_id, date) as conflict target causes UniqueViolationError
on insert of the second source category.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, Integer, Numeric, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin, TIMESTAMPTZ


class SourceDailyKpi(Base, TenantScopedMixin):
    """One row per tenant per source category per calendar day — per-source KPIs.

    UPSERT conflict target: (tenant_id, source, date) — 3-column key (Pitfall 5).
    source TEXT uses funnel_config category names (D-04, D-09).

    T-03-02-02: View including tenant_id — downstream queries MUST filter by tenant_id.
    T-03-02-04: All money cols NUMERIC(12,2), rates NUMERIC(5,4) — no FLOAT (D-16).
    """

    __tablename__ = "source_daily_kpi"

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "source",
            "date",
            name="uq_source_daily_kpi_tenant_source_date",
        ),
    )

    # Source category — TEXT (D-09: not enum; funnel_config category name)
    # One of: mail_fb_ig | telefon | whatsapp | site | designer | alte | google (D-04)
    # NOT NULL — every row must have a source category
    source: Mapped[str] = mapped_column(Text, nullable=False)

    # Business date — NOT NULL; part of 3-column UPSERT conflict target
    date: Mapped[date] = mapped_column(Date, nullable=False)

    # ── Lead volume ───────────────────────────────────────────────────────────
    leads: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── Ad spend (nullable — populated Iteration 2) ───────────────────────────
    ad_spend: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    # ── Efficiency metrics (nullable — populated Iteration 2) ────────────────
    cpl: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    cac: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    roas: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)

    # ── Funnel stage counts ───────────────────────────────────────────────────
    visits: Mapped[int | None] = mapped_column(Integer, nullable=True)
    offers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deals_won: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── Revenue — NUMERIC(12,2) per DATA-04 ──────────────────────────────────
    revenue: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    # ── Conversion rate — NUMERIC(5,4) ───────────────────────────────────────
    conversion_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)

    # ── Calculation timestamp ─────────────────────────────────────────────────
    calculated_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default="now()", nullable=False
    )
