"""SQLAlchemy ORM model for detected_problems table.

One row per rule per day per tenant.
UPSERT conflict target: (tenant_id, date, rule_id) — 3-col unique key.
Phase 4 Plan 02 — schema foundation.

Rule IDs (stored as TEXT — rules are code, not data):
  - slow_first_touch
  - stuck_offer
  - showroom_traffic_drop
  - underperforming_salesperson
  - junk_lead_quality

Severity levels: low | medium | high

estimated_loss_ron is NUMERIC(12,2) per D-19 — never float.
current_value / expected_value are NUMERIC(12,4) — rule-specific metric values.
context_json holds count + offending IDs + key metric value (D-02, D-03).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TIMESTAMPTZ, Base, TenantScopedMixin


class DetectedProblem(Base, TenantScopedMixin):
    """One row per rule per day per tenant — aggregate anomaly detection result.

    UPSERT conflict target: (tenant_id, date, rule_id) — 3-column unique key.
    AnomalyRepository uses pg_insert().on_conflict_do_update() against this key.

    T-04-02-01: context_json stores external_ids and numeric values only — no PII.
    D-19: estimated_loss_ron is NUMERIC(12,2) — never float.
    """

    __tablename__ = "detected_problems"

    __table_args__ = (
        # Pitfall 5 (3-col unique constraint): must list all 3 conflict-target columns
        # exactly as they appear in the migration DDL.
        UniqueConstraint(
            "tenant_id",
            "date",
            "rule_id",
            name="uq_detected_problems_tenant_date_rule",
        ),
    )

    # Business date — NOT NULL; part of 3-column UPSERT conflict target
    date: Mapped[date] = mapped_column(Date, nullable=False)

    # Rule identifier — TEXT NOT NULL; one of the 5 rule_id string values
    # (slow_first_touch | stuck_offer | showroom_traffic_drop |
    #  underperforming_salesperson | junk_lead_quality)
    rule_id: Mapped[str] = mapped_column(Text, nullable=False)

    # Severity level — TEXT NOT NULL; one of: low | medium | high
    severity: Mapped[str] = mapped_column(Text, nullable=False)

    # Metric name — TEXT NOT NULL; e.g. 'time_to_first_touch_minutes'
    metric: Mapped[str] = mapped_column(Text, nullable=False)

    # Observed value — NUMERIC(12,4) nullable (may be absent for count-based rules)
    current_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)

    # Expected/baseline value — NUMERIC(12,4) nullable
    expected_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)

    # Estimated lost revenue in RON — NUMERIC(12,2) per D-19 (never float)
    # Formulas defined in 04-CONTEXT.md D-04 through D-08.
    estimated_loss_ron: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    # Structured context: count + offending IDs + key metric values.
    # slow_first_touch:        {"count": 3, "lead_ids": ["ext-001"], "worst_hours_elapsed": 8.5}
    # stuck_offer:             {"count": 2, "lead_ids": ["ext-007"], "max_days_stuck": 21}
    # showroom_traffic_drop:   {"baseline_days": 30, "drop_pct": 37.5}
    #   baseline_days: number of non-null conversion_l_to_v days in the 30-day window
    #   drop_pct: percentage drop from baseline (e.g., 37.5 = 37.5% below baseline)
    #   Note: actual_visits / expected_visits are NOT present — conversion_l_to_v ratio is used.
    # underperforming_salesperson: {"count": 1, "salesperson_ids": [7], "details": [...]}
    # junk_lead_quality:       {"junk_count": 45, "total_leads": 150, "junk_rate": 0.30}
    # T-04-02-01: external_ids only — no PII (no names, phones, emails)
    context_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Detection timestamp — alias for created_at semantics.
    # Populated by server_default="now()" at INSERT time.
    detected_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default="now()", nullable=False
    )
