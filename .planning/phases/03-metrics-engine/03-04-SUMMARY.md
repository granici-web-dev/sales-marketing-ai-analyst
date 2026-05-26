---
phase: 03-metrics-engine
plan: "04"
subsystem: celery-task-wiring
tags: [metrics, celery, chain, task, daily-kpi, phase3, wave3, final]
dependency_graph:
  requires:
    - plans/03-01 (Wave 0 test stubs — test_calculate_daily_kpis.py + test_sync_mefi_leads.py)
    - plans/03-02 (DailyKpi, SalespersonDailyKpi, SourceDailyKpi models + migration 004)
    - plans/03-03 (DailyKpiService, SalespersonKpiService, SourceKpiService, MetricsRepository)
  provides:
    - backend/app/tasks/etl/calculate_daily_kpis.py
    - backend/app/tasks/etl/sync_mefi_leads.py (daily_pipeline() chain extended)
    - backend/app/tasks/celery_app.py (include list extended)
  affects:
    - plans/04-xx (anomaly detection can now read populated metric tables)
tech_stack:
  added: []
  patterns:
    - NullPool engine per task invocation (Pitfall 2 / INFRA-05)
    - Deferred imports inside _calc_async for fork-safety
    - SyncRun lifecycle source="metrics" for audit trail (PIPE-04)
    - Celery chain .si() immutable signatures (D-18)
    - date.fromisoformat() SQL injection mitigation (T-03-04-02)
    - UUID(tenant_id) validation at sync entry (T-03-04-01)
key_files:
  created:
    - backend/app/tasks/etl/calculate_daily_kpis.py
  modified:
    - backend/app/tasks/etl/sync_mefi_leads.py
    - backend/app/tasks/celery_app.py
    - backend/tests/unit/test_sync_mefi_leads.py
decisions:
  - "calculate_daily_kpis uses date.fromisoformat() not datetime.strptime — ValueError on invalid input propagates to autoretry (correct behavior: invalid date should not silently default to yesterday)"
  - "Services called sequentially inside one TaskSession — not concurrently — to avoid shared read lock contention"
  - "Error handler opens NEW TaskSession because original session may have rolled back"
  - "Deferred import of calculate_daily_kpis inside daily_pipeline() function body avoids circular import risk via celery_app include list"
metrics:
  duration_minutes: 4
  completed_at: "2026-05-26T14:41:51Z"
  tasks_completed: 2
  files_created: 1
  files_modified: 3
  commits: 2
---

# Phase 3 Plan 04: Celery Task Wiring Summary

**One-liner:** calculate_daily_kpis Celery task wiring DailyKpiService + SalespersonKpiService + SourceKpiService + MetricsRepository into NullPool-safe task with SyncRun lifecycle, chained after sync_mefi_leads via immutable .si() signatures.

## What Was Built

Wave 3 (final) of Phase 3 Metrics Engine. The Phase 3 metric services built in Plan 03 are now wired into a production-ready Celery task that runs as the second link in the daily ETL pipeline at 04:00 Europe/Bucharest.

### Task 1 — calculate_daily_kpis.py + celery_app.py registration (commit: 104ed868)

| File | Purpose | Key Design |
|------|---------|------------|
| `calculate_daily_kpis.py` | Celery task entry point | NullPool + deferred imports; SyncRun source="metrics"; date defaults to yesterday Bucharest |
| `celery_app.py` | Task module registration | include list extended with app.tasks.etl.calculate_daily_kpis |

**Security mitigations applied:**
- T-03-04-01: `UUID(tenant_id)` at sync entry — malformed strings raise ValueError before any DB access
- T-03-04-02: `date.fromisoformat(calculation_date)` — raw strings never reach SQL
- T-03-04-03: structlog binds tenant_id + kpi_date only — no PII (INFRA-06)
- T-03-04-04/05: NullPool + finally:dispose() — connection always closed (Pitfall 2)
- T-03-04-06: Failed runs write SyncRun(status="failed", error_msg) for audit (PIPE-04)

**Test results:** 6/7 tests GREEN at Task 1 commit (test_daily_pipeline_includes_calculate_task awaited Task 2)

### Task 2 — daily_pipeline() chain extension + chain integration test (commit: 3b1bf5f3)

| File | Change | Key Design |
|------|--------|------------|
| `sync_mefi_leads.py` | daily_pipeline() returns 2-task chain | .si() immutable signatures; deferred import inside function body |
| `test_sync_mefi_leads.py` | TestDailyPipeline class added | Asserts chain has 2 tasks with correct names |

**Test results:** 91/91 Phase 3 tests GREEN after Task 2

## Test Results — All Phase 3 Tests GREEN

| Test File | Tests | Status |
|-----------|-------|--------|
| test_business_hours.py | 8 | GREEN |
| test_metrics_repository.py | 10 | GREEN |
| test_daily_kpi_service.py | 8 | GREEN |
| test_salesperson_kpi_service.py | 7 | GREEN |
| test_source_kpi_service.py | 7 | GREEN |
| test_calculate_daily_kpis.py | 7 | GREEN |
| test_sync_mefi_leads.py | 20 | GREEN |
| test_migration_004.py | 15 | GREEN |
| test_metrics_models.py | 9 | GREEN |
| **Total** | **91** | **91 passed** |

## Verification

All plan verification checks passed:

- [x] `pytest tests/unit/test_calculate_daily_kpis.py tests/unit/test_sync_mefi_leads.py -x` → 27 passed
- [x] `python -c "from app.tasks.celery_app import celery_app; assert 'tasks.etl.calculate_daily_kpis' in celery_app.tasks"` → OK
- [x] Chain names: `['tasks.etl.sync_mefi_leads', 'tasks.etl.calculate_daily_kpis']` → OK
- [x] `Europe/Bucharest` in calculate_daily_kpis.py, business_hours.py, daily_kpi_service.py, source_kpi_service.py, salesperson_kpi_service.py
- [x] No module-level `app.*` imports in calculate_daily_kpis.py (grep returns 0 lines)
- [x] All 91 Phase 3 unit tests GREEN

## Decisions Made

1. `date.fromisoformat(calculation_date)` raises `ValueError` on invalid dates, which propagates to the `autoretry_for=(Exception,)` handler — invalid date should NOT silently default to yesterday (correct: an operator passing a bad date should see an explicit error).
2. Services called sequentially (not concurrently) inside one TaskSession — avoids shared read-lock contention in PostgreSQL when three services query related views.
3. Error handler opens a NEW `TaskSession` to write the failed SyncRun, because the original session may have been rolled back by the exception.
4. `from app.tasks.etl.calculate_daily_kpis import calculate_daily_kpis` is inside the `daily_pipeline()` function body — prevents circular import via the `celery_app.include` list and keeps the sync_mefi_leads module load fast.
5. `.si()` used for both chain links — `calculate_daily_kpis` does not consume the ETL result (it accepts `tenant_id` and optional date independently per D-12).

## Acceptance Criteria — All Met

- [x] `calculate_daily_kpis.py` exists with all required text: `from __future__ import annotations`, `name="tasks.etl.calculate_daily_kpis"`, `def calculate_daily_kpis`, `async def _calc_async`, `NullPool`, `set_tenant_id`, `MetricsRepository`, `DailyKpiService`, `SalespersonKpiService`, `SourceKpiService`, `ZoneInfo("Europe/Bucharest")`, `timedelta(days=1)`, `date_type.fromisoformat`
- [x] File contains `source="metrics"` (SyncRun discriminator)
- [x] File contains `autoretry_for=(Exception,)` AND `max_retries=3` AND `default_retry_delay=60`
- [x] No module-level `app.*` imports except `celery_app` (grep returns 0 lines)
- [x] `celery_app.py` include list contains `"app.tasks.etl.calculate_daily_kpis"`
- [x] `pytest tests/unit/test_calculate_daily_kpis.py -x` → 7/7 GREEN
- [x] Task registered: `'tasks.etl.calculate_daily_kpis' in celery_app.tasks` → True
- [x] `sync_mefi_leads.py` daily_pipeline contains `calculate_daily_kpis.si(tenant_id)` AND `chain(sync_mefi_leads.si(tenant_id), calculate_daily_kpis.si(tenant_id))`
- [x] Deferred import is inside function body (line 325, after `def daily_pipeline` at line 311)
- [x] `test_sync_mefi_leads.py` contains `test_daily_pipeline_chains_calculate_daily_kpis` asserting on `tasks.etl.calculate_daily_kpis`
- [x] `pytest tests/unit/test_sync_mefi_leads.py -x` → 20/20 GREEN
- [x] Chain output: `['tasks.etl.sync_mefi_leads', 'tasks.etl.calculate_daily_kpis']`
- [x] All 9 Phase 3 unit test files GREEN (91 total tests)

## Deviations from Plan

None. Plan executed exactly as written.

## Known Stubs

None. `calculate_daily_kpis` is a full implementation that wires real services. Empty results against an empty DB are correct behavior, not stubs.

## Threat Flags

None. This plan adds a Celery task (no new HTTP endpoints, auth paths, or schema changes). All six documented threat mitigations (T-03-04-01 through T-03-04-06) are applied in the implementation.

## Self-Check: PASSED

- [x] `calculate_daily_kpis.py` exists at `backend/app/tasks/etl/calculate_daily_kpis.py`
- [x] `sync_mefi_leads.py` modified: daily_pipeline() returns 2-task chain
- [x] `celery_app.py` modified: include list has `app.tasks.etl.calculate_daily_kpis`
- [x] `test_sync_mefi_leads.py` modified: TestDailyPipeline class added
- [x] Commit 104ed868 (Task 1) in git log
- [x] Commit 3b1bf5f3 (Task 2) in git log
- [x] 91 Phase 3 tests GREEN
- [x] Chain output verified: `['tasks.etl.sync_mefi_leads', 'tasks.etl.calculate_daily_kpis']`
- [x] METR-01 fully covered: task writes 3 tables, idempotent UPSERT
- [x] D-18 chain semantics live: sync_mefi_leads → calculate_daily_kpis at 04:00 Bucharest via existing beat schedule
- [x] Phase 3 ships
