---
phase: 04-anomaly-detection
plan: 02
subsystem: schema
tags: [alembic, sqlalchemy, detected-problems, anomaly-detection, migration]

# Dependency graph
requires:
  - phase: 04-anomaly-detection
    plan: 01
    provides: Wave 0 RED-state test contracts for AnomalyRepository UPSERT (3-col conflict target)
  - phase: 03-metrics-engine
    provides: TenantScopedMixin pattern, migration DDL conventions (004 pattern), daily_kpi.py model pattern
provides:
  - Alembic migration 007 creating detected_problems table with UNIQUE(tenant_id, date, rule_id)
  - DetectedProblem SQLAlchemy ORM model with 8 domain columns + TenantScopedMixin
  - app.models.anomaly package exporting DetectedProblem
  - app.models updated to include DetectedProblem for Alembic autogenerate discovery
affects:
  - 04-03 (Wave 2: AnomalyService + AnomalyRepository implement against this schema)
  - 04-04 (Wave 3: detect_anomalies task writes DetectedProblem rows via AnomalyRepository)
  - 05 (Phase 5 AI Insights reads detected_problems to generate daily reports)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "3-col UniqueConstraint in __table_args__ tuple: matches migration DDL name exactly (Pitfall 5)"
    - "Migration DDL: op.create_table with ForeignKeyConstraint + UniqueConstraint inline (004 pattern)"
    - "Performance indexes added separately via op.create_index after op.create_table"
    - "downgrade() drops indexes before table (reverse creation order)"
    - "NUMERIC(12,4) for metric values, NUMERIC(12,2) for monetary columns — never float (D-19)"
    - "detected_at TIMESTAMPTZ alias capturing detection timestamp separate from created_at"

key-files:
  created:
    - backend/alembic/versions/007_detected_problems.py
    - backend/app/models/anomaly/__init__.py
    - backend/app/models/anomaly/detected_problem.py
  modified:
    - backend/app/models/__init__.py

key-decisions:
  - "3-column UniqueConstraint covers (tenant_id, date, rule_id) — UPSERT conflict target matches 04-CONTEXT.md D-01"
  - "detected_at column added alongside created_at — provides semantic alias for detection timestamp without duplicating TenantScopedMixin created_at"
  - "app/models/__init__.py updated to register DetectedProblem for Alembic autogenerate discovery — Rule 2 (missing critical functionality)"

# Metrics
duration: 2min
completed: 2026-05-28
---

# Phase 4 Plan 02: Anomaly Detection Schema Foundation Summary

**Alembic migration 007 creating detected_problems table and DetectedProblem SQLAlchemy ORM model with 3-col UniqueConstraint(tenant_id, date, rule_id) — schema foundation for Phase 4 AnomalyRepository and Phase 5 AI Insights**

## Performance

- **Duration:** 2 min
- **Started:** 2026-05-28T11:50:23Z
- **Completed:** 2026-05-28T11:52:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Created migration `007_detected_problems.py` with `op.create_table("detected_problems", ...)` containing all 12 columns (4 TenantScopedMixin + 8 domain), ForeignKeyConstraint to tenants.id, 3-column UniqueConstraint, and two performance indexes
- Created `DetectedProblem(Base, TenantScopedMixin)` with 8 domain columns typed as Mapped[...] annotations; estimated_loss_ron as NUMERIC(12,2), metric values as NUMERIC(12,4) — no float types
- Created `app/models/anomaly/__init__.py` exporting DetectedProblem
- Updated `app/models/__init__.py` to register DetectedProblem for Alembic autogenerate discovery (Rule 2 deviation)

## Task Commits

Each task was committed atomically:

1. **Task 1: Alembic migration 007** - `18deafb8` (feat)
2. **Task 2: DetectedProblem model + anomaly package** - `7c710813` (feat)

## Files Created/Modified

- `backend/alembic/versions/007_detected_problems.py` — Migration creating detected_problems table with UNIQUE(tenant_id, date, rule_id), two performance indexes (ix_detected_problems_tenant_date, ix_detected_problems_tenant_rule), FK to tenants.id, and clean downgrade()
- `backend/app/models/anomaly/detected_problem.py` — DetectedProblem ORM model: 8 domain columns (date, rule_id, severity, metric, current_value, expected_value, estimated_loss_ron, context_json) + detected_at TIMESTAMPTZ
- `backend/app/models/anomaly/__init__.py` — Package init exporting DetectedProblem
- `backend/app/models/__init__.py` — Added Phase 4 DetectedProblem import for Alembic autogenerate

## Decisions Made

- 3-column UniqueConstraint `(tenant_id, date, rule_id)` matches the UPSERT conflict target from D-01 exactly — AnomalyRepository (Wave 3) will use `pg_insert().on_conflict_do_update(index_elements=["tenant_id", "date", "rule_id"])`
- `detected_at` column added as a semantic alias for the detection timestamp — provides clearer intent than `created_at` when inspecting anomaly records
- `app/models/__init__.py` updated to register DetectedProblem — ensures `alembic revision --autogenerate` can see the model

## Deviations from Plan

### Auto-added Missing Critical Functionality

**1. [Rule 2 - Missing Critical Functionality] Registered DetectedProblem in app/models/__init__.py**
- **Found during:** Task 2
- **Issue:** The plan specified creating `app/models/anomaly/__init__.py` but did not mention updating the top-level `app/models/__init__.py`. Without this registration, `alembic revision --autogenerate` cannot discover the model, which is a critical requirement for the migration toolchain.
- **Fix:** Added `from app.models.anomaly import DetectedProblem` and `"DetectedProblem"` to `__all__` in `backend/app/models/__init__.py`, following the existing Phase 1/2/3 pattern.
- **Files modified:** `backend/app/models/__init__.py`
- **Commit:** `7c710813`

## Issues Encountered

None.

## Known Stubs

None — this plan creates schema files only. No UI data sources or placeholders.

## Threat Flags

None — migration and ORM model files only. No new network endpoints, auth paths, or file access patterns. context_json stores external_ids and numeric values only per T-04-02-01.

## Self-Check: PASSED

- `backend/alembic/versions/007_detected_problems.py` — FOUND
- `backend/app/models/anomaly/__init__.py` — FOUND
- `backend/app/models/anomaly/detected_problem.py` — FOUND
- `backend/app/models/__init__.py` — MODIFIED (DetectedProblem added)
- Commit `18deafb8` — FOUND
- Commit `7c710813` — FOUND
- `DetectedProblem.__tablename__` == "detected_problems" — VERIFIED
- UniqueConstraint covers (tenant_id, date, rule_id) — VERIFIED
- All 8 domain columns present, no missing required columns — VERIFIED
- estimated_loss_ron is NUMERIC(12,2) — VERIFIED
- current_value / expected_value are NUMERIC(12,4) — VERIFIED
- down_revision = "006" — VERIFIED

## Next Phase Readiness

- Wave 1 (schema foundation) complete — migration 007 and DetectedProblem model ready
- Plan 04-03 (Wave 2): AnomalyService + AnomalyRepository implementation — turns 23 RED-state unit tests GREEN
- Plan 04-04 (Wave 3): detect_anomalies Celery task wired into daily pipeline chain — turns 5 integration tests GREEN

---
*Phase: 04-anomaly-detection*
*Completed: 2026-05-28*
