from __future__ import annotations

"""Create daily_insights table for Phase 5 AI Insights generation.

Revision ID: 008
Revises: 007
Create Date: 2026-05-28

One row per tenant per day — upsert on (tenant_id, date).
See 05-CONTEXT.md D-16 for full column spec.

Column summary:
  id, tenant_id, created_at, updated_at  — TenantScopedMixin columns
  date             — business date (DATE NOT NULL)
  status           — D-14 state machine text: running|success|failed|fallback
  payload_json     — serialized DailyInsightResponse (JSONB, nullable)
  generated_at     — when Claude finished generating (TIMESTAMPTZ, nullable)
  input_tokens     — AI-08 token tracking (INTEGER, nullable)
  output_tokens    — AI-08 token tracking (INTEGER, nullable)
  cost_usd         — AI-08 cost accounting, D-16 (NUMERIC(10,6), nullable)
  raw_response     — last Claude response string, preserved on failure (TEXT, nullable)

Security notes:
  T-05-02-01: raw_response stores Claude JSON output only — no customer PII;
              prompt builder filters context_json before API call (Wave 2 guardrail).
  T-05-02-02: down_revision="007" hardcoded — alembic validates chain before DDL.
  T-05-02-03: tenant_id NOT NULL + FK to tenants.id prevents phantom tenant rows.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_insights",
        # TenantScopedMixin columns (replicated from ORM base — standalone DDL pattern)
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
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
        # Business date — NOT NULL; part of 2-column UPSERT conflict target (tenant_id, date)
        sa.Column("date", sa.Date, nullable=False),
        # D-14 status state machine — TEXT NOT NULL
        # Values: running | success | failed | fallback
        # Status validation is enforced in application layer (InsightService), not CHECK constraint.
        sa.Column("status", sa.Text, nullable=False),
        # Serialized DailyInsightResponse Pydantic model — JSONB nullable
        # Written by InsightRepository after successful generation or fallback construction.
        sa.Column("payload_json", JSONB, nullable=True),
        # When Claude finished generating — populated by InsightService (D-208 datetime.now(UTC))
        sa.Column(
            "generated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        # AI-08 token tracking — INTEGER nullable; NULL when Claude call was not made (fallback)
        sa.Column("input_tokens", sa.Integer, nullable=True),
        sa.Column("output_tokens", sa.Integer, nullable=True),
        # AI-08 cost accounting — NUMERIC(10,6) per D-16; never float
        # Formula: (input_tokens / 1_000_000) * 3.0 + (output_tokens / 1_000_000) * 15.0
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=True),
        # Last raw Anthropic API response text — preserved on status='failed' for debugging
        # T-05-02-01: stores structured JSON output only — no customer PII
        sa.Column("raw_response", sa.Text, nullable=True),
        # FK to tenants — T-05-02-03: prevents phantom tenant_id insertion
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_daily_insights_tenant_id",
        ),
        # 2-column UPSERT conflict target: one insight row per tenant per day
        sa.UniqueConstraint(
            "tenant_id",
            "date",
            name="uq_daily_insights_tenant_date",
        ),
    )

    # Performance index — most common query: "give me today's insight for tenant X"
    op.create_index(
        "ix_daily_insights_tenant_date",
        "daily_insights",
        ["tenant_id", "date"],
    )


def downgrade() -> None:
    # Drop index before table (reverse creation order)
    op.drop_index("ix_daily_insights_tenant_date", table_name="daily_insights")
    op.drop_table("daily_insights")
