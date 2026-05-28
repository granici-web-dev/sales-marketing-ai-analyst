---
phase: 06-backend-api
plan: "02"
subsystem: backend-services
tags: [read-service, dashboard, insights, health, sqlalchemy, tdd]
dependency_graph:
  requires:
    - "03-metrics-engine (DailyKpi, SalespersonDailyKpi, SourceDailyKpi ORM models)"
    - "05-ai-insights (DailyInsight ORM model)"
    - "02-mefi-etl (MefiSalesperson, RawMefiLead, MefiLeadHistory ORM models)"
    - "01-foundation (SyncRun, PipelineRun ORM models)"
  provides:
    - "DashboardReadService — 4 async methods for dashboard routers (Plan 06-03)"
    - "InsightReadService — 2 async methods for insights router (Plan 06-03)"
    - "HealthReadService — get_health() for health router (Plan 06-03)"
  affects:
    - "06-03-PLAN.md — routers depend on these service classes"
tech_stack:
  added: []
  patterns:
    - "TDD RED/GREEN cycle for all 3 service classes"
    - "AsyncMock session injection for unit tests (no live DB)"
    - "text() SQL with explicit :tid bindparam for raw_mefi_leads query (MARK-04 exception)"
    - "Decimal arithmetic in Python with zero-division guards (T-06-02-03)"
    - "ZoneInfo('Europe/Bucharest') for yesterday calculation (Pitfall 6)"
key_files:
  created:
    - backend/app/services/dashboards/__init__.py
    - backend/app/services/dashboards/dashboard_read_service.py
    - backend/app/services/dashboards/health_read_service.py
    - backend/app/services/insights/insight_read_service.py
    - backend/tests/unit/test_dashboard_read_service.py
    - backend/tests/unit/test_insight_read_service.py
    - backend/tests/unit/test_health_read_service.py
  modified: []
decisions:
  - "MARK-04 exception documented in code: raw_mefi_leads queried via text() in DashboardReadService.get_marketing_dashboard() — no pre-computed junk-by-source view exists; tenant_id bound explicitly (T-06-02-02)"
  - "SALE-05 locked decision: revenue_series uses always daily granularity — get_sales_dashboard returns one dict per day, no weekly aggregation"
  - "visits_count keeps NULL semantics (not coalesced to 0) — KI-03 and Pitfall 2"
  - "win_rate computed in Python as Decimal(deals_won)/Decimal(leads_assigned) with leads_assigned>0 guard (T-06-02-03)"
  - "datetime.now(BUCHAREST) - 1 day for 'yesterday' in InsightReadService.get_today() (Pitfall 6)"
  - "generation_failed=True for status in ('failed','fallback') per INSI-05"
  - "stale threshold: 26 hours per UI-06 spec"
metrics:
  duration: "6 minutes"
  completed_date: "2026-05-28"
  tasks_completed: 2
  tasks_total: 2
  files_created: 7
  files_modified: 0
  tests_added: 20
  tests_passing: 20
---

# Phase 6 Plan 02: Read Services (Dashboard, Insight, Health) Summary

**One-liner:** Three async read-service classes querying pre-computed metric tables with TDD: DashboardReadService (4 methods), InsightReadService (get_today/get_by_date with Bucharest timezone), HealthReadService (26h stale threshold).

## What Was Built

This plan created the three read-service classes that the Plan 03 FastAPI routers will call. All services are read-only, all methods are async, all queries filter by tenant_id.

### DashboardReadService (`backend/app/services/dashboards/dashboard_read_service.py`)

- **`get_sales_dashboard(from_date, to_date)`** — 5-step async aggregation: funnel counts from DailyKpi SUM, last-day rates + WoW/MoM deltas, source breakdown from SourceDailyKpi, daily revenue series (SALE-05), stuck offers via `get_stuck_offers()`
- **`get_salespeople_dashboard(from_date, to_date)`** — ORM OUTERJOIN SalespersonDailyKpi × MefiSalesperson with CAST(salesperson_external_id AS INTEGER) to match integer external_id; win_rate and avg_deal_size computed in Python
- **`get_marketing_dashboard(from_date, to_date)`** — lead_volume_by_source time series per source, site conversion rate from SourceDailyKpi, junk_by_source via `text()` SQL on raw_mefi_leads (MARK-04 documented exception), `ad_spend/cpl/cac/roas=None` always
- **`get_stuck_offers(from_date, to_date)`** — `text()` SQL querying `v_mefi_leads_active` VIEW joined to `mefi_lead_history` and `mefi_salespeople`; returns offers stuck > 14 days, ordered by days_stuck DESC, limited to 50

### InsightReadService (`backend/app/services/insights/insight_read_service.py`)

- **`get_today()`** — queries `daily_insights WHERE date = yesterday_bucharest`; yesterday computed as `datetime.now(ZoneInfo("Europe/Bucharest")).date() - timedelta(days=1)` (Pitfall 6: pipeline generates for yesterday)
- **`get_by_date(query_date)`** — queries specific date; returns `None` when no row (router raises 404)
- **`generation_failed`** flag: `True` when `status in ("failed", "fallback")` (INSI-05)

### HealthReadService (`backend/app/services/dashboards/health_read_service.py`)

- **`get_health()`** — queries `sync_runs WHERE source='mefi' ORDER BY started_at DESC LIMIT 1` + `pipeline_runs ORDER BY started_at DESC LIMIT 1`; stale logic: `(now_utc - last_sync_at) > timedelta(hours=26)` or `last_sync_at is None` (UI-06)

## Security Mitigations Applied

| Threat ID | Mitigation |
|-----------|-----------|
| T-06-02-01 | All ORM queries: `.where(Model.tenant_id == self._tenant_id)` |
| T-06-02-02 | MARK-04 `text()` query: explicit `:tid` bindparam — `with_loader_criteria` does not fire on `text()` (Pitfall 5) |
| T-06-02-03 | win_rate: `Decimal(deals_won) / Decimal(leads_assigned)` with `leads_assigned > 0` guard — no float, no ZeroDivisionError |

## Test Coverage

| File | Tests | Passed |
|------|-------|--------|
| test_dashboard_read_service.py | 8 | 8 |
| test_insight_read_service.py | 6 | 6 |
| test_health_read_service.py | 6 | 6 |
| **Total** | **20** | **20** |

All tests follow AsyncMock injection pattern (no live DB required).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed `_mock_execute_result(first=None)` sentinel guard**
- **Found during:** Task 1 GREEN phase (test_get_sales_dashboard_empty_range)
- **Issue:** Python's `if first is not None` evaluates to `False` for `None` arg, so `result.first.return_value` was never set — mock returned a MagicMock instead of `None`, causing `Decimal(str(MagicMock()))` to raise `InvalidOperation`
- **Fix:** Changed guard to sentinel object (`_SENTINEL = object()`) so `first=None` correctly sets `result.first.return_value = None`
- **Files modified:** `tests/unit/test_dashboard_read_service.py`

**2. [Rule 1 - Bug] Made `datetime` patchable in InsightReadService**
- **Found during:** Task 2 implementation review
- **Issue:** Test patches `app.services.insights.insight_read_service.datetime`; using aliased import `from datetime import datetime as _datetime_cls` or `import datetime as _dt_module` would break the patch target
- **Fix:** Used `from datetime import date, datetime, timedelta` — `datetime` is now a module-level name that can be patched
- **Files modified:** `backend/app/services/insights/insight_read_service.py`

## Known Stubs

None. All service methods are fully implemented and return real data from pre-computed metric tables. No hardcoded placeholder values or TODO markers.

## Threat Flags

No new threat surface introduced. All new code is read-only SELECT queries on existing tables/views.

## Self-Check: PASSED

- FOUND: backend/app/services/dashboards/__init__.py
- FOUND: backend/app/services/dashboards/dashboard_read_service.py
- FOUND: backend/app/services/dashboards/health_read_service.py
- FOUND: backend/app/services/insights/insight_read_service.py
- FOUND: backend/tests/unit/test_dashboard_read_service.py
- FOUND: backend/tests/unit/test_insight_read_service.py
- FOUND: backend/tests/unit/test_health_read_service.py
- Commits verified: d2d35127, d92469f6, 292b56a3, 475506d3
- All 20 tests PASSED
