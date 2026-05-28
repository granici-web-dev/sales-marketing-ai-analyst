---
phase: 06-backend-api
plan: 01
subsystem: backend-api
tags: [fastapi, pydantic, auth, schemas, decimal-serialization]
dependency_graph:
  requires:
    - backend/app/core/security.py
    - backend/app/schemas/auth.py
    - backend/app/db/deps.py
    - backend/app/models/user.py
  provides:
    - backend/app/core/dependencies.py (get_current_user)
    - backend/app/schemas/dashboards/sales.py (SalesDashboardResponse + 7 sub-models)
    - backend/app/schemas/dashboards/salespeople.py (SalespeopleDashboardResponse + SalespersonRow)
    - backend/app/schemas/dashboards/marketing.py (MarketingDashboardResponse + LeadVolumeBySource + JunkBySource)
    - backend/app/schemas/health.py (HealthDataResponse added)
  affects:
    - backend/app/api/v1/dashboards.py (plan 03, uses get_current_user + schemas)
    - backend/app/api/v1/insights.py (plan 03, uses get_current_user)
    - backend/services/dashboards/dashboard_read_service.py (plan 02, returns SalesDashboardResponse)
tech_stack:
  added: []
  patterns:
    - "HTTPBearer JWT guard via FastAPI Depends()"
    - "Pydantic v2 field_serializer for Decimal → str (DATA-04)"
    - "Field(alias=) for reserved Python keywords as JSON keys"
key_files:
  created:
    - backend/app/core/dependencies.py
    - backend/app/schemas/dashboards/__init__.py
    - backend/app/schemas/dashboards/sales.py
    - backend/app/schemas/dashboards/salespeople.py
    - backend/app/schemas/dashboards/marketing.py
    - backend/tests/factories/dashboard_factory.py
    - backend/tests/unit/test_dashboard_schemas.py
  modified:
    - backend/app/schemas/health.py (added HealthDataResponse)
decisions:
  - "PeriodRange uses Field(alias='from') and Field(alias='to') with populate_by_name=True — avoids Python keyword conflict for ?from= query params"
  - "SalespersonRow.avg_time_to_first_touch_minutes is int | None — nullable per KI-03 / D-05"
  - "MarketingDashboardResponse.ad_spend/cpl/cac/roas are typed as None = None — explicit null, not optional fields — MARK-03"
  - "Individual @field_serializer per Decimal field (not model-level json_encoders) — Pydantic v2 canonical approach per T-06-01-03"
metrics:
  duration: "~20 minutes"
  completed: "2026-05-28T18:05:00Z"
  tasks_completed: 2
  files_created: 7
  files_modified: 1
---

# Phase 6 Plan 01: Auth Dependency + Dashboard Response Schemas Summary

**One-liner:** HTTPBearer JWT guard dependency (`get_current_user`) + Pydantic v2 response schemas for all 3 dashboards and health data with DATA-04 Decimal-as-string serialization.

## Tasks Completed

| # | Task | Commit | Result |
|---|------|--------|--------|
| 1 | Create get_current_user dependency | `2be1af23` | import ok — HTTPBearer + verify_token + DB user lookup |
| 2 | Dashboard schemas + factory + tests | `15732387` | 11/11 Decimal serialization tests GREEN |

## Key Artifacts

### backend/app/core/dependencies.py
- `get_current_user` FastAPI dependency using `HTTPBearer` security scheme
- Calls `verify_token()` → extracts UUID from `"sub"` claim → DB SELECT (specific columns, no SELECT *)
- 401 for: invalid/expired token, missing sub, non-existent user, inactive user
- No tenant_id in returned `UserOut` — tenant set by `StructlogContextMiddleware` already

### backend/app/schemas/dashboards/sales.py
Exports: `SalesDashboardResponse`, `PeriodRange`, `FunnelCounts`, `ConversionRates`, `KpiCards`, `SourceBreakdownItem`, `RevenueSeries`, `StuckOffer`
- `ConversionRates`: 5 rate fields + 10 WoW/MoM delta fields, all `Decimal | None` with `@field_serializer`
- `KpiCards`: revenue, avg_deal_size, 4 delta fields — all `Decimal | None` with `@field_serializer`

### backend/app/schemas/dashboards/salespeople.py
Exports: `SalespeopleDashboardResponse`, `SalespersonRow`
- `SalespersonRow.avg_time_to_first_touch_minutes: int | None` — nullable (KI-03/D-05)
- 8 Decimal fields each with individual `@field_serializer`

### backend/app/schemas/dashboards/marketing.py
Exports: `MarketingDashboardResponse`, `LeadVolumeBySource`, `LeadVolumeBySourcePoint`, `JunkBySource`
- `ad_spend: None = None` — explicit null (MARK-03 Iteration 2 placeholder)
- `junk_pct` serialized as string (DATA-04)

### backend/app/schemas/health.py (updated)
Added `HealthDataResponse(last_sync_at: datetime | None, last_pipeline_status: str | None, stale: bool)` alongside existing `HealthResponse`

### backend/tests/unit/test_dashboard_schemas.py
11 tests covering DATA-04 Decimal serialization for all schema types. All GREEN.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] pyjwt missing from venv despite being in pyproject.toml**
- **Found during:** Task 1 — import verification of `get_current_user`
- **Issue:** `ModuleNotFoundError: No module named 'jwt'` — pyjwt declared in pyproject.toml (`pyjwt>=2.8,<3`) but not installed in `.venv`
- **Fix:** `pip install "pyjwt>=2.8,<3"` → installed pyjwt 2.13.0
- **Files modified:** none (venv-only)
- **Commit:** `2be1af23` (documented in commit message)

## Success Criteria Verification

- [x] `backend/app/core/dependencies.py` exists and exports `get_current_user`
- [x] `backend/app/schemas/dashboards/sales.py` exports `SalesDashboardResponse`, `FunnelCounts`, `ConversionRates`, `KpiCards`, `SourceBreakdownItem`, `RevenueSeries`, `StuckOffer`
- [x] `backend/app/schemas/dashboards/salespeople.py` exports `SalespeopleDashboardResponse`, `SalespersonRow`
- [x] `backend/app/schemas/dashboards/marketing.py` exports `MarketingDashboardResponse`, `LeadVolumeBySource`, `JunkBySource`
- [x] `backend/app/schemas/health.py` exports `HealthDataResponse` (alongside existing `HealthResponse`)
- [x] All Decimal fields in all schemas have `@field_serializer` returning `str | None`
- [x] `tests/unit/test_dashboard_schemas.py` passes — 11/11 Decimal-as-string assertions GREEN
- [x] `tests/factories/dashboard_factory.py` builds valid dicts for all 3 dashboards + health

## Known Stubs

None — schemas are pure type definitions with no data source stubs. Factory returns representative values for test use only. Dashboard data will be wired from `DashboardReadService` (Plan 02).

## Threat Flags

No new network endpoints, auth paths, or file access patterns introduced in this plan. All items are in-process Pydantic schema definitions and a FastAPI dependency.

The `get_current_user` dependency implements T-06-01-01 (JWT spoofing mitigation) and T-06-01-02 (UserOut info disclosure mitigation) as specified in the plan threat model. No new threat surface beyond what the plan anticipated.

## Self-Check

Files created/modified:
- [x] backend/app/core/dependencies.py — FOUND
- [x] backend/app/schemas/dashboards/__init__.py — FOUND
- [x] backend/app/schemas/dashboards/sales.py — FOUND
- [x] backend/app/schemas/dashboards/salespeople.py — FOUND
- [x] backend/app/schemas/dashboards/marketing.py — FOUND
- [x] backend/app/schemas/health.py — FOUND (updated)
- [x] backend/tests/factories/dashboard_factory.py — FOUND
- [x] backend/tests/unit/test_dashboard_schemas.py — FOUND

Commits: `2be1af23` (Task 1) and `15732387` (Task 2) both verified in git log.

## Self-Check: PASSED
