---
phase: 04-anomaly-detection
plan: 04
subsystem: celery-task-wiring
tags: [anomaly-detection, celery, nullpool, syncrun, pipeline-chain, tdd-green]

# Dependency graph
requires:
  - phase: 04-anomaly-detection
    plan: 03
    provides: AnomalyService.run_all_rules(), AnomalyRepository.upsert_detected_problem()
  - phase: 03-metrics-engine
    plan: 04
    provides: calculate_daily_kpis task pattern (NullPool, deferred imports, SyncRun, autoretry)
provides:
  - detect_anomalies Celery task with name="tasks.etl.detect_anomalies"
  - daily_pipeline() extended to 3-link chain: sync_mefi_leads → calculate_daily_kpis → detect_anomalies
  - celery_app.py include list updated with "app.tasks.etl.detect_anomalies"
affects:
  - 05 (Phase 5: AI Insights — generate_daily_insights will be 4th link in daily_pipeline chain)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "NullPool per Celery task invocation — mirrors calculate_daily_kpis.py exactly (Pitfall 2 / INFRA-05)"
    - "Deferred imports inside _detect_async() coroutine body — fork-safe pattern (INFRA-05)"
    - "WR-06 stale SyncRun cleanup: UPDATE ... SET status='failed' before creating new running row"
    - "CR-05: autoretry_for=(Exception,) without manual self.retry() — no double-retry hazard"
    - "WR-04: single session.commit() after all repo.upsert_detected_problem() calls"
    - "D-15: detect_anomalies.si() as 3rd immutable chain link — chain halt on failure (PIPE-02)"

key-files:
  created:
    - backend/app/tasks/etl/detect_anomalies.py
  modified:
    - backend/app/tasks/etl/sync_mefi_leads.py
    - backend/app/tasks/celery_app.py
    - backend/tests/unit/test_sync_mefi_leads.py

key-decisions:
  - "detect_anomalies task structure mirrors calculate_daily_kpis.py exactly (D-17) — same NullPool, deferred imports, stale SyncRun cleanup, single commit after all upserts"
  - "kpi_date defaults to yesterday in Europe/Bucharest — consistent with calculate_daily_kpis D-10 default"
  - "Task 2 auto-fix: test_daily_pipeline_chains_calculate_daily_kpis updated from 2-task to 3-task assertion (Phase 3 test was stale — noted Phase 4 would add detect_anomalies)"

# Metrics
duration: 20min
completed: 2026-05-28
---

# Phase 4 Plan 04: detect_anomalies Celery Task + Pipeline Wiring Summary

**detect_anomalies Celery task (NullPool, deferred imports, SyncRun, WR-04/WR-06) wired as third link in daily_pipeline() chain — all integration tests GREEN**

## Performance

- **Duration:** 20 min
- **Started:** 2026-05-28T12:30:00Z
- **Completed:** 2026-05-28T12:50:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Created `backend/app/tasks/etl/detect_anomalies.py`: `detect_anomalies` Celery task with `name="tasks.etl.detect_anomalies"` (WR-07), NullPool engine per invocation, deferred imports inside `_detect_async()` body (INFRA-05 / Pitfall 2), WR-06 stale SyncRun cleanup before new running row, SyncRun(source="anomaly") audit trail (PIPE-04), single commit after all upserts (WR-04), autoretry without manual self.retry() (CR-05)
- Extended `daily_pipeline()` in `sync_mefi_leads.py` to 3-link chain: `sync_mefi_leads.si(tenant_id) → calculate_daily_kpis.si(tenant_id) → detect_anomalies.si(tenant_id)` (D-15)
- Added `"app.tasks.etl.detect_anomalies"` to `celery_app.py` include list (Phase 4)
- 2 non-DB integration tests GREEN: `test_task_writes_syncrun_with_source_anomaly` + `test_task_validates_tenant_id_as_uuid`
- 3 live-DB integration tests correctly skipped (require TEST_DATABASE_URL)
- 23/23 Phase 4 unit tests still GREEN

## Task Commits

Each task was committed atomically:

1. **Task 1: create detect_anomalies Celery task** - `7c48beb3` (feat)
2. **Task 2: extend daily_pipeline and register detect_anomalies in celery_app** - `c586a9bc` (feat)
3. **Rule 1 auto-fix: stale daily_pipeline test** - `c8c658bf` (fix)

## Files Created/Modified

- `backend/app/tasks/etl/detect_anomalies.py` — NEW: detect_anomalies Celery task; NullPool, deferred imports, WR-06 stale SyncRun cleanup, PIPE-04 SyncRun audit, AnomalyService + AnomalyRepository wiring, WR-04 single commit, error handler with new session
- `backend/app/tasks/etl/sync_mefi_leads.py` — MODIFIED daily_pipeline() only: added detect_anomalies import + third chain link; updated docstring
- `backend/app/tasks/celery_app.py` — MODIFIED include list only: added "app.tasks.etl.detect_anomalies" (Phase 4 comment)
- `backend/tests/unit/test_sync_mefi_leads.py` — MODIFIED TestDailyPipeline test: updated from 2-task to 3-task chain assertion (Rule 1 auto-fix)

## Decisions Made

- **detect_anomalies mirrors calculate_daily_kpis.py structure exactly** — D-17 required copying the full NullPool + deferred imports + WR-06 + error handler pattern. No deviations from the template.
- **kpi_date = yesterday in Europe/Bucharest** — consistent with calculate_daily_kpis D-10 default (no `calculation_date` parameter needed for detect_anomalies since anomaly detection is always for yesterday).

## Deviations from Plan

### Auto-Fixed Issues

**1. [Rule 1 - Bug] Stale daily_pipeline test asserting 2-task chain after Phase 4 extension to 3 tasks**
- **Found during:** Task 2 verification (`python -m pytest tests/ --ignore=tests/integration`)
- **Issue:** `test_daily_pipeline_chains_calculate_daily_kpis` in `test_sync_mefi_leads.py` asserted `len(tasks) == 2`. Phase 4 extended the chain to 3 tasks. The test even had a comment noting Phase 4 would add detect_anomalies — it was intentionally left for Phase 4 to update.
- **Fix:** Updated assertion to `len(tasks) == 3` and added `tasks[2].name == "tasks.etl.detect_anomalies"` assertion. Updated docstring to reference D-15.
- **Files modified:** `backend/tests/unit/test_sync_mefi_leads.py`
- **Commit:** `c8c658bf`

## Issues Encountered

None beyond the stale test auto-fixed above.

## Phase 4 Complete

All 4 waves executed:

| Wave | Plan | Description | Status |
|------|------|-------------|--------|
| 0 | 04-01 | Test stubs (RED state) | COMPLETE |
| 1 | 04-02 | Schema: migration 007 + DetectedProblem model | COMPLETE |
| 2 | 04-03 | Service layer: AnomalyService + AnomalyRepository | COMPLETE |
| 3 | 04-04 | Celery task wiring: detect_anomalies + pipeline chain | COMPLETE |

**Total Phase 4 artifacts:**
- 1 Alembic migration (007_detected_problems)
- 1 SQLAlchemy model (DetectedProblem)
- 1 service (AnomalyService: 5 rules + run_all_rules)
- 1 repository (AnomalyRepository: 3-col UPSERT)
- 1 Celery task (detect_anomalies)
- 2 file edits (sync_mefi_leads.py daily_pipeline, celery_app.py include list)
- 28 tests: 23 unit GREEN + 5 integration (2 non-DB GREEN + 3 skipped pending TEST_DATABASE_URL)

**ANOM requirements coverage:** ANOM-01 through ANOM-07 all satisfied.

## Known Stubs

None — all wiring is complete. AnomalyService fetches from real DB tables when run in production.

## Threat Flags

No new security surface beyond what was in the plan's threat model. All T-04-04-01 through T-04-04-06 mitigations implemented: UUID validation at entry, JSON serialization (in celery_app.py), SyncRun audit trail, error_msg truncated to 500 chars, NullPool + finally dispose, immutable .si() chain signatures.

## Self-Check: PASSED

- `backend/app/tasks/etl/detect_anomalies.py` — FOUND
- `backend/app/tasks/etl/sync_mefi_leads.py` detect_anomalies.si() — FOUND (grep count=1)
- `backend/app/tasks/celery_app.py` "app.tasks.etl.detect_anomalies" — FOUND (grep count=1)
- Commit `7c48beb3` — FOUND
- Commit `c586a9bc` — FOUND
- Commit `c8c658bf` — FOUND
- detect_anomalies.name == "tasks.etl.detect_anomalies" — VERIFIED
- 45 tests passed, 3 skipped (live-DB tests without TEST_DATABASE_URL) — VERIFIED

---
*Phase: 04-anomaly-detection*
*Completed: 2026-05-28*
