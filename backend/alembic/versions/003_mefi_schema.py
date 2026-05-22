from __future__ import annotations

"""Create MEFI tables, conformed views, and seed funnel_config.

Revision ID: 003
Revises: 002
Create Date: 2026-05-22

Creates the MEFI ETL schema foundation for Phase 2:

  1. ADD COLUMN funnel_config JSONB to tenants table
     (funnel_config was NOT present in 001_base_tables.py — must add here)

  2. CREATE TABLE raw_mefi_leads
     Nightly MEFI lead sync target. UPSERT conflict target: (tenant_id, external_id).
     Custom field columns extracted for performance: showroom, offer_sent_flag, UTM fields.
     estimated_value is NUMERIC(12,2) — never float (DATA-04).

  3. CREATE TABLE mefi_lead_history
     Best-effort status change log (MEFI-06). Records status transitions detected
     between nightly syncs. No UNIQUE constraint — multiple rows per lead are expected.

  4. CREATE TABLE mefi_salespeople
     Salesperson roster auto-discovered from lead assigned_to data (D-05).
     UPSERT conflict target: (tenant_id, external_id). is_active/showroom NULL until
     manually set by admin after first sync (D-06).

  5. CREATE INDEXes for query performance

  6. CREATE UNIQUE CONSTRAINTs for UPSERT conflict targets

  7. CREATE OR REPLACE VIEW v_mefi_leads_active
     Filters lifecycle IN ('active', 'lost') + adds computed funnel columns:
     reached_visit, reached_offer, reached_contract, created_at_local,
     status_changed_at_local (AT TIME ZONE 'Europe/Bucharest' — DATA-03).
     NOTE: reached_* use current status_id only (Phase 2). True "ever reached"
     requires mefi_lead_history join — planned for Phase 3 metrics.

  8. CREATE OR REPLACE VIEW v_mefi_leads_junk
     Filters lifecycle = 'junk' — for anomaly rule ANOM-07.

  9. UPDATE tenants SET funnel_config = JSONB WHERE slug = 'sofa-belle'
     Idempotent seed: AND funnel_config IS NULL prevents overwriting manual edits (T-02-01).
     FUNNEL_CONFIG matches D-08 from 02-CONTEXT.md exactly.

Security notes:
  T-02-01: funnel_config seed is idempotent (AND funnel_config IS NULL guard)
  T-02-02: Views include tenant_id — services must always filter WHERE tenant_id = :tid
  T-02-03: NUMERIC(12,2) prevents float precision loss (DATA-04)
"""

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# ── Revision identifiers ──────────────────────────────────────────────────────

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ── Funnel configuration (D-08 from 02-CONTEXT.md) ───────────────────────────
# This JSONB blob is seeded into tenants.funnel_config for Sofa Belle.
# All tenant-specific MEFI ID mappings live here — never hardcoded in service code.
#
# funnel_stages: MEFI status IDs that define each funnel stage
# source_categories: groups MEFI source IDs into analytics categories
# offer_sent_flag_field: custom field key for alternative offer-sent detection
# showroom_field: custom field key for showroom assignment
# junk_statuses: MEFI status IDs that classify leads as junk (lifecycle='junk')
# lifecycle_filter: all lifecycle values to store in raw_mefi_leads (D-01)

FUNNEL_CONFIG = {
    "funnel_stages": {
        "visit": [17],      # status_id 17 = SHOWROOM
        "offer": [3],       # status_id 3 = Ofertat
        "contract": [1],    # status_id 1 = Clienți (WON)
    },
    "offer_sent_flag_field": "form-cf-20",
    "source_categories": {
        "mail_fb_ig": [2, 11],          # 2=Meta ADS, 11=Mail
        "telefon": [10],                 # 10=Telefon
        "whatsapp": [9],                 # 9=WhatsApp
        "site": [6],                     # 6=Site
        "designer": [],                  # DESIGNER is a status (24), not a source
        "alte": [3, 4, 5, 7, 12, 13],   # Recomandare, Teren, Showroom, Arhitect, Colaborare, Client Fidel
    },
    "lifecycle_filter": ["active", "lost", "junk"],
    "showroom_field": "form-cf-14",
    "junk_statuses": [23],  # status_id 23 = IRELEVANT
}

# ── Conformed view DDL ────────────────────────────────────────────────────────

# View: v_mefi_leads_active
# Filters junk leads, adds funnel stage boolean columns and Bucharest-local timestamps.
# T-02-02: tenant_id included — downstream services MUST filter by tenant_id.
# DATA-03: AT TIME ZONE 'Europe/Bucharest' for all date grouping operations.
# Explicit column list — no SELECT * (CLAUDE.md: never use SELECT *)
V_MEFI_LEADS_ACTIVE = """
CREATE OR REPLACE VIEW v_mefi_leads_active AS
SELECT
    -- TenantScopedMixin columns
    r.tenant_id,
    r.id,
    r.created_at,
    r.updated_at,

    -- MEFI standard fields
    r.external_id,
    r.status_id,
    r.status_name,
    r.source_id,
    r.source_name,
    r.lifecycle,
    r.assigned_to_id,
    r.assigned_to_name,
    r.estimated_value,
    r.priority,
    r.is_duplicate,

    -- MEFI timestamps (UTC storage)
    r.created_at_source,
    r.last_contact_at,
    r.status_changed_at,

    -- Extracted custom fields (DATA-02)
    r.showroom,
    r.offer_sent_flag,
    r.utm_source,
    r.utm_campaign,
    r.utm_content,
    r.utm_medium,

    -- Raw preservation
    r.custom_fields_raw,
    r.raw_payload,
    r.synced_at,

    -- Computed: Bucharest-local timestamps (DATA-03)
    -- AT TIME ZONE converts TIMESTAMPTZ → TIMESTAMP in the named zone
    r.created_at_source AT TIME ZONE 'Europe/Bucharest' AS created_at_local,
    r.status_changed_at AT TIME ZONE 'Europe/Bucharest' AS status_changed_at_local,

    -- Computed: funnel stage flags (D-09 "ever reached" approximation)
    -- NOTE: reached_* columns use current status_id only (Phase 2 limitation).
    -- True "ever reached" requires mefi_lead_history join — planned for Phase 3.
    -- Visit: lead is at SHOWROOM stage OR has progressed beyond it
    (r.status_id = 17 OR r.status_id IN (3, 1)) AS reached_visit,

    -- Offer: lead has Ofertat status OR offer_sent_flag set OR has progressed to contract
    (r.status_id = 3 OR r.offer_sent_flag = true OR r.status_id = 1) AS reached_offer,

    -- Contract: lead is a Clienți (WON deal)
    (r.status_id = 1) AS reached_contract

FROM raw_mefi_leads r
WHERE r.lifecycle IN ('active', 'lost')
"""

# View: v_mefi_leads_junk
# Filters for junk/spam/irrelevant leads only.
# Used by anomaly rule ANOM-07: alert if junk% > 20% of total leads.
# Explicit column list — no SELECT * (CLAUDE.md: never use SELECT *)
V_MEFI_LEADS_JUNK = """
CREATE OR REPLACE VIEW v_mefi_leads_junk AS
SELECT
    r.tenant_id,
    r.id,
    r.created_at,
    r.updated_at,
    r.external_id,
    r.status_id,
    r.status_name,
    r.source_id,
    r.source_name,
    r.lifecycle,
    r.assigned_to_id,
    r.assigned_to_name,
    r.estimated_value,
    r.priority,
    r.is_duplicate,
    r.created_at_source,
    r.last_contact_at,
    r.status_changed_at,
    r.showroom,
    r.offer_sent_flag,
    r.utm_source,
    r.utm_campaign,
    r.utm_content,
    r.utm_medium,
    r.custom_fields_raw,
    r.raw_payload,
    r.synced_at
FROM raw_mefi_leads r
WHERE r.lifecycle = 'junk'
"""


def upgrade() -> None:
    # ── Step 1: Add funnel_config column to tenants ───────────────────────────
    # funnel_config is ABSENT from migration 001 — must add here before UPDATE seed.
    # Nullable: existing tenants keep NULL until the UPDATE seed below sets it.
    op.add_column(
        "tenants",
        sa.Column("funnel_config", JSONB, nullable=True),
    )

    # ── Step 2: Create raw_mefi_leads table ───────────────────────────────────
    op.create_table(
        "raw_mefi_leads",
        # TenantScopedMixin columns (replicated from ORM base — migration is standalone DDL)
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),

        # MEFI identifier — NOT NULL (UPSERT conflict target)
        sa.Column("external_id", sa.Text, nullable=False),

        # MEFI standard fields
        sa.Column("status_id", sa.Integer, nullable=True),
        sa.Column("status_name", sa.Text, nullable=True),
        sa.Column("source_id", sa.Integer, nullable=True),
        sa.Column("source_name", sa.Text, nullable=True),

        # Lifecycle bucket — NOT NULL (active/lost/junk)
        sa.Column("lifecycle", sa.Text, nullable=False),

        # Salesperson assignment
        sa.Column("assigned_to_id", sa.Integer, nullable=True),
        sa.Column("assigned_to_name", sa.Text, nullable=True),

        # Revenue — NUMERIC(12,2), never float (DATA-04, T-02-03)
        sa.Column("estimated_value", sa.Numeric(12, 2), nullable=True),

        sa.Column("priority", sa.Text, nullable=True),
        sa.Column(
            "is_duplicate",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),

        # MEFI source timestamps (UTC)
        sa.Column("created_at_source", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_contact_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("status_changed_at", sa.TIMESTAMP(timezone=True), nullable=True),

        # Extracted custom fields (DATA-02)
        sa.Column("showroom", sa.Text, nullable=True),            # form-cf-14
        sa.Column("offer_sent_flag", sa.Boolean, nullable=True),  # form-cf-20
        sa.Column("utm_source", sa.Text, nullable=True),          # form-cf-38
        sa.Column("utm_campaign", sa.Text, nullable=True),        # form-cf-39
        sa.Column("utm_content", sa.Text, nullable=True),         # form-cf-40
        sa.Column("utm_medium", sa.Text, nullable=True),          # form-cf-41

        # Raw preservation
        sa.Column("custom_fields_raw", JSONB, nullable=True),
        sa.Column("raw_payload", JSONB, nullable=True),
        sa.Column("synced_at", sa.TIMESTAMP(timezone=True), nullable=True),

        # FK to tenants
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_raw_mefi_leads_tenant_id",
        ),
    )

    # ── Step 3: Create mefi_lead_history table ────────────────────────────────
    op.create_table(
        "mefi_lead_history",
        # TenantScopedMixin columns
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),

        # Lead reference — TEXT to match raw_mefi_leads.external_id type
        sa.Column("lead_external_id", sa.Text, nullable=False),

        # Previous status (NULL for new leads with no prior recorded status)
        sa.Column("from_status_id", sa.Integer, nullable=True),
        sa.Column("from_status_name", sa.Text, nullable=True),

        # New status after detected change — NOT NULL (we always know the destination)
        sa.Column("to_status_id", sa.Integer, nullable=False),
        sa.Column("to_status_name", sa.Text, nullable=True),

        # When change was detected (our sync time, not MEFI event time)
        sa.Column("changed_at", sa.TIMESTAMP(timezone=True), nullable=False),

        # FK to tenants
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_mefi_lead_history_tenant_id",
        ),
    )

    # ── Step 4: Create mefi_salespeople table ─────────────────────────────────
    op.create_table(
        "mefi_salespeople",
        # TenantScopedMixin columns
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),

        # MEFI user ID — INTEGER (enums.md: user IDs are integers, not UUIDs)
        sa.Column("external_id", sa.Integer, nullable=False),

        sa.Column("name", sa.Text, nullable=False),

        # Manually set by admin after first sync — NULL = not yet determined (D-06)
        sa.Column("is_active", sa.Boolean, nullable=True),
        sa.Column("showroom", sa.Text, nullable=True),

        # FK to tenants
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_mefi_salespeople_tenant_id",
        ),
    )

    # ── Step 5: Create indexes ────────────────────────────────────────────────
    # Primary lookup index on tenant_id (standard for all tenant-scoped tables)
    op.create_index(
        "ix_raw_mefi_leads_tenant_id",
        "raw_mefi_leads",
        ["tenant_id"],
    )
    # Incremental sync key — fetch leads changed since last sync
    op.create_index(
        "ix_raw_mefi_leads_status_changed_at",
        "raw_mefi_leads",
        ["status_changed_at"],
    )
    # Showroom dimension — for per-showroom metrics grouping
    op.create_index(
        "ix_raw_mefi_leads_showroom",
        "raw_mefi_leads",
        ["showroom"],
    )
    # UTM source dimension — for marketing attribution grouping
    op.create_index(
        "ix_raw_mefi_leads_utm_source",
        "raw_mefi_leads",
        ["utm_source"],
    )
    # mefi_lead_history: lookup by tenant + lead (for history JOIN in Phase 3)
    op.create_index(
        "ix_mefi_lead_history_tenant_lead",
        "mefi_lead_history",
        ["tenant_id", "lead_external_id"],
    )
    # mefi_salespeople: lookup by tenant + MEFI user ID
    op.create_index(
        "ix_mefi_salespeople_tenant_external",
        "mefi_salespeople",
        ["tenant_id", "external_id"],
    )

    # ── Step 6: Create UNIQUE constraints ─────────────────────────────────────
    # UPSERT conflict target for raw_mefi_leads (MEFI-02, D-12)
    op.create_unique_constraint(
        "uq_raw_mefi_leads_tenant_external",
        "raw_mefi_leads",
        ["tenant_id", "external_id"],
    )
    # UPSERT conflict target for mefi_salespeople (D-05)
    op.create_unique_constraint(
        "uq_mefi_salespeople_tenant_external",
        "mefi_salespeople",
        ["tenant_id", "external_id"],
    )

    # ── Step 7: Create v_mefi_leads_active view ───────────────────────────────
    # Filters junk, adds funnel booleans and Bucharest-local timestamps.
    # T-02-02: view includes tenant_id — services must filter by tenant_id.
    op.execute(V_MEFI_LEADS_ACTIVE)

    # ── Step 8: Create v_mefi_leads_junk view ─────────────────────────────────
    op.execute(V_MEFI_LEADS_JUNK)

    # ── Step 9: Seed funnel_config for Sofa Belle ─────────────────────────────
    # Idempotent: AND funnel_config IS NULL ensures running upgrade head twice
    # does NOT overwrite manually edited configs (T-02-01).
    # CAST(:cfg AS jsonb) instead of :cfg::jsonb — SQLAlchemy's text() parser
    # doesn't recognise a named bindparam when '::' immediately follows the
    # colon (it mistakes the cast operator for part of the param name and
    # raises "doesn't define a bound parameter named 'cfg'").
    op.execute(
        sa.text(
            """
            UPDATE tenants
            SET funnel_config = CAST(:cfg AS jsonb)
            WHERE slug = 'sofa-belle'
              AND funnel_config IS NULL
            """
        ).bindparams(cfg=json.dumps(FUNNEL_CONFIG))
    )


def downgrade() -> None:
    # Drop views first (depend on raw_mefi_leads)
    op.execute("DROP VIEW IF EXISTS v_mefi_leads_junk")
    op.execute("DROP VIEW IF EXISTS v_mefi_leads_active")

    # Drop indexes (before tables)
    op.drop_index("ix_mefi_salespeople_tenant_external", table_name="mefi_salespeople")
    op.drop_index("ix_mefi_lead_history_tenant_lead", table_name="mefi_lead_history")
    op.drop_index("ix_raw_mefi_leads_utm_source", table_name="raw_mefi_leads")
    op.drop_index("ix_raw_mefi_leads_showroom", table_name="raw_mefi_leads")
    op.drop_index("ix_raw_mefi_leads_status_changed_at", table_name="raw_mefi_leads")
    op.drop_index("ix_raw_mefi_leads_tenant_id", table_name="raw_mefi_leads")

    # Drop tables in reverse creation order (respect FK constraints)
    op.drop_table("mefi_salespeople")
    op.drop_table("mefi_lead_history")
    op.drop_table("raw_mefi_leads")

    # Remove funnel_config column from tenants
    op.drop_column("tenants", "funnel_config")
