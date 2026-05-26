from __future__ import annotations

"""Create metric tables, update v_mefi_leads_active, seed business_hours in funnel_config.

Revision ID: 004
Revises: 003
Create Date: 2026-05-25

Creates Phase 3 metric schema — 6 upgrade steps:

  1. CREATE TABLE daily_kpi
     Full SPEC.md §7 schema + WoW/MoM delta columns (Schema Gap 1, METR-05).
     Ad-spend, GA4, calls columns NULLABLE — populated by future phases (D-08).
     visits_count / offers_count / contracts_count NOT NULL DEFAULT 0.

  2. CREATE TABLE salesperson_daily_kpi
     Full SPEC.md §7 schema + data_completeness_pct NUMERIC(5,2) (Schema Gap 2, METR-06).
     Per D-17: only rows for is_active=True salespeople emitted by service layer.

  3. CREATE TABLE source_daily_kpi
     Full SPEC.md §7 schema. source TEXT (not enum — D-09).
     3-column UNIQUE: (tenant_id, source, date) — Pitfall 5 guard.

  4. CREATE INDEXes on (tenant_id, date) for all three tables
     + CREATE UNIQUE CONSTRAINTs as UPSERT conflict targets.

  5. CREATE OR REPLACE VIEW v_mefi_leads_active (Schema Gap 5, D-13)
     Replaces migration 003 current-status-only view with history-based
     "ever reached" booleans via LEFT JOIN to mefi_lead_history.
     D-13: ever-reached funnel logic via history JOIN — supersedes 003 approximation.

  6. UPDATE tenants SET funnel_config = funnel_config || CAST(:patch AS jsonb)
     WHERE slug = 'sofa-belle' AND (funnel_config->>'business_hours') IS NULL
     Idempotent seed: adds business_hours key for time_to_first_touch calc (D-07).

Security notes:
  T-03-02-01: funnel_config business_hours seed is idempotent (IS NULL guard)
  T-03-02-02: Views include r.tenant_id — services MUST filter WHERE tenant_id = :tid
  T-03-02-03: History JOIN includes h.tenant_id = r.tenant_id — no cross-tenant bleed
  T-03-02-04: NUMERIC types only for all money/rate/delta columns (D-16)
"""

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# ── Revision identifiers ──────────────────────────────────────────────────────

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ── Business hours patch (D-07 from 03-CONTEXT.md) ───────────────────────────
# Seeded into tenants.funnel_config JSONB for Sofa Belle.
# Mon-Sun 09:00-19:00 Europe/Bucharest — 7 days/week, 10-hour window.
# Used by salesperson_kpi_service for avg_time_to_first_touch_minutes calculation.

BUSINESS_HOURS_PATCH = {
    "business_hours": {
        "days": [0, 1, 2, 3, 4, 5, 6],   # Mon=0 ... Sun=6 (D-07: 7 days/week)
        "open": "09:00",
        "close": "19:00",
        "tz": "Europe/Bucharest",
    }
}

# ── Updated v_mefi_leads_active view DDL (Schema Gap 5) ──────────────────────
#
# D-13: "ever reached" funnel logic via mefi_lead_history JOIN.
# Supersedes migration 003 current-status-only approximation.
#
# reached_visit:    current status IN (17,3,1) OR ever had status 17 in history
# reached_offer:    current status IN (3,1) OR offer_sent_flag=true OR ever had status 3 in history
# reached_contract: current status = 1 (WON — only counts as contract if currently WON)
#
# T-03-02-03: JOIN includes h.tenant_id = r.tenant_id — prevents cross-tenant history bleed.
# D-15: AT TIME ZONE 'Europe/Bucharest' preserved for local timestamp computed columns.
# Explicit column list — no SELECT * (CLAUDE.md: never use SELECT *).

V_MEFI_LEADS_ACTIVE_V004 = """
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

    -- Computed: Bucharest-local timestamps (DATA-03, D-15)
    -- AT TIME ZONE converts TIMESTAMPTZ -> TIMESTAMP in the named zone
    r.created_at_source AT TIME ZONE 'Europe/Bucharest' AS created_at_local,
    r.status_changed_at AT TIME ZONE 'Europe/Bucharest' AS status_changed_at_local,

    -- Computed: funnel stage flags (D-13 "ever reached" via history JOIN)
    -- D-13: ever-reached funnel logic via history JOIN — supersedes 003 current-status-only
    -- T-03-02-03: JOIN condition includes h.tenant_id = r.tenant_id — no cross-tenant bleed

    -- Visit: current status IN (17,3,1) OR ever had status 17 in history
    (
        r.status_id IN (17, 3, 1)
        OR COALESCE(
            BOOL_OR(h.to_status_id IN (17, 3, 1)) OVER (PARTITION BY r.tenant_id, r.external_id),
            FALSE
        )
    ) AS reached_visit,

    -- Offer: current status IN (3,1) OR offer_sent_flag=true OR ever had status 3 in history
    (
        r.status_id IN (3, 1)
        OR r.offer_sent_flag = TRUE
        OR COALESCE(
            BOOL_OR(h.to_status_id IN (3, 1)) OVER (PARTITION BY r.tenant_id, r.external_id),
            FALSE
        )
    ) AS reached_offer,

    -- Contract: current status = 1 (WON — only currently WON counts)
    (r.status_id = 1) AS reached_contract

FROM raw_mefi_leads r
LEFT JOIN mefi_lead_history h
    ON h.tenant_id = r.tenant_id
    AND h.lead_external_id = r.external_id
WHERE r.lifecycle IN ('active', 'lost')
"""

# ── Downgrade restore constant: migration 003 v_mefi_leads_active DDL ────────
# Exact copy from 003_mefi_schema.py V_MEFI_LEADS_ACTIVE constant.
# Used by downgrade() to restore the previous current-status-only view.

V_MEFI_LEADS_ACTIVE_V003 = """
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
    -- AT TIME ZONE converts TIMESTAMPTZ -> TIMESTAMP in the named zone
    r.created_at_source AT TIME ZONE 'Europe/Bucharest' AS created_at_local,
    r.status_changed_at AT TIME ZONE 'Europe/Bucharest' AS status_changed_at_local,

    -- Computed: funnel stage flags (D-09 "ever reached" approximation)
    -- NOTE: reached_* columns use current status_id only (Phase 2 limitation).
    -- True "ever reached" requires mefi_lead_history join -- planned for Phase 3.
    -- Visit: lead is at SHOWROOM stage OR has progressed beyond it
    (r.status_id = 17 OR r.status_id IN (3, 1)) AS reached_visit,

    -- Offer: lead has Ofertat status OR offer_sent_flag set OR has progressed to contract
    (r.status_id = 3 OR r.offer_sent_flag = true OR r.status_id = 1) AS reached_offer,

    -- Contract: lead is a Clienti (WON deal)
    (r.status_id = 1) AS reached_contract

FROM raw_mefi_leads r
WHERE r.lifecycle IN ('active', 'lost')
"""


def upgrade() -> None:
    # ── Step 1: CREATE TABLE daily_kpi ───────────────────────────────────────
    # Full SPEC.md §7 schema + WoW/MoM delta columns (Schema Gap 1, METR-05).
    # TenantScopedMixin columns replicated — migration is standalone DDL (003 pattern).
    op.create_table(
        "daily_kpi",
        # TenantScopedMixin columns (replicated from ORM base)
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

        # Business date — NOT NULL; UPSERT conflict target with tenant_id
        sa.Column("date", sa.Date, nullable=False),

        # --- Ad spend (nullable — populated Iteration 2) ---
        sa.Column("spend_meta", sa.Numeric(10, 2), nullable=True),
        sa.Column("spend_google", sa.Numeric(10, 2), nullable=True),
        sa.Column("spend_tiktok", sa.Numeric(10, 2), nullable=True),
        sa.Column("spend_digital_total", sa.Numeric(10, 2), nullable=True),

        # --- GA4 (nullable — populated Iteration 3) ---
        sa.Column("web_sessions", sa.Integer, nullable=True),
        sa.Column("web_conversion_rate", sa.Numeric(5, 4), nullable=True),

        # --- Lead volume by source (nullable) ---
        sa.Column("leads_mail_fb_ig", sa.Integer, nullable=True),
        sa.Column("leads_telefon", sa.Integer, nullable=True),
        sa.Column("leads_whatsapp", sa.Integer, nullable=True),
        sa.Column("leads_site", sa.Integer, nullable=True),
        sa.Column("leads_designer", sa.Integer, nullable=True),
        sa.Column("leads_alte", sa.Integer, nullable=True),
        sa.Column("leads_total", sa.Integer, nullable=True),

        # --- CPL (nullable — populated Iteration 2) ---
        sa.Column("cpl_overall", sa.Numeric(8, 2), nullable=True),
        sa.Column("cpl_by_channel", JSONB, nullable=True),

        # --- Funnel counts (NOT NULL — Phase 3 always computes these) ---
        sa.Column(
            "visits_count",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "offers_count",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "contracts_count",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),

        # --- Conversion rates — NUMERIC(5,4) per SPEC.md §7 ---
        sa.Column("conversion_l_to_v", sa.Numeric(5, 4), nullable=True),
        sa.Column("conversion_v_to_o", sa.Numeric(5, 4), nullable=True),
        sa.Column("conversion_l_to_o", sa.Numeric(5, 4), nullable=True),
        sa.Column("conversion_o_to_c", sa.Numeric(5, 4), nullable=True),
        sa.Column("conversion_l_to_c", sa.Numeric(5, 4), nullable=True),

        # --- Revenue — NUMERIC(12,2) per DATA-04 ---
        sa.Column("revenue", sa.Numeric(12, 2), nullable=True),
        sa.Column("avg_deal_size", sa.Numeric(10, 2), nullable=True),
        sa.Column("avg_deal_size_per_day", sa.Numeric(10, 2), nullable=True),
        sa.Column("cost_acquisition_contract", sa.Numeric(12, 2), nullable=True),

        # --- CAC/ROAS (nullable — Iteration 2) ---
        sa.Column("cac", sa.Numeric(10, 2), nullable=True),
        sa.Column("roas", sa.Numeric(8, 2), nullable=True),

        # --- Calls (nullable — future telephony) ---
        sa.Column("calls_total", sa.Integer, nullable=True),
        sa.Column("calls_answered", sa.Integer, nullable=True),
        sa.Column("calls_missed", sa.Integer, nullable=True),
        sa.Column("avg_call_duration_seconds", sa.Integer, nullable=True),
        sa.Column("avg_sentiment_score", sa.Numeric(3, 2), nullable=True),

        # --- WoW / MoM deltas (METR-05 — NOT in SPEC.md §7, added by this migration) ---
        # NUMERIC(8,4): range covers fractional change [-1, +infinity)
        # NULL when prior-period row absent (D-11 — never impute zero)
        sa.Column("leads_total_wow_delta", sa.Numeric(8, 4), nullable=True),
        sa.Column("leads_total_mom_delta", sa.Numeric(8, 4), nullable=True),
        sa.Column("conversion_l_to_v_wow_delta", sa.Numeric(8, 4), nullable=True),
        sa.Column("conversion_l_to_v_mom_delta", sa.Numeric(8, 4), nullable=True),
        sa.Column("conversion_v_to_o_wow_delta", sa.Numeric(8, 4), nullable=True),
        sa.Column("conversion_v_to_o_mom_delta", sa.Numeric(8, 4), nullable=True),
        sa.Column("conversion_l_to_o_wow_delta", sa.Numeric(8, 4), nullable=True),
        sa.Column("conversion_l_to_o_mom_delta", sa.Numeric(8, 4), nullable=True),
        sa.Column("conversion_o_to_c_wow_delta", sa.Numeric(8, 4), nullable=True),
        sa.Column("conversion_o_to_c_mom_delta", sa.Numeric(8, 4), nullable=True),
        sa.Column("conversion_l_to_c_wow_delta", sa.Numeric(8, 4), nullable=True),
        sa.Column("conversion_l_to_c_mom_delta", sa.Numeric(8, 4), nullable=True),
        sa.Column("revenue_wow_delta", sa.Numeric(8, 4), nullable=True),
        sa.Column("revenue_mom_delta", sa.Numeric(8, 4), nullable=True),
        sa.Column("avg_deal_size_wow_delta", sa.Numeric(8, 4), nullable=True),
        sa.Column("avg_deal_size_mom_delta", sa.Numeric(8, 4), nullable=True),

        # --- Calculation timestamp ---
        sa.Column(
            "calculated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),

        # FK to tenants
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_daily_kpi_tenant_id",
        ),
    )

    # ── Step 2: CREATE TABLE salesperson_daily_kpi ────────────────────────────
    # Full SPEC.md §7 schema + data_completeness_pct (Schema Gap 2, METR-06).
    op.create_table(
        "salesperson_daily_kpi",
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

        # Salesperson identifier — TEXT NOT NULL (UPSERT conflict target)
        sa.Column("salesperson_external_id", sa.Text, nullable=False),

        # Business date — NOT NULL; part of 3-column UPSERT conflict target
        sa.Column("date", sa.Date, nullable=False),

        # --- Lead funnel metrics ---
        sa.Column("leads_assigned", sa.Integer, nullable=True),
        sa.Column("leads_contacted", sa.Integer, nullable=True),

        # Business-hours-adjusted minutes (D-06). NULL = no mefi_lead_history rows (D-05).
        sa.Column("avg_time_to_first_touch_minutes", sa.Integer, nullable=True),

        # --- Funnel stage counts ---
        sa.Column("visits_conducted", sa.Integer, nullable=True),
        sa.Column("offers_sent", sa.Integer, nullable=True),
        sa.Column("deals_won", sa.Integer, nullable=True),
        sa.Column("deals_lost", sa.Integer, nullable=True),

        # --- Revenue ---
        sa.Column("revenue", sa.Numeric(12, 2), nullable=True),

        # --- Conversion rates ---
        sa.Column("conversion_l_to_v", sa.Numeric(5, 4), nullable=True),
        sa.Column("conversion_v_to_o", sa.Numeric(5, 4), nullable=True),
        sa.Column("conversion_o_to_c", sa.Numeric(5, 4), nullable=True),
        sa.Column("conversion_l_to_c", sa.Numeric(5, 4), nullable=True),

        # --- Revenue per deal ---
        sa.Column("avg_deal_size", sa.Numeric(10, 2), nullable=True),

        # --- Calls (nullable — future telephony) ---
        sa.Column("calls_made", sa.Integer, nullable=True),
        sa.Column("calls_answered", sa.Integer, nullable=True),
        sa.Column("avg_call_duration_seconds", sa.Integer, nullable=True),
        sa.Column("avg_sentiment_score", sa.Numeric(3, 2), nullable=True),

        # --- data_completeness_pct (Schema Gap 2 — METR-06, NOT in SPEC.md §7) ---
        # % of leads with estimated_value set. Range 0.00-100.00 (Assumption A3).
        sa.Column("data_completeness_pct", sa.Numeric(5, 2), nullable=True),

        # --- Calculation timestamp ---
        sa.Column(
            "calculated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),

        # FK to tenants
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_salesperson_daily_kpi_tenant_id",
        ),
    )

    # ── Step 3: CREATE TABLE source_daily_kpi ────────────────────────────────
    # Full SPEC.md §7 schema. source TEXT (D-09: not enum).
    # 3-column UNIQUE: (tenant_id, source, date) — Pitfall 5.
    op.create_table(
        "source_daily_kpi",
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

        # Source category — TEXT NOT NULL (D-09: funnel_config category names, not enum)
        # One of: mail_fb_ig | telefon | whatsapp | site | designer | alte | google (D-04)
        sa.Column("source", sa.Text, nullable=False),

        # Business date — NOT NULL; part of 3-column UPSERT conflict target
        sa.Column("date", sa.Date, nullable=False),

        # --- Lead volume ---
        sa.Column("leads", sa.Integer, nullable=True),

        # --- Ad spend (nullable — populated Iteration 2) ---
        sa.Column("ad_spend", sa.Numeric(10, 2), nullable=True),

        # --- Efficiency metrics (nullable — populated Iteration 2) ---
        sa.Column("cpl", sa.Numeric(8, 2), nullable=True),
        sa.Column("cac", sa.Numeric(10, 2), nullable=True),
        sa.Column("roas", sa.Numeric(8, 2), nullable=True),

        # --- Funnel stage counts ---
        sa.Column("visits", sa.Integer, nullable=True),
        sa.Column("offers", sa.Integer, nullable=True),
        sa.Column("deals_won", sa.Integer, nullable=True),

        # --- Revenue ---
        sa.Column("revenue", sa.Numeric(12, 2), nullable=True),

        # --- Conversion rate ---
        sa.Column("conversion_rate", sa.Numeric(5, 4), nullable=True),

        # --- Calculation timestamp ---
        sa.Column(
            "calculated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),

        # FK to tenants
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_source_daily_kpi_tenant_id",
        ),
    )

    # ── Step 4: Create indexes ────────────────────────────────────────────────
    # Primary lookup: (tenant_id, date) covers all per-tenant-per-day queries
    op.create_index(
        "ix_daily_kpi_tenant_date",
        "daily_kpi",
        ["tenant_id", "date"],
    )
    op.create_index(
        "ix_salesperson_daily_kpi_tenant_date",
        "salesperson_daily_kpi",
        ["tenant_id", "date"],
    )
    op.create_index(
        "ix_source_daily_kpi_tenant_date",
        "source_daily_kpi",
        ["tenant_id", "date"],
    )

    # ── Step 5: Create UNIQUE constraints ─────────────────────────────────────
    # UPSERT conflict target for daily_kpi (2-column key)
    op.create_unique_constraint(
        "uq_daily_kpi_tenant_date",
        "daily_kpi",
        ["tenant_id", "date"],
    )
    # UPSERT conflict target for salesperson_daily_kpi (3-column key)
    op.create_unique_constraint(
        "uq_salesperson_daily_kpi_tenant_sp_date",
        "salesperson_daily_kpi",
        ["tenant_id", "salesperson_external_id", "date"],
    )
    # UPSERT conflict target for source_daily_kpi (3-column key — Pitfall 5)
    op.create_unique_constraint(
        "uq_source_daily_kpi_tenant_source_date",
        "source_daily_kpi",
        ["tenant_id", "source", "date"],
    )

    # ── Step 6a: Replace v_mefi_leads_active with history-based version ───────
    # Drop old view first (migration 003 current-status-only version)
    op.execute("DROP VIEW IF EXISTS v_mefi_leads_active")
    # Create updated view with mefi_lead_history JOIN (D-13, Schema Gap 5)
    op.execute(V_MEFI_LEADS_ACTIVE_V004)

    # ── Step 6b: Seed business_hours into tenants.funnel_config ──────────────
    # Idempotent: (funnel_config->>'business_hours') IS NULL guard prevents
    # overwriting manually edited configs on re-run (T-03-02-01, same as 003 pattern).
    # CAST(:patch AS jsonb) — NOT ::jsonb — SQLAlchemy text() parser mistakes ::
    # cast operator for a named parameter (bindparam pitfall documented in 003).
    op.execute(
        sa.text(
            """
            UPDATE tenants
            SET funnel_config = funnel_config || CAST(:patch AS jsonb)
            WHERE slug = 'sofa-belle'
              AND (funnel_config->>'business_hours') IS NULL
            """
        ).bindparams(patch=json.dumps(BUSINESS_HOURS_PATCH))
    )


def downgrade() -> None:
    # Reverse order of upgrade steps

    # Remove business_hours key from funnel_config
    # jsonb minus operator removes a key by name
    op.execute(
        sa.text(
            "UPDATE tenants SET funnel_config = funnel_config - 'business_hours' "
            "WHERE slug = 'sofa-belle'"
        )
    )

    # Restore v_mefi_leads_active to migration 003 current-status-only version
    op.execute("DROP VIEW IF EXISTS v_mefi_leads_active")
    op.execute(V_MEFI_LEADS_ACTIVE_V003)

    # Drop unique constraints
    op.drop_constraint("uq_source_daily_kpi_tenant_source_date", "source_daily_kpi", type_="unique")
    op.drop_constraint(
        "uq_salesperson_daily_kpi_tenant_sp_date", "salesperson_daily_kpi", type_="unique"
    )
    op.drop_constraint("uq_daily_kpi_tenant_date", "daily_kpi", type_="unique")

    # Drop indexes
    op.drop_index("ix_source_daily_kpi_tenant_date", table_name="source_daily_kpi")
    op.drop_index("ix_salesperson_daily_kpi_tenant_date", table_name="salesperson_daily_kpi")
    op.drop_index("ix_daily_kpi_tenant_date", table_name="daily_kpi")

    # Drop tables in reverse creation order
    op.drop_table("source_daily_kpi")
    op.drop_table("salesperson_daily_kpi")
    op.drop_table("daily_kpi")
