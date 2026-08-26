"""SQLAlchemy ORM models for MEFI CRM raw data storage.

Three tables are defined here:
  - raw_mefi_leads: nightly sync target for all MEFI lead records
  - mefi_lead_history: best-effort status change log between syncs (MEFI-06)
  - mefi_salespeople: salesperson roster discovered during sync (D-05, D-06)

All three models inherit TenantScopedMixin which provides:
  - id: UUID primary key (auto-generated)
  - tenant_id: UUID NOT NULL (every row scoped to a tenant — CLAUDE.md Principle #3)
  - created_at / updated_at: TIMESTAMPTZ via TimestampMixin

UNIQUE constraints are declared in __table_args__ so the ORM is aware of them
for the UPSERT conflict target resolution, even though the actual DB constraints
are created via the Alembic migration 003_mefi_schema.py.

Phase 2 Plan 01 — schema foundation for all subsequent MEFI ETL plans.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, Integer, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TIMESTAMPTZ, Base, TenantScopedMixin


class RawMefiLead(Base, TenantScopedMixin):
    """Raw MEFI lead record — one row per MEFI lead per tenant.

    All MEFI leads regardless of lifecycle (active/lost/junk) are stored here.
    Downstream conformed views filter by lifecycle:
      - v_mefi_leads_active: lifecycle IN ('active', 'lost') — used by metrics
      - v_mefi_leads_junk: lifecycle = 'junk' — used by anomaly detection

    CLAUDE.md Principle #3: tenant_id on every row — enforced here and in the
    Alembic migration UNIQUE(tenant_id, external_id) constraint.

    UPSERT conflict target: (tenant_id, external_id) — see migration 003.
    """

    __tablename__ = "raw_mefi_leads"

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "external_id",
            name="uq_raw_mefi_leads_tenant_external",
        ),
    )

    # MEFI lead identifier — TEXT (MEFI uses string IDs in the API response)
    # NOT NULL — required for the UPSERT conflict target (D-12, MEFI-02)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)

    # ── MEFI standard status and source fields ────────────────────────────────
    status_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_name: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Lifecycle bucket: 'active' | 'lost' | 'junk' — derived from MEFI status
    # NOT NULL — every lead must have a lifecycle classification (D-01)
    lifecycle: Mapped[str] = mapped_column(Text, nullable=False)

    # Salesperson assignment
    assigned_to_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assigned_to_name: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Revenue amount — NUMERIC(12,2) to avoid float precision loss (DATA-04)
    # Python type hint uses Decimal to match the NUMERIC precision guarantee
    estimated_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    # Lead priority: 'low' | 'medium' | 'high' (from enums.md)
    priority: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Duplicate flag — MEFI may mark leads as duplicates; default False
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ── Timestamps from MEFI (stored as-is, UTC) ──────────────────────────────
    # Views add AT TIME ZONE 'Europe/Bucharest' variants (DATA-03)
    created_at_source: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)
    last_contact_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)
    status_changed_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)

    # ── Extracted custom fields (DATA-02) ─────────────────────────────────────
    # Promoted from custom_fields[] array for indexing and query performance.
    # Source field IDs documented in docs/api-references/mefi/custom-fields.md

    # form-cf-14: Showroom — 'Brașov' | 'București' | 'Cluj'
    showroom: Mapped[str | None] = mapped_column(Text, nullable=True)

    # form-cf-20: Ofertat — '✅DA' → True, '❌NU' → False, absent → NULL
    # NULL means field was not set at all (different from "not sent")
    offer_sent_flag: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # form-cf-38..41: UTM marketing attribution parameters
    utm_source: Mapped[str | None] = mapped_column(Text, nullable=True)  # form-cf-38
    utm_campaign: Mapped[str | None] = mapped_column(Text, nullable=True)  # form-cf-39
    utm_content: Mapped[str | None] = mapped_column(Text, nullable=True)  # form-cf-40
    utm_medium: Mapped[str | None] = mapped_column(Text, nullable=True)  # form-cf-41

    # ── Raw preservation ──────────────────────────────────────────────────────
    # Full custom_fields array stored for schema evolution (new fields added in MEFI
    # appear automatically here without a schema migration)
    custom_fields_raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Complete original MEFI API response for debugging and data recovery
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # When this row was last written by our sync task
    synced_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)


class MefiLeadHistory(Base, TenantScopedMixin):
    """Best-effort status change log for MEFI leads between nightly syncs.

    Each row records a detected status transition: the previous status (from_*)
    and the new status (to_*) as observed during a sync run.

    MEFI-06: This is "best-effort" — if a lead cycles through multiple statuses
    between two syncs, only the net change (old stored value → new API value) is
    captured. Intermediate states are lost.

    No UNIQUE constraint — multiple history rows per lead are expected and valid
    (one per detected change across multiple syncs).

    Phase 3+ metrics use this table for "ever reached" funnel stage computation.
    See: NOTE in v_mefi_leads_active view — current view uses status_id only.
    """

    __tablename__ = "mefi_lead_history"

    # Reference back to raw_mefi_leads — stored as TEXT to match external_id type
    # NOT NULL — every history row must link to a lead
    lead_external_id: Mapped[str] = mapped_column(Text, nullable=False)

    # Previous status (NULL for new leads — no prior recorded status)
    from_status_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    from_status_name: Mapped[str | None] = mapped_column(Text, nullable=True)

    # New status after the detected change
    # NOT NULL — we always know what the lead changed TO
    to_status_id: Mapped[int] = mapped_column(Integer, nullable=False)
    to_status_name: Mapped[str | None] = mapped_column(Text, nullable=True)

    # When the change was detected (our sync time, not MEFI event time)
    # NOT NULL — required for temporal ordering of history events
    changed_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)


class MefiSalesperson(Base, TenantScopedMixin):
    """Salesperson roster auto-discovered from MEFI lead assignment data.

    Populated by the sync task (D-05): every unique assigned_to_id seen in leads
    gets an upserted row here via INSERT ... ON CONFLICT DO NOTHING.

    After first sync, Sofa Belle / developer manually sets:
      - is_active = True for the 6 active salespeople (others may be former staff)
      - showroom = 'Brașov' | 'București' | 'Cluj' for each salesperson

    Phase 3 metrics filter on is_active = True when computing per-salesperson KPIs.
    Known salesperson IDs: see docs/api-references/mefi/enums.md (D-06).

    UPSERT conflict target: (tenant_id, external_id)
    """

    __tablename__ = "mefi_salespeople"

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "external_id",
            name="uq_mefi_salespeople_tenant_external",
        ),
    )

    # MEFI user ID — INTEGER (MEFI user IDs are integers, not UUIDs — see enums.md)
    # NOT NULL — required for the UPSERT conflict target
    external_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Full name from MEFI (e.g. "Palega Andrei", "Roibu Valeria")
    # NOT NULL — we always receive the name in MEFI API response
    name: Mapped[str] = mapped_column(Text, nullable=False)

    # Manually set by admin after first sync — NULL until confirmed (D-06)
    # True = active salesperson, False = former/inactive, NULL = not yet determined
    is_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Manually set by admin after first sync — NULL until confirmed (D-06)
    # Values: 'Brașov' | 'București' | 'Cluj' | NULL (unset)
    showroom: Mapped[str | None] = mapped_column(Text, nullable=True)
