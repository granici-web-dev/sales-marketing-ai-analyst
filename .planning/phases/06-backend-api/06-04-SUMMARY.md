---
plan: 06-04
phase: 06-backend-api
status: complete
executor: orchestrator-inline
completed_at: 2026-05-28
---

# Plan 06-04 Summary — Phase 6 Integration Test Suite

## What Was Built

**Full SC#1-SC#7 integration test suite covering all Phase 6 success criteria.**

`backend/tests/integration/test_phase6_endpoints.py` — 15 tests:

- **SC#1:** `test_sc1_sales_dashboard_200` — GET /dashboards/sales returns 200 with correct shape; `test_sc1_revenue_as_string` — DATA-04: revenue Decimal serialized as string
- **SC#2:** `test_sc2_salespeople_dashboard_200` — GET /dashboards/salespeople returns 200 with `avg_time_to_first_touch_minutes` and `data_completeness_pct`
- **SC#3:** `test_sc3_marketing_dashboard_200` — GET /dashboards/marketing returns 200 with `lead_volume_by_source` list; MARK-03 ad_spend/cpl/cac/roas are null (no ad integrations yet)
- **SC#4:** `test_sc4_insights_today_200` / `_404_when_none` / `_by_date_404_for_missing` / `_generation_failed_when_status_failed` — GET /insights/today and /insights?date= correct 200/404 handling; `generation_failed=True` propagates from status=failed
- **SC#5:** `test_sc5_refresh_first_call_202` / `_second_call_429` — POST /insights/refresh: first call → 202 + pipeline_run_id; second call → 429 + Retry-After
- **SC#6:** `test_sc6_health_data_no_auth` / `_stale_true_propagates` — GET /health/data returns 200 without auth; stale=True propagates correctly
- **SC#7:** `test_sc7_docs_accessible` / `_openapi_json_has_phase6_paths` — /docs and /openapi.json accessible; all 5 Phase 6 paths present in schema
- **Regression:** `test_healthz_phase1_regression` — GET /healthz → `{"status": "ok"}`

## Test Results

- Phase 6 integration suite: **15/15 PASS**
- AI-09 check: CLEAN (zero matches for `anthropic` / `AsyncAnthropic` in `backend/app/api/`)
- Full regression (excl. pre-existing failures): **373 passed, 18 skipped**
- Pre-existing failures: 14 (Phase 3 source KPI: 5, Phase 5 pipeline chain: 1, tenant isolation: 1, DB-dep auth/migration: 7) — none introduced by Phase 6

## Key Decisions / Deviations

- **Deferred import patch target:** `InsightReadService` is imported inside each endpoint function body (AI-09 pattern). Patch target must be `app.services.insights.insight_read_service.InsightReadService`, not `app.api.v1.insights.InsightReadService`. Fixed after initial run → 4 failures → 0 failures.
- **`override_deps` autouse fixture** overrides both `get_current_user` and `get_session` via `app.dependency_overrides` — avoids real DB/Redis in all tests.
- **DashboardFactory** provides Sofa Belle-representative mock data with correct Decimal field structure for DATA-04 assertions.

## Self-Check: PASSED

key-files.created:
  - backend/tests/integration/test_phase6_endpoints.py

All 15 new tests PASS. AI-09 clean. All 7 ROADMAP Phase 6 success criteria verified by test.
