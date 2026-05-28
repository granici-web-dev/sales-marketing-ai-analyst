---
phase: 05-ai-insights
plan: 02
subsystem: schema-foundation
tags: [alembic, sqlalchemy, orm, daily-insights, migration]
dependency_graph:
  requires:
    - "05-01 (Wave 0 test stubs — test_daily_insight_schema.py RED state)"
    - "04-02 (migration 007 — down_revision chain)"
    - "backend/app/db/base.py (TenantScopedMixin, TIMESTAMPTZ)"
    - "backend/app/models/anomaly/detected_problem.py (ORM model pattern)"
  provides:
    - "Alembic migration 008 — daily_insights table DDL"
    - "DailyInsight SQLAlchemy ORM model — Wave 3 InsightRepository target"
    - "backend/app/models/insights package — Alembic autogenerate discovery"
  affects:
    - "backend/app/models/__init__.py (DailyInsight added for autogenerate)"
    - "Wave 3 plans (05-03): InsightRepository UPSERT target table"
tech_stack:
  added: []
  patterns:
    - "SQLAlchemy 2.x Mapped[...] syntax with mapped_column() for all domain columns"
    - "TenantScopedMixin inheritance (id, tenant_id, created_at, updated_at)"
    - "Standalone DDL migration pattern — no autogenerate dependency"
    - "2-column UPSERT conflict target (tenant_id, date) via UniqueConstraint"
key_files:
  created:
    - "backend/alembic/versions/008_daily_insights.py"
    - "backend/app/models/insights/__init__.py"
    - "backend/app/models/insights/daily_insight.py"
  modified:
    - "backend/app/models/__init__.py"
decisions:
  - "Status validation in application layer (InsightService) — no CHECK constraint in DDL; keeps migration DDL clean and avoids migration-level logic"
  - "2-column UPSERT conflict target (tenant_id, date) — one insight row per tenant per day, InsightRepository uses on_conflict_do_update"
  - "cost_usd as NUMERIC(10,6) — never float per D-19; tracks AI-08 cost accounting to 6 decimal places"
  - "raw_response as TEXT nullable — preserved on status=failed for debugging without re-calling API"
metrics:
  duration: "124 seconds"
  completed: "2026-05-28"
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 1
---

# Phase 5 Plan 02: Schema Foundation Summary

**One-liner:** Alembic migration 008 creates the daily_insights table with all 12 D-16 columns (including cost_usd NUMERIC(10,6) and raw_response TEXT), UNIQUE(tenant_id, date) for idempotent daily UPSERT, and the DailyInsight SQLAlchemy ORM model with all 8 domain columns mapped via SQLAlchemy 2.x Mapped syntax.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Alembic migration 008_daily_insights.py | 5dee21f3 | backend/alembic/versions/008_daily_insights.py |
| 2 | DailyInsight ORM model + package init files | fdccfcb5 | backend/app/models/insights/__init__.py, backend/app/models/insights/daily_insight.py, backend/app/models/__init__.py |

## Verification Results

All 4 plan verifications passed:

1. Column inspection: all 12 columns present including `cost_usd` and `raw_response` — PASSED
2. Migration parse: `revision='008', down_revision='007'` — PASSED
3. UniqueConstraint grep: `uq_daily_insights_tenant_date` found at line 98 in migration — PASSED
4. Wave 0 test collection: `pytest tests/unit/test_daily_insight_schema.py --collect-only` — 8 tests collected (still RED — schema module not created until Wave 2) — PASSED

## Schema Coverage

### Migration 008 (DDL)

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | UUID PK | NOT NULL | gen_random_uuid() server default |
| tenant_id | UUID | NOT NULL | FK → tenants.id (T-05-02-03) |
| created_at | TIMESTAMPTZ | NOT NULL | now() server default |
| updated_at | TIMESTAMPTZ | NOT NULL | now() server default |
| date | DATE | NOT NULL | Business date — UPSERT key |
| status | TEXT | NOT NULL | D-14: running\|success\|failed\|fallback |
| payload_json | JSONB | nullable | Serialized DailyInsightResponse |
| generated_at | TIMESTAMPTZ | nullable | When Claude finished |
| input_tokens | INTEGER | nullable | AI-08 tracking |
| output_tokens | INTEGER | nullable | AI-08 tracking |
| cost_usd | NUMERIC(10,6) | nullable | AI-08 cost accounting |
| raw_response | TEXT | nullable | Debugging aid on failure |

Constraints: UNIQUE(tenant_id, date), FK(tenant_id → tenants.id)
Index: ix_daily_insights_tenant_date on (tenant_id, date)

### ORM Model (DailyInsight)

8 domain columns mapped via SQLAlchemy 2.x `Mapped[...]` syntax:
- `date: Mapped[date_type]` — Date
- `status: Mapped[str]` — Text
- `payload_json: Mapped[dict | None]` — JSONB
- `generated_at: Mapped[datetime | None]` — TIMESTAMPTZ
- `input_tokens: Mapped[int | None]` — Integer
- `output_tokens: Mapped[int | None]` — Integer
- `cost_usd: Mapped[Decimal | None]` — Numeric(10, 6)
- `raw_response: Mapped[str | None]` — Text

UniqueConstraint("tenant_id", "date", name="uq_daily_insights_tenant_date") matches migration DDL exactly — UPSERT conflict target alignment verified.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. This plan creates migration DDL and ORM model only. No production logic with stub values.

## Threat Surface Scan

No new network endpoints or auth paths. Security-relevant surfaces from threat model:

| Threat ID | Status |
|-----------|--------|
| T-05-02-01 | Mitigated — raw_response/payload_json store AI JSON output only; PII filter deferred to Wave 2 prompt_builder |
| T-05-02-02 | Mitigated — down_revision="007" hardcoded; chain integrity validated by alembic before DDL |
| T-05-02-03 | Mitigated — FK to tenants.id (fk_daily_insights_tenant_id) + NOT NULL prevents phantom tenant_id insertion |

## Self-Check: PASSED

Files confirmed to exist:
- backend/alembic/versions/008_daily_insights.py — FOUND
- backend/app/models/insights/__init__.py — FOUND
- backend/app/models/insights/daily_insight.py — FOUND

Commits confirmed:
- 5dee21f3 — Task 1 (migration 008)
- fdccfcb5 — Task 2 (ORM model + package init)
