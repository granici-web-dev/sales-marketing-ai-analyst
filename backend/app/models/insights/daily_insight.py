from __future__ import annotations

"""SQLAlchemy ORM model for daily_insights table.

One row per tenant per day.
UPSERT conflict target: (tenant_id, date) — 2-col unique key.
Phase 5 Plan 02 — schema foundation.

D-16 column spec:
  id, tenant_id, created_at, updated_at  — from TenantScopedMixin
  date             — business date (DATE NOT NULL)
  status           — D-14 state machine: running | success | failed | fallback
  payload_json     — serialized DailyInsightResponse (JSONB, nullable)
  generated_at     — when Claude finished generating (TIMESTAMPTZ, nullable)
  input_tokens     — AI-08 token tracking (INTEGER, nullable)
  output_tokens    — AI-08 token tracking (INTEGER, nullable)
  cost_usd         — AI-08 cost accounting NUMERIC(10,6), nullable
  raw_response     — last Claude response string, preserved on failure (TEXT, nullable)

D-14 status state machine:
  running  — generation task is in progress
  success  — Claude generated valid DailyInsightResponse
  failed   — all retries exhausted AND fallback construction itself failed
  fallback — Claude failed; InsightService constructed report from detected_problems directly

T-05-02-01: raw_response stores Claude JSON output only — no customer PII.
"""

from datetime import date as date_type
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Date, Integer, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin, TIMESTAMPTZ


class DailyInsight(Base, TenantScopedMixin):
    """One row per tenant per day — upsert on (tenant_id, date).

    D-16 column spec. D-14 status state machine: running | success | failed | fallback.

    InsightRepository uses pg_insert().on_conflict_do_update() against
    the (tenant_id, date) unique key for idempotent daily pipeline runs.

    T-05-02-01: payload_json and raw_response store structured AI output only —
                no customer PII (no names, phones, emails).
    D-19: cost_usd is NUMERIC(10,6) — never float.
    """

    __tablename__ = "daily_insights"

    __table_args__ = (
        # 2-column UPSERT conflict target: one insight row per tenant per day
        UniqueConstraint(
            "tenant_id",
            "date",
            name="uq_daily_insights_tenant_date",
        ),
    )

    # Business date — NOT NULL; part of 2-column UPSERT conflict target
    date: Mapped[date_type] = mapped_column(Date, nullable=False)

    # D-14 status state machine — TEXT NOT NULL
    # Values: running | success | failed | fallback
    # Application layer (InsightService) enforces valid values.
    status: Mapped[str] = mapped_column(Text, nullable=False)

    # Serialized DailyInsightResponse Pydantic model — JSONB nullable
    # Populated by InsightRepository after successful generation or fallback construction.
    payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # When Claude finished generating — set by InsightService to datetime.now(UTC)
    # NULL when Claude call was not made (fallback or running status).
    generated_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)

    # AI-08 token tracking — NULL when Claude call was not made
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # AI-08 cost accounting — NUMERIC(10,6) per D-16; never float (D-19)
    # Formula: (input_tokens / 1_000_000) * 3.0 + (output_tokens / 1_000_000) * 15.0
    # Claude Sonnet 4.5 pricing from SPEC.md Section 10.
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)

    # Last raw Anthropic API response text — preserved on status='failed' for debugging
    # T-05-02-01: stores structured JSON output only — no customer PII
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
