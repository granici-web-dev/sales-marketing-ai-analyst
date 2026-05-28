---
phase: 04-anomaly-detection
plan: 03
subsystem: service-layer
tags: [anomaly-detection, sqlalchemy, structlog, decimal, upsert, tdd-green]

# Dependency graph
requires:
  - phase: 04-anomaly-detection
    plan: 02
    provides: DetectedProblem model, migration 007, detected_problems UNIQUE(tenant_id, date, rule_id)
  - phase: 03-metrics-engine
    provides: MetricsRepository UPSERT pattern, DailyKpiService constructor pattern, structlog conventions
provides:
  - AnomalyService with 5 detect methods + run_all_rules orchestrator
  - AnomalyRepository with upsert_detected_problem (3-col conflict target)
  - app.services.anomaly package exporting AnomalyService
affects:
  - 04-04 (Wave 3: detect_anomalies Celery task calls run_all_rules() and uses AnomalyRepository)
  - 05 (Phase 5: AI Insights reads detected_problems rows produced by this service)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Optional pre-fetched data params pattern: detect_*() methods accept data as kwargs; fetch from DB when None"
    - "run_all_rules() delegates to detect methods — no pre-fetch in orchestrator (test-friendly)"
    - "_get_junk_ids() called exactly once per run_all_rules() call (D-11 efficiency requirement)"
    - "3-col pg_insert UPSERT: ON CONFLICT DO UPDATE on (tenant_id, date, rule_id) — Pitfall 5"
    - "ValueError guard before pg_insert: validates tenant_id presence (Pitfall 6)"
    - "All monetary Decimal arithmetic: never float (D-19)"
    - "structlog binds tenant_id + service; logs only counts, never lead_ids (T-04-03-01)"

key-files:
  created:
    - backend/app/services/anomaly/__init__.py
    - backend/app/services/anomaly/anomaly_service.py
    - backend/app/services/repositories/anomaly_repository.py
  modified: []

key-decisions:
  - "Optional params design: detect_*() methods use None defaults — testable with pre-fetched data; auto-fetch from DB when called from run_all_rules()"
  - "run_all_rules() calls _get_junk_ids() then invokes detect methods directly — no separate _fetch_all_data() in orchestrator (avoids AsyncMock.fetchall() coroutine issue in unit tests)"
  - "CLOSE_RATE_FALLBACK = 0.15 when no baseline data available (safe default per D-04)"
  - "Underperforming salesperson loss = count × avg_deal_size × 0.30 (conservative proxy per D-05 NOTE when contracts_closed not available per day)"

# Metrics
duration: 30min
completed: 2026-05-28
---

# Phase 4 Plan 03: Anomaly Service Layer Summary

**AnomalyService (5 rule methods + run_all_rules orchestrator) and AnomalyRepository (3-col UPSERT writer) — all 23 RED-state unit tests turned GREEN**

## Performance

- **Duration:** 30 min
- **Started:** 2026-05-28T11:35:00Z
- **Completed:** 2026-05-28T12:06:21Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Created `AnomalyRepository` in `app/services/repositories/anomaly_repository.py`: `upsert_detected_problem()` with pg_insert `ON CONFLICT DO UPDATE` on `(tenant_id, date, rule_id)` (3-col target, Pitfall 5), ValueError guard on missing/None tenant_id (Pitfall 6), no session.commit() inside method (WR-04)
- Created `AnomalyService` in `app/services/anomaly/anomaly_service.py`: 5 detect methods + `run_all_rules()` orchestrator. Each method accepts optional pre-fetched data (for unit tests) or fetches from DB via `_db_fetch_*` helpers
- All 5 detect methods implement correct loss formulas (D-06/D-07/D-08/D-05), thresholds (D-20), junk exclusion (D-11), severity assignments (ROADMAP SC#2/SC#3)
- Created `app/services/anomaly/__init__.py` exporting AnomalyService
- 23/23 unit tests GREEN: 18 from `test_anomaly_service.py` + 5 from `test_anomaly_repository.py`

## Task Commits

Each task was committed atomically:

1. **Task 1: AnomalyRepository** - `093278af` (feat)
2. **Task 2: AnomalyService + package init** - `b86dd752` (feat)

## Files Created/Modified

- `backend/app/services/repositories/anomaly_repository.py` — AnomalyRepository with `upsert_detected_problem()`: pg_insert ON CONFLICT on (tenant_id, date, rule_id), ValueError guard, no internal commit
- `backend/app/services/anomaly/anomaly_service.py` — AnomalyService: 5 detect methods (slow_first_touch, stuck_offer, showroom_traffic_drop, underperforming_salesperson, junk_lead_quality), `run_all_rules()`, `_get_junk_ids()`, `_db_fetch_*` helpers, constant thresholds
- `backend/app/services/anomaly/__init__.py` — Package init exporting AnomalyService

## Decisions Made

- **Optional params design** — detect_*() methods take optional pre-fetched data (`slow_leads=None`, `baseline_rows=None` etc.); when None, DB helpers are called. This allows unit tests to pass pre-fetched data without DB, while `run_all_rules()` calls detect methods without pre-fetching (methods self-fetch).
- **run_all_rules() orchestration** — only calls `_get_junk_ids()` then invokes each detect method with `kpi_date` and `junk_ids`. No separate `_fetch_all_data()` in orchestrator — avoids AsyncMock.fetchall() coroutine issue in unit tests where detect methods are mocked.
- **CLOSE_RATE_FALLBACK = 0.15** — safe default when no trailing conversion_o_to_c data available (D-04 fallback pattern).
- **Underperforming salesperson loss proxy** — `len(underperforming) × avg_deal_size × 0.30` (D-05 NOTE: conservative proxy when contracts_closed not available per day in daily pipeline).

## Deviations from Plan

### Auto-Fixed Issues

**1. [Rule 1 - Bug] AsyncMock.fetchall() coroutine issue in run_all_rules() tests**
- **Found during:** Task 2
- **Issue:** The plan described `run_all_rules()` calling `_fetch_*` helper methods before calling detect methods. When `AsyncMock()` is used as session in tests, `result.fetchall()` returns a coroutine (not iterable), causing `TypeError: 'coroutine' object is not iterable` in the 2 `TestRunAllRules` tests.
- **Fix:** Restructured design — detect methods accept optional pre-fetched data, auto-fetch from DB when called with `None`. `run_all_rules()` calls `_get_junk_ids()` then calls detect methods without pre-fetching (detect methods self-fetch). This makes `run_all_rules()` unit-testable when detect methods are mocked as AsyncMock.
- **Files modified:** `backend/app/services/anomaly/anomaly_service.py`
- **Commit:** `b86dd752`

## Issues Encountered

None beyond the AsyncMock issue auto-fixed above.

## Known Stubs

None — this plan creates pure Python service logic. No UI data sources or placeholders.

## Threat Flags

None — service-layer files only. All DB queries use parameterized bindparams (T-04-03-02). No PII logged per T-04-03-01. Decimal arithmetic enforced per T-04-03-03.

## Self-Check: PASSED

- `backend/app/services/anomaly/__init__.py` — FOUND
- `backend/app/services/anomaly/anomaly_service.py` — FOUND
- `backend/app/services/repositories/anomaly_repository.py` — FOUND
- Commit `093278af` — FOUND
- Commit `b86dd752` — FOUND
- 23 tests GREEN — VERIFIED
- `detect methods: ['detect_junk_lead_quality', 'detect_showroom_traffic_drop', 'detect_slow_first_touch', 'detect_stuck_offer', 'detect_underperforming_salesperson']` — VERIFIED
- `imports OK` — VERIFIED

## Next Phase Readiness

- Wave 2 (service layer) complete — AnomalyService + AnomalyRepository ready for Wave 3
- Plan 04-04 (Wave 3): detect_anomalies Celery task: call `run_all_rules()`, upsert results via `AnomalyRepository`, wire into daily pipeline chain (turns 5 integration tests GREEN)
- Phase 5 (AI Insights): reads `detected_problems` rows written by this service

---
*Phase: 04-anomaly-detection*
*Completed: 2026-05-28*
