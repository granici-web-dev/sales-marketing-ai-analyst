from __future__ import annotations

"""Create detected_problems table for Phase 4 anomaly detection.

Revision ID: 007
Revises: 006
Create Date: 2026-05-28

Adds the detected_problems table which stores one aggregate row per rule per
day per tenant. Written by the AnomalyRepository (Wave 3) and read by the
Phase 5 AI Insights generator.

UPSERT conflict target: (tenant_id, date, rule_id) — 3-column unique key.
See 04-CONTEXT.md D-01 for the row-granularity decision.

Security notes:
  T-04-02-01: context_json stores lead external_ids and numeric values only —
              no customer names, phones, or emails (PII-free).
  T-04-02-02: down_revision="006" hardcoded — alembic check validates chain
              integrity before any upgrade.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "detected_problems",
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
        # Detection timestamp — when the anomaly was first detected.
        # Mirrors ORM model: detected_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default="now()", nullable=False)
        sa.Column(
            "detected_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # Business date — NOT NULL; part of 3-column UPSERT conflict target
        sa.Column("date", sa.Date, nullable=False),
        # Rule identifier — TEXT NOT NULL; one of: slow_first_touch | stuck_offer |
        # showroom_traffic_drop | underperforming_salesperson | junk_lead_quality
        sa.Column("rule_id", sa.Text, nullable=False),
        # Severity level — TEXT NOT NULL; one of: low | medium | high
        sa.Column("severity", sa.Text, nullable=False),
        # Metric name — TEXT NOT NULL; e.g. 'time_to_first_touch_minutes'
        sa.Column("metric", sa.Text, nullable=False),
        # Observed value — NUMERIC(12,4) nullable (may be absent for count-based rules)
        sa.Column("current_value", sa.Numeric(12, 4), nullable=True),
        # Expected/baseline value — NUMERIC(12,4) nullable
        sa.Column("expected_value", sa.Numeric(12, 4), nullable=True),
        # Estimated lost revenue in RON — NUMERIC(12,2) per D-19 (never float)
        sa.Column("estimated_loss_ron", sa.Numeric(12, 2), nullable=True),
        # Structured context: count + offending lead/salesperson IDs + key values.
        # Example: {"count": 3, "lead_ids": ["ext-001"], "worst_hours_elapsed": 8.5}
        # T-04-02-01: external_ids only — no PII stored here.
        sa.Column("context_json", JSONB, nullable=True),
        # FK to tenants
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_detected_problems_tenant_id",
        ),
        # 3-column UPSERT conflict target (Pitfall 5 from 03-PATTERNS.md)
        sa.UniqueConstraint(
            "tenant_id",
            "date",
            "rule_id",
            name="uq_detected_problems_tenant_date_rule",
        ),
    )

    # Performance indexes — cover the two most common query patterns:
    # 1. "Give me all problems for tenant X on date Y" (daily insights generation)
    op.create_index(
        "ix_detected_problems_tenant_date",
        "detected_problems",
        ["tenant_id", "date"],
    )
    # 2. "Give me all occurrences of rule R for tenant X" (trend analysis)
    op.create_index(
        "ix_detected_problems_tenant_rule",
        "detected_problems",
        ["tenant_id", "rule_id"],
    )


def downgrade() -> None:
    # Drop indexes before table (reverse creation order)
    op.drop_index("ix_detected_problems_tenant_rule", table_name="detected_problems")
    op.drop_index("ix_detected_problems_tenant_date", table_name="detected_problems")
    op.drop_table("detected_problems")
