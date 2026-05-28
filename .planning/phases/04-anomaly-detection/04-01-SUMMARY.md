---
phase: 04-anomaly-detection
plan: 01
subsystem: testing
tags: [factory-boy, pytest, pytest-asyncio, tdd, anomaly-detection, red-state]

# Dependency graph
requires:
  - phase: 03-metrics-engine
    provides: MetricsRepository UPSERT pattern (Pitfall 5/6, WR-04), DailyKpiService structure, metrics_factory.py pattern, calculate_daily_kpis.py task pattern (SyncRun, NullPool, deferred imports)
provides:
  - RED-state test contracts for AnomalyService (5 rule methods + run_all_rules)
  - RED-state test contracts for AnomalyRepository (UPSERT with 3-col conflict target)
  - RED-state integration test for detect_anomalies Celery task
  - anomaly_factory.py with DetectedProblemRowFactory, LeadWithNoTouchFactory, StuckOfferLeadFactory
  - 28 total tests: 23 unit + 5 integration (3 skipped until DB available)
affects:
  - 04-02 (Wave 1: migration + model), 04-03 (Wave 2: service layer), 04-04 (Wave 3: Celery task)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "RED-state test pattern: deferred imports in _make_service()/_make_repo() helpers"
    - "Factory pattern: Meta.model = dict for plain dict factories (not ORM instances)"
    - "Builder helper pattern: make_*() functions wrapping factory .build() with overrides"
    - "3-col conflict target test: mirrors Pitfall 5 from MetricsRepository"
    - "WR-04 test: assert session.commit not called inside upsert methods"
    - "D-11 test: assert _get_junk_ids called exactly once per run_all_rules()"
    - "Integration skip: pytest.mark.skipif on TEST_DATABASE_URL for DB-required tests"

key-files:
  created:
    - backend/tests/factories/anomaly_factory.py
    - backend/tests/unit/test_anomaly_service.py
    - backend/tests/unit/test_anomaly_repository.py
    - backend/tests/integration/test_detect_anomalies_task.py
  modified: []

key-decisions:
  - "25% junk lead threshold used (D-20/ROADMAP SC#6) — overrides REQUIREMENTS.md baseline of 20%"
  - "Integration tests skip gracefully without TEST_DATABASE_URL — no Docker required for RED-state collection"
  - "detect_slow_first_touch receives pre-filtered slow_leads list — service doesn't query DB directly in test"

patterns-established:
  - "Deferred import pattern: _make_service()/_make_repo() with # noqa: PLC0415 comment"
  - "Factory builder helpers: make_detected_problem_row() and make_daily_kpi_baseline_rows()"
  - "RED-state confirmation: ModuleNotFoundError for app.services.anomaly (not SyntaxError)"
  - "WR-06 integration test: pre-seed stale SyncRun, run task, assert status=failed"

requirements-completed: [ANOM-01, ANOM-02, ANOM-03, ANOM-04, ANOM-05, ANOM-06, ANOM-07]

# Metrics
duration: 25min
completed: 2026-05-28
---

# Phase 4 Plan 01: Anomaly Detection TDD Wave 0 Summary

**RED-state test contracts for 5 anomaly rules, AnomalyRepository UPSERT, and detect_anomalies Celery task — 4 new test files, 28 tests, all failing with ModuleNotFoundError confirming TDD Wave 0**

## Performance

- **Duration:** 25 min
- **Started:** 2026-05-28T00:00:00Z
- **Completed:** 2026-05-28T00:25:00Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Created anomaly_factory.py (GREEN) with 3 factory classes and 2 builder helpers — importable and producing correct dict structures verified
- Created test_anomaly_service.py (RED) with 18 tests covering all 5 detect methods + run_all_rules orchestrator, including junk exclusion (ANOM-07) and all loss formula arithmetic (D-06, D-07, D-08)
- Created test_anomaly_repository.py (RED) with 5 tests covering UPSERT guard patterns (Pitfall 5/6, WR-04, D-01 idempotency)
- Created test_detect_anomalies_task.py (RED) with 5 tests including ROADMAP SC#6 (junk leads excluded from slow_first_touch) and D-01 UPSERT idempotency integration tests

## Task Commits

Each task was committed atomically:

1. **Task 1: Create anomaly_factory.py** - `d7907ac1` (test)
2. **Task 2: Create RED-state unit tests for AnomalyService and AnomalyRepository** - `8d0b7850` (test)
3. **Task 3: Create RED-state integration test for detect_anomalies task** - `4f2bdefd` (test)

## Files Created/Modified

- `backend/tests/factories/anomaly_factory.py` — DetectedProblemRowFactory, LeadWithNoTouchFactory, StuckOfferLeadFactory, make_detected_problem_row(), make_daily_kpi_baseline_rows() (GREEN — importable)
- `backend/tests/unit/test_anomaly_service.py` — 18 RED-state tests for AnomalyService: 6 test classes covering all 5 rules + run_all_rules (RED — ModuleNotFoundError)
- `backend/tests/unit/test_anomaly_repository.py` — 5 RED-state tests for AnomalyRepository UPSERT (RED — ModuleNotFoundError)
- `backend/tests/integration/test_detect_anomalies_task.py` — 5 tests: 2 non-DB (RED) + 3 integration with @pytest.mark.integration (skipped without TEST_DATABASE_URL)

## Decisions Made

- 25% junk lead threshold used in test_fires_when_junk_rate_gte_25pct — D-20 and ROADMAP SC#6 override REQUIREMENTS.md baseline of 20%; test comment documents the conflict explicitly
- Integration tests use @_INTEGRATION_SKIP decorator wrapping pytest.mark.skipif — mirrors existing test_mefi_etl.py pattern for consistency
- detect_slow_first_touch test signature passes pre-filtered slow_leads list — matches plan spec; the service method accepts data, not queries DB itself

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Known Stubs

None — this plan creates test-only files. No UI data sources or placeholders.

## Threat Flags

None — test-only files, no new network endpoints or auth paths introduced.

## Self-Check: PASSED

- `backend/tests/factories/anomaly_factory.py` — FOUND
- `backend/tests/unit/test_anomaly_service.py` — FOUND
- `backend/tests/unit/test_anomaly_repository.py` — FOUND
- `backend/tests/integration/test_detect_anomalies_task.py` — FOUND
- Commit `d7907ac1` — FOUND
- Commit `8d0b7850` — FOUND
- Commit `4f2bdefd` — FOUND

## Next Phase Readiness

- Wave 0 (RED-state test contracts) complete — 28 tests defined, all failing with ModuleNotFoundError
- Plan 04-02 (Wave 1): Alembic migration for detected_problems table + SQLAlchemy DetectedProblem model
- Plan 04-03 (Wave 2): AnomalyService + AnomalyRepository implementation (turns 23 unit tests GREEN)
- Plan 04-04 (Wave 3): detect_anomalies Celery task wired into daily pipeline chain (turns 5 integration tests GREEN)

---
*Phase: 04-anomaly-detection*
*Completed: 2026-05-28*
