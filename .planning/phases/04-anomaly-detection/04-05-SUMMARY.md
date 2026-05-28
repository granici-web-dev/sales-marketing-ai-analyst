---
phase: 04-anomaly-detection
plan: "05"
subsystem: database
tags: [alembic, migration, sqlalchemy, anomaly-detection, postgresql]

requires:
  - phase: 04-04
    provides: AnomalyService, migration 007 (detected_problems table), detect_anomalies Celery task

provides:
  - Migration 007 with 13 columns matching ORM model (detected_at TIMESTAMPTZ added, CR-01 closed)
  - _get_junk_ids() scoped to kpi_date via AND created_date_local = :kpi_date (CR-02 closed)
  - context_json keys aligned with ORM model docstring — junk_count and total_leads (INFO closed)

affects: [phase-05-ai-insights, schema-consumers-of-detected_problems]

tech-stack:
  added: []
  patterns:
    - "Migration DDL must mirror ORM model columns exactly — verified by grep on column names"
    - "SQL date-scoping via bindparam: avoid unbounded all-time queries in date-keyed rule engines"
    - "context_json schema governed by ORM model docstring — single source of truth"

key-files:
  created: []
  modified:
    - backend/alembic/versions/007_detected_problems.py
    - backend/app/services/anomaly/anomaly_service.py

key-decisions:
  - "detected_at uses server_default=sa.text('now()') — value set by PostgreSQL, not by ORM caller (T-04-05-01)"
  - "_get_junk_ids kpi_date is a Python date object computed internally — never user-supplied (T-04-05-03)"
  - "No new dependencies added — gap-closure is purely DDL + SQL fix (T-04-05-SC)"

patterns-established:
  - "DDL-ORM sync check: grep the ORM model for all mapped_column() fields; mirror each in migration upgrade()"
  - "Date-scoped DB helpers: every rule method that queries by date must bind that date in WHERE clause"

requirements-completed:
  - ANOM-01
  - ANOM-07

duration: 12min
completed: 2026-05-28
---

# Phase 4 Plan 05: Gap Closure (CR-01, CR-02, INFO) Summary

**Migration 007 gains `detected_at` TIMESTAMPTZ column (13 columns now match ORM), and `_get_junk_ids()` is date-scoped via `AND created_date_local = :kpi_date` — both BLOCKER defects from 04-VERIFICATION.md closed, all 23 unit tests GREEN.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-05-28T00:00:00Z
- **Completed:** 2026-05-28T00:12:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- CR-01 closed: `detected_at TIMESTAMPTZ NOT NULL DEFAULT now()` added to migration 007 `upgrade()` between `updated_at` and `date` columns — DDL now matches DetectedProblem ORM model exactly (13 columns)
- CR-02 closed: `_get_junk_ids()` SQL query extended with `AND created_date_local = :kpi_date` bindparam — query no longer returns all-time junk leads for a single-day analysis window
- INFO closed: `context_json` keys in `detect_junk_lead_quality()` renamed from `count`/`total` to `junk_count`/`total_leads` matching the ORM model docstring schema
- All 23 unit tests (18 service + 5 repository) remain GREEN after both fixes

## Task Commits

Each task was committed atomically:

1. **Task 1: Add detected_at column to migration 007 (CR-01)** - `adaeedaa` (fix)
2. **Task 2: Add date filter to _get_junk_ids() and fix context_json keys (CR-02 + INFO)** - `75f91c23` (fix)

## Files Created/Modified

- `backend/alembic/versions/007_detected_problems.py` — Added `detected_at` TIMESTAMPTZ column after `updated_at`; downgrade() and indexes unchanged
- `backend/app/services/anomaly/anomaly_service.py` — `_get_junk_ids()` SQL date-scoped + docstring updated; `detect_junk_lead_quality()` context_json key rename

## Decisions Made

None — gap-closure plan executed exactly as specified. All fixes were pinpoint edits with no architectural implications. Threat model threats T-04-05-01 through T-04-05-SC all accepted as-is.

## Deviations from Plan

None — plan executed exactly as written. Both fixes applied as specified with no additional changes required.

## Issues Encountered

Pre-existing collection failure in `tests/unit/test_models.py` (ImportError: cannot import name 'TIMESTAMPTZ' from sqlalchemy.dialects.postgresql) — unrelated to this plan's changes. Exists since Phase 1 stub creation (commit fe9d24aa). Deferred to Phase 7 or as standalone fix. 11 other pre-existing failures in test_core_modules.py (security token tests) and test_source_kpi_service.py (categorization stubs) also unrelated. Target test files (test_anomaly_service.py + test_anomaly_repository.py) all 23 GREEN.

## Next Phase Readiness

- Migration 007 DDL is now production-safe — `detected_at` column present, schema matches ORM model
- AnomalyService is date-correct — `_get_junk_ids()` will not inflate junk counts with all-time data
- Phase 4 gap-closure complete; Phase 5 AI Insights can consume `detected_problems` rows safely
- No blockers for Phase 5

## Self-Check

- [x] `backend/alembic/versions/007_detected_problems.py` — exists and has `detected_at` column
- [x] `backend/app/services/anomaly/anomaly_service.py` — exists and has `created_date_local` + `junk_count`/`total_leads`
- [x] Commit `adaeedaa` — Task 1 (migration fix)
- [x] Commit `75f91c23` — Task 2 (service fix)

## Self-Check: PASSED

---
*Phase: 04-anomaly-detection*
*Completed: 2026-05-28*
